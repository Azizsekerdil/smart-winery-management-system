"""Güvenli AI Terminali / Geliştirici Ajanı uç noktaları.

İş akışı (madde 12):
  1. Plan   → /terminal/plan      (risk değerlendirmesi, etkilenen dosyalar)
  2. Onay   → /terminal/{id}/approval
  3. Kontrol noktası + geçici dal (onayla birlikte otomatik)
  4. Çalıştır → /terminal/{id}/run
  5. Test/lint → /terminal/{id}/verify
  6. Diff   → /terminal/{id}/diff
  7. Birleştir veya geri al → /terminal/{id}/merge | /rollback
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.agent import git_ops
from app.agent.executor import run_command, run_lint, run_tests
from app.agent.sandbox import (
    assess_plan,
    check_command,
    is_within_workspace,
    sandbox_info,
    workspace_root,
)
from app.api.crud import get_or_404
from app.core.audit import record_audit
from app.core.config import settings
from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.ai import AgentRun, AgentTask, AgentTaskStatus, AITaskKind, RiskLevel
from app.models.ops import AuditAction
from app.models.user import User
from app.schemas.ai import (
    AgentApproval,
    AgentPlanRequest,
    AgentRunOut,
    AgentTaskOut,
    CommandCheck,
    SandboxStatus,
    TerminalCommandRequest,
)
from app.schemas.common import Message
from app.services.ai.base import ChatMessage, ProviderError
from app.services.ai.prompts import system_prompt
from app.services.ai.registry import chat_with_fallback
from app.services.codes import next_code

router = APIRouter(prefix="/terminal", tags=["AI Terminali"])

UseTerminal = Annotated[User, Depends(require_perms(Perm.AI_TERMINAL))]
ApproveTerminal = Annotated[User, Depends(require_perms(Perm.AI_TERMINAL_APPROVE))]


def _require_enabled() -> None:
    if not settings.AGENT_ENABLED:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AI Terminali yapılandırmada kapalı (AGENT_ENABLED=false).",
        )


def _task_out(task: AgentTask) -> AgentTaskOut:
    out = AgentTaskOut.model_validate(task)
    out.command_checks = [
        CommandCheck(
            command=v.command, allowed=v.allowed, risk=RiskLevel(v.risk), reason=v.reason,
            matched_rule=v.matched_rule,
        )
        for v in (check_command(c) for c in (task.proposed_commands or []))
    ]
    return out


@router.get("/status", response_model=SandboxStatus, summary="Terminal güvenlik durumu")
async def terminal_status(_user: UseTerminal) -> SandboxStatus:
    info = sandbox_info()
    git_state = await git_ops.state()
    return SandboxStatus(
        **info,
        git_available=git_state.available,
        git_repo=git_state.is_repo,
        current_branch=git_state.branch,
        dirty=git_state.dirty,
    )


@router.post("/check", response_model=CommandCheck, summary="Komutu çalıştırmadan denetle")
async def check_only(payload: TerminalCommandRequest, _user: UseTerminal) -> CommandCheck:
    verdict = check_command(payload.command)
    return CommandCheck(
        command=verdict.command,
        allowed=verdict.allowed,
        risk=RiskLevel(verdict.risk),
        reason=verdict.reason,
        matched_rule=verdict.matched_rule,
    )


@router.post(
    "/plan",
    response_model=AgentTaskOut,
    status_code=status.HTTP_201_CREATED,
    summary="1. Adım — görev planı oluştur (çalıştırmaz)",
)
async def create_plan(
    payload: AgentPlanRequest, request: Request, session: SessionDep, user: UseTerminal
) -> AgentTaskOut:
    _require_enabled()

    plan_steps: list[dict] = []
    commands = list(payload.proposed_commands)
    paths = list(payload.affected_paths)

    # Dil modelinden plan iste (istege bagli; basarisiz olursa manuel plan kullanilir)
    llm_note = None
    if payload.use_llm:
        prompt = (
            "Aşağıdaki geliştirme isteği için ADIM ADIM bir plan çıkar.\n"
            "Yanıtı şu biçimde ver (başka açıklama ekleme):\n"
            "ADIMLAR:\n1. ...\n2. ...\n"
            "DOSYALAR:\n- göreli/yol/dosya.py\n"
            "KOMUTLAR:\n- python -m pytest -q\n\n"
            f"Kurallar: yalnızca {workspace_root()} içinde çalış; "
            "dosya/klasör silme, git push, paket yayınlama önerme.\n\n"
            f"İSTEK:\n{payload.request_text}"
        )
        try:
            result, resolved = await chat_with_fallback(
                session,
                [
                    ChatMessage("system", system_prompt(AITaskKind.KOD_GELISTIRICI)),
                    ChatMessage("user", prompt),
                ],
                provider_key=payload.provider_key,
                model=payload.model,
                task_kind=AITaskKind.KOD_GELISTIRICI,
                temperature=0.2,
                max_tokens=1200,
                user_id=user.id,
            )
            section = None
            for line in result.content.splitlines():
                stripped = line.strip()
                upper = stripped.upper()
                if upper.startswith("ADIMLAR"):
                    section = "steps"
                    continue
                if upper.startswith("DOSYALAR"):
                    section = "paths"
                    continue
                if upper.startswith("KOMUTLAR"):
                    section = "commands"
                    continue
                if not stripped:
                    continue
                item = stripped.lstrip("-*0123456789. ").strip()
                if not item:
                    continue
                if section == "steps":
                    plan_steps.append({"no": len(plan_steps) + 1, "aciklama": item})
                elif section == "paths" and item not in paths:
                    paths.append(item)
                elif section == "commands" and item not in commands:
                    commands.append(item)
            llm_provider, llm_model = resolved.config.provider_key, result.model
        except ProviderError as exc:
            llm_note = (
                "Plan dil modelinden alınamadı, yalnızca girdiğiniz adımlar kullanıldı. "
                f"Sebep: {exc.safe_message}"
            )
            llm_provider, llm_model = None, None
    else:
        llm_provider, llm_model = None, None

    if not plan_steps:
        plan_steps = [
            {"no": i + 1, "aciklama": f"Komut çalıştır: {c}"} for i, c in enumerate(commands)
        ] or [{"no": 1, "aciklama": payload.request_text[:200]}]

    risk, reasons, verdicts = assess_plan(commands, paths)
    if llm_note:
        reasons.append(llm_note)

    task = AgentTask(
        code=await next_code(session, AgentTask),
        title=(payload.title or payload.request_text)[:220],
        request_text=payload.request_text,
        user_id=user.id,
        provider_key=llm_provider,
        model=llm_model,
        status=(
            AgentTaskStatus.REDDEDILDI if risk == "engellendi" else AgentTaskStatus.PLAN_HAZIR
        ),
        risk_level=risk,
        risk_reasons=reasons,
        plan_steps=plan_steps,
        affected_paths=paths,
        proposed_commands=commands,
        created_by_id=user.id,
    )
    if risk == "engellendi":
        task.rejection_reason = "Plan güvenlik politikası tarafından engellendi."

    session.add(task)
    await session.flush()

    await record_audit(
        session,
        action=AuditAction.TERMINAL_KOMUT,
        entity_type="agent_tasks",
        entity_id=task.id,
        entity_code=task.code,
        summary=f"AI terminal planı oluşturuldu ({risk}): {task.title[:120]}",
        after={
            "risk": risk,
            "komutlar": commands,
            "dosyalar": paths,
            "engellenen": [v.command for v in verdicts if not v.allowed],
        },
        user=user,
        request=request,
        ai_provider=llm_provider,
        ai_model=llm_model,
        agent_task_id=task.id,
        severity="uyari" if risk in ("yuksek", "engellendi") else "bilgi",
    )
    await session.commit()
    await session.refresh(task)
    return _task_out(task)


@router.get("", response_model=list[AgentTaskOut], summary="Görev listesi")
async def list_tasks(
    session: SessionDep, _user: UseTerminal, limit: int = Query(50, le=200)
) -> list[AgentTaskOut]:
    rows = (
        (await session.execute(select(AgentTask).order_by(AgentTask.id.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return [_task_out(t) for t in rows]


@router.get("/{task_id}", response_model=AgentTaskOut, summary="Görev detayı")
async def get_task(task_id: int, session: SessionDep, _user: UseTerminal) -> AgentTaskOut:
    task = await get_or_404(session, AgentTask, task_id, "Görev")
    return _task_out(task)


@router.post(
    "/{task_id}/approval",
    response_model=AgentTaskOut,
    summary="2. Adım — planı onayla / reddet (onayla birlikte Git kontrol noktası oluşur)",
)
async def approve_task(
    task_id: int,
    payload: AgentApproval,
    request: Request,
    session: SessionDep,
    user: ApproveTerminal,
) -> AgentTaskOut:
    _require_enabled()
    task = await get_or_404(session, AgentTask, task_id, "Görev")

    if task.risk_level == RiskLevel.ENGELLENDI:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Bu görev güvenlik politikası tarafından engellendi ve onaylanamaz. "
            + " ".join(task.risk_reasons or []),
        )
    if task.status not in (AgentTaskStatus.PLAN_HAZIR, AgentTaskStatus.ONAY_BEKLIYOR):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Görev '{task.status}' durumunda; onaylanamaz."
        )

    before = task.to_dict()
    if not payload.approve:
        task.status = AgentTaskStatus.REDDEDILDI
        task.rejection_reason = payload.reason
        await record_audit(
            session,
            action=AuditAction.TERMINAL_RED,
            entity_type="agent_tasks",
            entity_id=task.id,
            entity_code=task.code,
            summary=f"AI terminal görevi reddedildi: {payload.reason or '—'}",
            before=before,
            after=task.to_dict(),
            user=user,
            request=request,
            agent_task_id=task.id,
            severity="uyari",
        )
        await session.commit()
        await session.refresh(task)
        return _task_out(task)

    # --- Git kontrol noktasi + gecici dal ---------------------------------
    commit, msg = await git_ops.create_checkpoint(task.code)
    task.git_checkpoint = commit
    notes = [msg]

    if commit:
        ok, branch = await git_ops.create_branch(f"ai/{task.code.lower()}")
        if ok:
            task.git_branch = branch
            notes.append(f"Geçici dal: {branch}")
        else:
            notes.append(f"Dal oluşturulamadı: {branch}")

    task.status = AgentTaskStatus.ONAYLANDI
    task.approved_by_id = user.id
    task.approved_at = dt.datetime.now(dt.UTC)
    task.result_summary = " · ".join(notes)

    await record_audit(
        session,
        action=AuditAction.TERMINAL_ONAY,
        entity_type="agent_tasks",
        entity_id=task.id,
        entity_code=task.code,
        summary=f"AI terminal görevi onaylandı. {task.result_summary}",
        before=before,
        after=task.to_dict(),
        user=user,
        request=request,
        agent_task_id=task.id,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(task)
    return _task_out(task)


@router.post(
    "/{task_id}/run",
    response_model=list[AgentRunOut],
    summary="3. Adım — onaylanmış komutları çalıştır",
)
async def run_task(
    task_id: int, request: Request, session: SessionDep, user: ApproveTerminal
) -> list[AgentRunOut]:
    _require_enabled()
    task = await get_or_404(session, AgentTask, task_id, "Görev")

    if settings.AGENT_REQUIRE_APPROVAL and task.status != AgentTaskStatus.ONAYLANDI:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Görev çalıştırılmadan önce onaylanmalıdır (plan → onay → çalıştır).",
        )

    task.status = AgentTaskStatus.CALISIYOR
    task.started_at = dt.datetime.now(dt.UTC)
    await session.flush()

    results: list[AgentRun] = []
    for index, command in enumerate(task.proposed_commands or [], start=1):
        started = dt.datetime.now(dt.UTC)
        result = await run_command(command, cwd=str(settings.agent_workspace_path))
        run = AgentRun(
            task_id=task.id,
            sequence=index,
            command=command,
            cwd=str(settings.agent_workspace_path),
            allowed=result.allowed,
            block_reason=result.block_reason,
            started_at=started,
            finished_at=dt.datetime.now(dt.UTC),
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            stdout=result.stdout,
            stderr=result.stderr,
            truncated=result.truncated,
        )
        session.add(run)
        results.append(run)

        await record_audit(
            session,
            action=AuditAction.TERMINAL_KOMUT,
            entity_type="agent_runs",
            entity_code=task.code,
            summary=f"Komut çalıştırıldı ({'engellendi' if not result.allowed else result.exit_code}): {command[:150]}",
            after={
                "komut": command,
                "cikis_kodu": result.exit_code,
                "izin": result.allowed,
                "zaman_asimi": result.timed_out,
            },
            user=user,
            request=request,
            agent_task_id=task.id,
            severity="uyari" if (not result.allowed or result.exit_code) else "bilgi",
        )

        if not result.allowed or (result.exit_code not in (0, None)):
            task.status = AgentTaskStatus.BASARISIZ
            task.result_summary = (
                f"{index}. komut başarısız: {result.block_reason or result.stderr[:200]}"
            )
            break
    else:
        task.status = AgentTaskStatus.TEST_EDILIYOR
        task.result_summary = f"{len(results)} komut başarıyla çalıştı."

    await session.flush()
    await session.commit()
    for r in results:
        await session.refresh(r)
    return [AgentRunOut.model_validate(r) for r in results]


@router.post(
    "/{task_id}/verify",
    response_model=AgentTaskOut,
    summary="4. Adım — lint + test çalıştır, diff üret",
)
async def verify_task(
    task_id: int,
    request: Request,
    session: SessionDep,
    user: ApproveTerminal,
    run_lint_check: bool = Query(True, alias="lint"),
    run_test_check: bool = Query(True, alias="tests"),
) -> AgentTaskOut:
    _require_enabled()
    task = await get_or_404(session, AgentTask, task_id, "Görev")

    if run_lint_check:
        lint_result = await run_lint()
        task.lint_output = (lint_result.stdout + "\n" + lint_result.stderr).strip()[:20000]

    if run_test_check:
        test_result = await run_tests()
        task.test_output = (test_result.stdout + "\n" + test_result.stderr).strip()[:40000]
        task.tests_passed = test_result.exit_code == 0
        task.status = (
            AgentTaskStatus.BASARILI if task.tests_passed else AgentTaskStatus.BASARISIZ
        )

    task.diff_text = (await git_ops.diff(base=task.git_checkpoint))[:100_000]
    task.finished_at = dt.datetime.now(dt.UTC)

    await record_audit(
        session,
        action=AuditAction.TERMINAL_KOMUT,
        entity_type="agent_tasks",
        entity_id=task.id,
        entity_code=task.code,
        summary=f"Doğrulama tamamlandı — testler: "
        f"{'geçti' if task.tests_passed else 'başarısız' if task.tests_passed is False else 'çalıştırılmadı'}",
        user=user,
        request=request,
        agent_task_id=task.id,
        severity="uyari" if task.tests_passed is False else "bilgi",
    )
    await session.commit()
    await session.refresh(task)
    return _task_out(task)


@router.get("/{task_id}/diff", summary="Değişiklik farkı (diff)")
async def task_diff(task_id: int, session: SessionDep, _user: UseTerminal) -> dict:
    task = await get_or_404(session, AgentTask, task_id, "Görev")
    text = task.diff_text or await git_ops.diff(base=task.git_checkpoint)
    return {"task_code": task.code, "checkpoint": task.git_checkpoint, "diff": text}


@router.get("/{task_id}/runs", response_model=list[AgentRunOut], summary="Komut çıktıları")
async def task_runs(task_id: int, session: SessionDep, _user: UseTerminal) -> list[AgentRunOut]:
    await get_or_404(session, AgentTask, task_id, "Görev")
    rows = (
        (
            await session.execute(
                select(AgentRun).where(AgentRun.task_id == task_id).order_by(AgentRun.sequence)
            )
        )
        .scalars()
        .all()
    )
    return [AgentRunOut.model_validate(r) for r in rows]


@router.post(
    "/{task_id}/merge",
    response_model=AgentTaskOut,
    summary="5a. Adım — değişiklikleri ana dala birleştir",
)
async def merge_task(
    task_id: int,
    request: Request,
    session: SessionDep,
    user: ApproveTerminal,
    target: str = Query("main"),
) -> AgentTaskOut:
    _require_enabled()
    task = await get_or_404(session, AgentTask, task_id, "Görev")

    if task.tests_passed is False:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Testler başarısız. Birleştirmeden önce hataları düzeltin veya geri alın.",
        )
    if not task.git_branch:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu görev için geçici dal yok.")

    await git_ops.commit_all(f"AI görevi {task.code}: {task.title[:80]}")
    ok, msg = await git_ops.merge_into(target, task.git_branch)
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT, msg)

    task.status = AgentTaskStatus.BASARILI
    task.result_summary = msg
    task.finished_at = dt.datetime.now(dt.UTC)

    await record_audit(
        session,
        action=AuditAction.TERMINAL_ONAY,
        entity_type="agent_tasks",
        entity_id=task.id,
        entity_code=task.code,
        summary=f"AI değişiklikleri birleştirildi: {msg}",
        user=user,
        request=request,
        agent_task_id=task.id,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(task)
    return _task_out(task)


@router.post(
    "/{task_id}/rollback",
    response_model=AgentTaskOut,
    summary="5b. Adım — kontrol noktasına geri al",
)
async def rollback_task(
    task_id: int, request: Request, session: SessionDep, user: ApproveTerminal
) -> AgentTaskOut:
    _require_enabled()
    task = await get_or_404(session, AgentTask, task_id, "Görev")
    if not task.git_checkpoint:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Bu görev için Git kontrol noktası bulunmuyor."
        )

    ok, msg = await git_ops.rollback(task.git_checkpoint)
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT, msg)

    task.status = AgentTaskStatus.GERI_ALINDI
    task.result_summary = msg
    task.finished_at = dt.datetime.now(dt.UTC)

    await record_audit(
        session,
        action=AuditAction.TERMINAL_GERI_AL,
        entity_type="agent_tasks",
        entity_id=task.id,
        entity_code=task.code,
        summary=f"AI değişiklikleri geri alındı: {msg}",
        user=user,
        request=request,
        agent_task_id=task.id,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(task)
    return _task_out(task)


@router.post("/{task_id}/cancel", response_model=Message, summary="Görevi iptal et")
async def cancel_task(
    task_id: int, request: Request, session: SessionDep, user: UseTerminal
) -> Message:
    task = await get_or_404(session, AgentTask, task_id, "Görev")
    if task.status in (AgentTaskStatus.BASARILI, AgentTaskStatus.GERI_ALINDI):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Görev '{task.status}' durumunda.")
    task.status = AgentTaskStatus.IPTAL
    await record_audit(
        session,
        action=AuditAction.TERMINAL_RED,
        entity_type="agent_tasks",
        entity_id=task.id,
        entity_code=task.code,
        summary="AI terminal görevi iptal edildi",
        user=user,
        request=request,
        agent_task_id=task.id,
    )
    await session.commit()
    return Message(detail="Görev iptal edildi.")


@router.post(
    "/run-once",
    response_model=AgentRunOut,
    summary="Tek komut çalıştır (yalnızca düşük riskli, onaylı kullanıcı)",
)
async def run_single(
    payload: TerminalCommandRequest,
    request: Request,
    session: SessionDep,
    user: ApproveTerminal,
) -> AgentRunOut:
    _require_enabled()
    verdict = check_command(payload.command)
    if not verdict.allowed:
        await record_audit(
            session,
            action=AuditAction.TERMINAL_KOMUT,
            entity_type="agent_runs",
            summary=f"Engellenen komut denemesi: {payload.command[:150]}",
            after={"komut": payload.command, "gerekce": verdict.reason},
            user=user,
            request=request,
            severity="uyari",
            commit=True,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, verdict.reason)

    if payload.cwd and not is_within_workspace(payload.cwd):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Çalışma dizini {settings.agent_workspace_path} dışında olamaz.",
        )

    task_id = payload.task_id
    if task_id is None:
        task = AgentTask(
            code=await next_code(session, AgentTask),
            title=payload.command[:220],
            request_text=payload.command,
            user_id=user.id,
            status=AgentTaskStatus.CALISIYOR,
            risk_level=verdict.risk,
            risk_reasons=[verdict.reason],
            proposed_commands=[payload.command],
            approved_by_id=user.id,
            approved_at=dt.datetime.now(dt.UTC),
            started_at=dt.datetime.now(dt.UTC),
            created_by_id=user.id,
        )
        session.add(task)
        await session.flush()
        task_id = task.id
    else:
        task = await get_or_404(session, AgentTask, task_id, "Görev")

    started = dt.datetime.now(dt.UTC)
    result = await run_command(payload.command, cwd=payload.cwd)
    run = AgentRun(
        task_id=task_id,
        sequence=1,
        command=payload.command,
        cwd=payload.cwd or str(settings.agent_workspace_path),
        allowed=result.allowed,
        block_reason=result.block_reason,
        started_at=started,
        finished_at=dt.datetime.now(dt.UTC),
        exit_code=result.exit_code,
        timed_out=result.timed_out,
        stdout=result.stdout,
        stderr=result.stderr,
        truncated=result.truncated,
    )
    session.add(run)
    task.status = (
        AgentTaskStatus.BASARILI if result.exit_code == 0 else AgentTaskStatus.BASARISIZ
    )
    task.finished_at = dt.datetime.now(dt.UTC)

    await record_audit(
        session,
        action=AuditAction.TERMINAL_KOMUT,
        entity_type="agent_runs",
        entity_code=task.code,
        summary=f"Tek komut çalıştırıldı (çıkış {result.exit_code}): {payload.command[:150]}",
        after={"komut": payload.command, "cikis_kodu": result.exit_code},
        user=user,
        request=request,
        agent_task_id=task_id,
        severity="uyari" if result.exit_code else "bilgi",
    )
    await session.commit()
    await session.refresh(run)
    return AgentRunOut.model_validate(run)
