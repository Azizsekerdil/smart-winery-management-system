"""Git kontrol noktasi, dal yonetimi, diff ve guvenli geri alma.

`git push` ve uzak depo islemleri BILINCLI olarak yoktur; GitHub'a gonderim
yalnizca kullanicinin acik onayiyla, ayri bir akista yapilir.
"""

from __future__ import annotations

import datetime as dt
import shutil
from dataclasses import dataclass

from app.agent.executor import run_command
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("agent.git")


@dataclass(slots=True)
class GitState:
    available: bool
    is_repo: bool
    branch: str | None = None
    dirty: bool = False
    head: str | None = None
    message: str = ""


def git_available() -> bool:
    return shutil.which("git") is not None


async def state() -> GitState:
    if not git_available():
        return GitState(False, False, message="Git kurulu değil.")

    root = str(settings.agent_workspace_path)
    check = await run_command("git rev-parse --is-inside-work-tree", cwd=root)
    if check.exit_code != 0:
        return GitState(True, False, message="Bu klasör bir Git deposu değil.")

    branch_res = await run_command("git rev-parse --abbrev-ref HEAD", cwd=root)
    status_res = await run_command("git status --porcelain", cwd=root)
    head_res = await run_command("git rev-parse --short HEAD", cwd=root)

    return GitState(
        available=True,
        is_repo=True,
        branch=(branch_res.stdout or "").strip() or None,
        dirty=bool((status_res.stdout or "").strip()),
        head=(head_res.stdout or "").strip() or None,
        message="Hazır.",
    )


async def create_checkpoint(label: str) -> tuple[str | None, str]:
    """Islem oncesi kontrol noktasi: tum degisiklikleri stash'e yedekler ve
    geri donulebilir bir etiket birakir. (commit, mesaj) doner."""
    st = await state()
    if not st.is_repo:
        return None, st.message

    root = str(settings.agent_workspace_path)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = f"ai-kontrol-{stamp}"

    if st.dirty:
        add = await run_command("git add -A", cwd=root)
        if add.exit_code != 0:
            return None, f"git add başarısız: {add.stderr[:200]}"
        commit = await run_command(
            f'git commit -m "AI kontrol noktası: {label[:60]}" --no-verify', cwd=root
        )
        if commit.exit_code not in (0, 1):  # 1 = değişiklik yok
            return None, f"Kontrol noktası oluşturulamadı: {commit.stderr[:200]}"

    head = await run_command("git rev-parse --short HEAD", cwd=root)
    commit_id = (head.stdout or "").strip()
    await run_command(f'git tag {tag}', cwd=root)
    return commit_id, f"Kontrol noktası oluşturuldu: {commit_id} ({tag})"


async def create_branch(name: str) -> tuple[bool, str]:
    root = str(settings.agent_workspace_path)
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "-_/").strip("/")[:60]
    if not safe:
        return False, "Geçersiz dal adı."
    result = await run_command(f"git switch -c {safe}", cwd=root)
    if result.exit_code != 0:
        alt = await run_command(f"git checkout -b {safe}", cwd=root)
        if alt.exit_code != 0:
            return False, f"Dal oluşturulamadı: {alt.stderr[:200]}"
    return True, safe


async def switch_branch(name: str) -> tuple[bool, str]:
    root = str(settings.agent_workspace_path)
    result = await run_command(f"git switch {name}", cwd=root)
    if result.exit_code != 0:
        return False, result.stderr[:300]
    return True, f"{name} dalına geçildi."


async def diff(*, staged: bool = False, base: str | None = None) -> str:
    root = str(settings.agent_workspace_path)
    if base:
        cmd = f"git diff {base} --stat"
        stat = await run_command(cmd, cwd=root)
        full = await run_command(f"git diff {base}", cwd=root)
    else:
        stat = await run_command("git diff --stat" + (" --cached" if staged else ""), cwd=root)
        full = await run_command("git diff" + (" --cached" if staged else ""), cwd=root)
    parts = []
    if stat.stdout.strip():
        parts.append("## Özet\n" + stat.stdout.strip())
    if full.stdout.strip():
        parts.append("## Ayrıntı\n" + full.stdout.strip())
    return "\n\n".join(parts) or "Değişiklik yok."


async def rollback(commit: str) -> tuple[bool, str]:
    """Kontrol noktasina guvenli geri donus.

    `--hard` yerine once mevcut durumu yedekler, sonra geri doner.
    """
    root = str(settings.agent_workspace_path)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    await run_command("git add -A", cwd=root)
    await run_command(f'git commit -m "AI geri alma öncesi yedek {stamp}" --no-verify', cwd=root)
    result = await run_command(f"git reset --hard {commit}", cwd=root)
    if result.exit_code != 0:
        return False, f"Geri alma başarısız: {result.stderr[:300]}"
    return True, f"{commit} kontrol noktasına dönüldü. Önceki durum yedek commit'te saklandı."


async def merge_into(target_branch: str, source_branch: str) -> tuple[bool, str]:
    root = str(settings.agent_workspace_path)
    ok, msg = await switch_branch(target_branch)
    if not ok:
        return False, msg
    result = await run_command(f"git merge {source_branch} --no-ff", cwd=root)
    if result.exit_code != 0:
        await run_command("git merge --abort", cwd=root)
        return False, f"Birleştirme başarısız (geri alındı): {result.stderr[:300]}"
    return True, f"{source_branch} → {target_branch} birleştirildi."


async def commit_all(message: str) -> tuple[bool, str]:
    root = str(settings.agent_workspace_path)
    await run_command("git add -A", cwd=root)
    clean = message.replace('"', "'")[:200]
    result = await run_command(f'git commit -m "{clean}" --no-verify', cwd=root)
    if result.exit_code == 1 and "nothing to commit" in (result.stdout + result.stderr).lower():
        return True, "Kaydedilecek değişiklik yok."
    if result.exit_code != 0:
        return False, result.stderr[:300]
    return True, result.stdout[:300]
