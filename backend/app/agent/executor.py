"""Guvenli komut calistirici.

Ozellikler:
  * kabuk KULLANILMAZ (`shell=False`) - enjeksiyon yuzeyi yoktur
  * calisma dizini her zaman calisma alani icinde
  * zaman asimi + cikti boyutu siniri
  * cikti maskeleme (API anahtarlari, belirtecler)
  * calisan surecin iptali
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from app.agent.sandbox import CommandVerdict, SandboxViolation, check_command, safe_path
from app.core.config import settings
from app.core.logging import get_logger, scrub

log = get_logger("agent.executor")

# Alt surece SIZDIRILMAYACAK ortam degiskenleri
SENSITIVE_ENV_PREFIXES = (
    "ANTHROPIC_", "NVIDIA_", "OPENAI_", "SECRET_", "SECRETS_", "AWS_", "AZURE_",
    "GH_", "GITHUB_", "DATABASE_URL",
)


@dataclass(slots=True)
class RunResult:
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool
    allowed: bool = True
    block_reason: str | None = None


def _child_env() -> dict[str, str]:
    """Gizli degerleri temizlenmis ortam degiskenleri."""
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(k.upper().startswith(p) for p in SENSITIVE_ENV_PREFIXES)
    }
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["NO_COLOR"] = "1"
    # Sanal ortami yola ekle
    venv_scripts = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    if venv_scripts.exists():
        env["PATH"] = f"{venv_scripts}{os.pathsep}{env.get('PATH', '')}"
    return env


def _truncate(data: bytes, limit: int) -> tuple[str, bool]:
    truncated = len(data) > limit
    payload = data[:limit]
    text = payload.decode("utf-8", errors="replace")
    if truncated:
        text += f"\n\n… [çıktı {limit} bayt sınırında kesildi]"
    return scrub(text), truncated


async def run_command(
    command: str,
    *,
    cwd: str | None = None,
    timeout: int | None = None,
    max_output: int | None = None,
) -> RunResult:
    """Tek bir komutu guvenli sekilde calistirir."""
    verdict: CommandVerdict = check_command(command)
    if not verdict.allowed:
        return RunResult(
            command=command,
            exit_code=None,
            stdout="",
            stderr=verdict.reason,
            timed_out=False,
            truncated=False,
            allowed=False,
            block_reason=verdict.reason,
        )

    try:
        workdir = safe_path(cwd) if cwd else safe_path(".")
    except SandboxViolation as exc:
        return RunResult(
            command=command, exit_code=None, stdout="", stderr=str(exc),
            timed_out=False, truncated=False, allowed=False, block_reason=str(exc),
        )
    if not workdir.exists():
        return RunResult(
            command=command, exit_code=None, stdout="",
            stderr=f"Çalışma dizini bulunamadı: {workdir}",
            timed_out=False, truncated=False, allowed=False,
            block_reason="Çalışma dizini yok.",
        )

    timeout = timeout or settings.AGENT_COMMAND_TIMEOUT_SECONDS
    max_output = max_output or settings.AGENT_MAX_OUTPUT_BYTES

    try:
        argv = shlex.split(command, posix=False)
    except ValueError as exc:
        return RunResult(
            command=command, exit_code=None, stdout="", stderr=f"Ayrıştırma hatası: {exc}",
            timed_out=False, truncated=False, allowed=False, block_reason="Ayrıştırma hatası.",
        )
    argv = [a.strip('"') for a in argv]

    log.info("agent_komut", command=scrub(command), cwd=str(workdir))

    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workdir),
            env=_child_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return RunResult(
            command=command, exit_code=None, stdout="",
            stderr=f"Komut bulunamadı: {argv[0]}. Aracın kurulu olduğundan emin olun.",
            timed_out=False, truncated=False, allowed=True,
        )
    except OSError as exc:
        return RunResult(
            command=command, exit_code=None, stdout="",
            stderr=f"Komut başlatılamadı: {type(exc).__name__}",
            timed_out=False, truncated=False, allowed=True,
        )

    timed_out = False
    try:
        raw_out, raw_err = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        timed_out = True
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        raw_out, raw_err = b"", f"Komut {timeout} saniyede tamamlanamadı ve durduruldu.".encode()

    stdout, t1 = _truncate(raw_out or b"", max_output)
    stderr, t2 = _truncate(raw_err or b"", max_output // 2)

    return RunResult(
        command=command,
        exit_code=process.returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        truncated=t1 or t2,
    )


async def run_tests(cwd: str | None = None) -> RunResult:
    """Proje testlerini calistirir."""
    return await run_command(
        "python -m pytest -q --maxfail=5", cwd=cwd or str(settings.agent_workspace_path)
    )


async def run_lint(cwd: str | None = None) -> RunResult:
    """Ruff ile kod kalitesi denetimi."""
    return await run_command(
        "python -m ruff check backend", cwd=cwd or str(settings.agent_workspace_path)
    )
