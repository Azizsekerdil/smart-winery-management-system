"""AI terminalinin guvenlik cekirdegi.

Iki bagimsiz savunma katmani vardir:

1. **Yol hapsi (path jail)** — her yol `AGENT_WORKSPACE` (varsayilan D:\\Wine)
   altinda cozulur. Sembolik bag, `..`, surucu degisimi ve UNC yollari
   normalize edildikten SONRA kontrol edilir.
2. **Komut politikasi** — yalnizca acikca izin verilen calistirilabilirler
   kabul edilir (izin listesi); ayrica yikici kaliplar icin kara liste vardir.
   Kabuk zincirleme operatorleri (`;`, `&&`, `|`, yonlendirme) reddedilir ki
   izin listesi atlatilamasin.

Bu modul VERITABANINA VE AGA DOKUNMAZ; saf ve test edilebilirdir.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path, PurePath

from app.core.config import settings

# ------------------------------------------------------------- izin listesi
# Yalnizca proje gelistirmesi icin gereken araclar.
ALLOWED_EXECUTABLES: frozenset[str] = frozenset(
    {
        "python", "python.exe", "py",
        "pip",
        "pytest",
        "ruff",
        "mypy",
        "alembic",
        "uvicorn",
        "npm", "npx", "node",
        "git",
        "echo",
        "type",  # Windows: dosya icerigi
        "dir", "ls",
        "where", "which",
    }
)

# Git icin izin verilen alt komutlar (yikici olanlar disarida)
GIT_ALLOWED_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "status", "diff", "log", "show", "add", "commit", "branch", "checkout",
        "switch", "stash", "rev-parse", "restore", "config", "init", "tag",
        "merge", "cherry-pick", "reset",
    }
)

GIT_BLOCKED_SUBCOMMANDS: frozenset[str] = frozenset(
    {"push", "remote", "clean", "filter-branch", "gc", "prune", "reflog"}
)

# npm/pip icin izin verilen alt komutlar.
# `install` / `ci` BILEREK YOK: paket kurulumu, paketin kendi kurulum betigini
# calistirir ve bu betik izin listesinin de yol hapsinin de disindadir.
PACKAGE_ALLOWED_SUBCOMMANDS: frozenset[str] = frozenset(
    {"run", "test", "list", "audit", "outdated", "show", "build"}
)

# Yalnizca `AGENT_ALLOW_PACKAGE_INSTALL=true` ile acilan alt komutlar.
PACKAGE_INSTALL_SUBCOMMANDS: frozenset[str] = frozenset({"install", "ci", "exec"})
PACKAGE_BLOCKED_SUBCOMMANDS: frozenset[str] = frozenset(
    {"publish", "unpublish", "adduser", "login", "logout", "token", "owner", "deprecate"}
)

# --------------------------------------------------------------- kara liste
BLOCKED_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\brm\s+-[a-z]*[rf]", re.I), "Özyinelemeli/zorlamalı silme"),
    (re.compile(r"(?i)\brmdir\b|\bRemove-Item\b"), "Klasör silme komutu"),
    (re.compile(r"(?i)\bdel\s+/[sq]"), "Toplu dosya silme"),
    (re.compile(r"(?i)\bformat\b\s+[a-z]:"), "Disk biçimlendirme"),
    (re.compile(r"(?i)\bdiskpart\b|\bmkfs\b|\bfdisk\b"), "Disk yönetimi"),
    (re.compile(r"(?i)\breg\s+(add|delete)\b|\bSet-ItemProperty\b.*HK(LM|CU)"), "Kayıt defteri değişikliği"),
    (re.compile(r"(?i)\bnew-itemproperty\b|\bregedit\b"), "Kayıt defteri erişimi"),
    (re.compile(r"(?i)\bnetsh\b|\bfirewall\b|\bDefender\b|\bMpPreference\b"), "Güvenlik yazılımı/ağ ayarı"),
    (re.compile(r"(?i)\bsc\s+(stop|delete|config)\b|\bStop-Service\b"), "Sistem servisi değişikliği"),
    (re.compile(r"(?i)\bshutdown\b|\bRestart-Computer\b"), "Sistemi kapatma/yeniden başlatma"),
    (re.compile(r"(?i)\btaskkill\b|\bStop-Process\b"), "Süreç sonlandırma"),
    (re.compile(r"(?i)\bnet\s+user\b|\bAdd-LocalGroupMember\b"), "Kullanıcı/yetki değişikliği"),
    (re.compile(r"(?i)\bicacls\b|\bcacls\b|\btakeown\b"), "Dosya izni değişikliği"),
    (re.compile(r"(?i)\b(curl|wget|Invoke-WebRequest|iwr|Invoke-RestMethod)\b"), "Ağdan indirme"),
    (re.compile(r"(?i)\bInvoke-Expression\b|\biex\b|\bStart-Process\b"), "Dinamik komut çalıştırma"),
    (re.compile(r"(?i)\bbase64\b\s+-d|\bFromBase64String\b"), "Kodlanmış komut çözme"),
    (re.compile(r"(?i)\bgit\s+push\b"), "Onaysız uzak depo gönderimi"),
    (re.compile(r"(?i)\bnpm\s+publish\b|\btwine\s+upload\b|\bpip\s+upload\b"), "Onaysız paket yayınlama"),
    (re.compile(r"(?i)\bdrop\s+(database|table)\b"), "Veritabanı silme"),
    (re.compile(r"(?i)\balembic\s+downgrade\b"), "Migration geri alma"),
    (re.compile(r"(?i)\.env\b"), "Gizli anahtar dosyasına erişim"),
    (re.compile(r"(?i)\bid_rsa\b|\.ssh\b|credentials?\.json|\.pem\b"), "Kimlik bilgisi dosyası"),
    (re.compile(r"(?i)%USERPROFILE%|\$env:USERPROFILE|\$HOME\b"), "Kullanıcı profili erişimi"),
    # Windows her iki ayraci da kabul eder; yalnizca ters bolu aramak
    # "C:/Windows/..." yazimiyla atlatilabilirdi.
    (re.compile(r"(?i)[a-z]:[\\/](Windows|Program Files( \(x86\))?|Users)\b"), "Sistem dizini erişimi"),
)

# Satir ici kod calistirma: izin listesini tamamen anlamsiz kilar, cunku
# yorumlayiciya verilen kod hicbir kaliba takilmadan istedigi dosyayi acabilir
# (or. `python -c "open('C:/Windows/Temp/x','w')"`). Kod, dosyaya yazilip
# calistirilmalidir; boylece degisiklik diff'te gorunur ve incelenebilir.
INLINE_CODE_FLAGS: dict[str, frozenset[str]] = {
    "python": frozenset({"-c", "-"}),
    "python.exe": frozenset({"-c", "-"}),
    "py": frozenset({"-c", "-"}),
    "node": frozenset({"-e", "--eval", "-p", "--print", "-"}),
}

# Kabuk zincirleme / yonlendirme: izin listesini atlatmayi engeller
SHELL_METACHARACTERS: tuple[str, ...] = ("&&", "||", ";", "|", ">", "<", "`", "$(", "&")

# Yuksek riskli ama izin verilebilir (ek onay ister)
ELEVATED_RISK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bgit\s+reset\s+--hard\b"), "Yerel değişiklikler geri alınacak"),
    (re.compile(r"(?i)\bgit\s+checkout\s+--\s"), "Dosya değişiklikleri atılacak"),
    # `npm ci` de bagimlilik kurar (kurulum betikleri calisir); `install` ile
    # ayni risk sinifindadir ve ayni sekilde isaretlenmelidir.
    (
        re.compile(r"(?i)\b(pip|npm)\s+install\b|\bnpm\s+ci\b"),
        "Bağımlılık kurulumu yapılacak",
    ),
    (re.compile(r"(?i)\balembic\s+upgrade\b"), "Veritabanı şeması değişecek"),
    (re.compile(r"(?i)\bgit\s+merge\b|\bgit\s+cherry-pick\b"), "Dal birleştirme"),
    # npx, yerelde kurulu olmayan bir paketi kayit defterinden indirip
    # calistirabilir; bu nedenle her zaman acik onay ister.
    (re.compile(r"(?i)^\s*npx\b"), "npx uzak paket indirip çalıştırabilir"),
)


@dataclass(slots=True)
class CommandVerdict:
    command: str
    allowed: bool
    risk: str  # dusuk | orta | yuksek | engellendi
    reason: str
    matched_rule: str | None = None


class SandboxViolation(Exception):
    """Calisma alani disina cikma girisimi."""


# ---------------------------------------------------------------- yol hapsi
def workspace_root() -> Path:
    return settings.agent_workspace_path


# Ortam degiskeni / kullanici dizini genislemesi iceren yollar: kabuk bunlari
# calisma alani disina genisletebilecegi icin dogrudan reddedilir.
_EXPANDABLE_RE = re.compile(r"%[A-Za-z_][A-Za-z0-9_]*%|\$\{?[A-Za-z_]|^~")


def is_within_workspace(candidate: str | Path) -> bool:
    """Verilen yolun calisma alani icinde olup olmadigini soyler."""
    root = workspace_root()
    if _EXPANDABLE_RE.search(str(candidate)):
        # Genisletildiginde calisma alani disina cikabilir; guvenli tarafta kal.
        return False
    try:
        path = Path(candidate)
        if not path.is_absolute():
            path = root / path
        resolved = path.resolve(strict=False)
    except (OSError, ValueError, RuntimeError):
        return False

    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    return True


def safe_path(candidate: str | Path) -> Path:
    """Yolu calisma alanina gore cozer; disariysa `SandboxViolation` firlatir."""
    root = workspace_root()
    if _EXPANDABLE_RE.search(str(candidate)):
        raise SandboxViolation(
            f"Erişim reddedildi: '{candidate}' ortam değişkeni veya kullanıcı dizini "
            "genişlemesi içeriyor. AI terminali yalnızca açık, çalışma alanı içi "
            "yollarla çalışır."
        )
    path = Path(candidate)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SandboxViolation(
            f"Erişim reddedildi: '{candidate}' çalışma alanının ({root}) dışında. "
            "AI terminali yalnızca proje dizini içinde işlem yapabilir."
        ) from exc
    return resolved


def _looks_like_path(token: str) -> bool:
    if token.startswith("-"):
        return False
    return (
        "/" in token
        or "\\" in token
        or token.startswith("..")
        or (len(token) > 1 and token[1] == ":")
        or token.startswith("~")
    )


def check_paths(command: str) -> tuple[bool, str | None]:
    """Komuttaki yol benzeri tokenlarin calisma alani icinde oldugunu dogrular."""
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        return False, "Komut ayrıştırılamadı (tırnak dengesizliği)."

    for raw in tokens[1:]:
        token = raw.strip('"').strip("'")
        if not token or not _looks_like_path(token):
            continue
        # git referanslari (origin/main gibi) yol degildir
        if token.count("/") == 1 and not token.startswith((".", "/", "~")) and ":" not in token:
            continue
        if token.startswith(("~", "%")):
            return False, f"Kullanıcı dizini referansı engellendi: {token}"
        mutlak = PurePath(token).is_absolute() or (len(token) > 1 and token[1] == ":")
        if mutlak and not is_within_workspace(token):
            return False, f"Çalışma alanı dışında mutlak yol: {token}"
        if not mutlak and ".." in PurePath(token).parts and not is_within_workspace(token):
            return False, f"Üst dizine çıkma girişimi: {token}"
    return True, None


# ------------------------------------------------------------ komut denetimi
def check_command(command: str) -> CommandVerdict:
    """Tek bir komutu politikaya gore degerlendirir."""
    cmd = (command or "").strip()
    if not cmd:
        return CommandVerdict(command, False, "engellendi", "Boş komut.")

    if len(cmd) > 4000:
        return CommandVerdict(command, False, "engellendi", "Komut çok uzun (>4000 karakter).")

    if "\n" in cmd or "\r" in cmd:
        return CommandVerdict(
            command, False, "engellendi",
            "Çok satırlı komut kabul edilmiyor. Her komutu ayrı adım olarak girin.",
        )

    for meta in SHELL_METACHARACTERS:
        if meta in cmd:
            return CommandVerdict(
                command, False, "engellendi",
                f"Kabuk operatörü '{meta}' kullanılamaz. Komutları ayrı adımlara bölün "
                "(izin listesi atlatılamasın diye zincirleme engellidir).",
            )

    for pattern, label in BLOCKED_PATTERNS:
        if pattern.search(cmd):
            return CommandVerdict(
                command, False, "engellendi",
                f"Yasaklı işlem: {label}. Bu komut güvenlik politikası gereği çalıştırılamaz.",
                matched_rule=label,
            )

    try:
        tokens = shlex.split(cmd, posix=False)
    except ValueError:
        return CommandVerdict(
            command, False, "engellendi", "Komut ayrıştırılamadı (tırnak dengesizliği)."
        )
    if not tokens:
        return CommandVerdict(command, False, "engellendi", "Boş komut.")

    exe = PurePath(tokens[0].strip('"')).name.lower()
    if exe not in ALLOWED_EXECUTABLES:
        return CommandVerdict(
            command, False, "engellendi",
            f"'{exe}' izin listesinde değil. İzin verilen araçlar: "
            + ", ".join(sorted(ALLOWED_EXECUTABLES)),
            matched_rule="izin_listesi",
        )

    sub = tokens[1].lower().strip('"') if len(tokens) > 1 else ""

    # Satir ici kod, izin listesini ve yol hapsini birlikte atlatir.
    yasak_bayraklar = INLINE_CODE_FLAGS.get(exe)
    if yasak_bayraklar:
        for ham in tokens[1:]:
            bayrak = ham.strip('"').strip("'").lower()
            # `-cimport os` gibi bitisik yazimlar da yakalanmali
            if bayrak in yasak_bayraklar or any(
                bayrak.startswith(b) and b != "-" for b in yasak_bayraklar
            ):
                return CommandVerdict(
                    command, False, "engellendi",
                    f"'{exe} {bayrak}' engellendi: satır içi kod çalıştırma, izin "
                    "listesini ve çalışma alanı sınırını atlatabilir. Kodu çalışma "
                    "alanı içinde bir dosyaya yazıp o dosyayı çalıştırın; böylece "
                    "değişiklik diff ekranında incelenebilir.",
                    matched_rule="satir_ici_kod",
                )

    if exe == "git":
        if sub in GIT_BLOCKED_SUBCOMMANDS:
            return CommandVerdict(
                command, False, "engellendi",
                f"'git {sub}' engellendi. Uzak depo işlemleri ve temizleme komutları "
                "yalnızca kullanıcı tarafından el ile yapılır.",
                matched_rule=f"git:{sub}",
            )
        if sub and sub not in GIT_ALLOWED_SUBCOMMANDS:
            return CommandVerdict(
                command, False, "engellendi",
                f"'git {sub}' izin listesinde değil.", matched_rule=f"git:{sub}",
            )

    if exe in ("npm", "npx", "pip"):
        if sub in PACKAGE_BLOCKED_SUBCOMMANDS:
            return CommandVerdict(
                command, False, "engellendi",
                f"'{exe} {sub}' engellendi (paket yayınlama/oturum işlemleri).",
                matched_rule=f"{exe}:{sub}",
            )
        # ------------------------------------------------ paket kurulum kapisi
        # `npx` alt komut almadan da uzak paket indirip calistirabilir, bu
        # yuzden komutun kendisi kurulum sayilir.
        kurulum = exe == "npx" or sub in PACKAGE_INSTALL_SUBCOMMANDS
        if kurulum and not settings.AGENT_ALLOW_PACKAGE_INSTALL:
            return CommandVerdict(
                command, False, "engellendi",
                f"'{(exe + ' ' + sub).strip()}' engellendi: paket kurulumu, paketin kendi "
                "kurulum betigini calistirir ve bu betik izin listesinin de yol "
                "hapsinin de DISINDADIR. Bagimliligi el ile inceleyip kurun veya "
                "AGENT_ALLOW_PACKAGE_INSTALL=true ile bilincli olarak acin.",
                matched_rule=f"{exe}:paket_kurulumu",
            )
        if exe == "pip" and sub and sub not in PACKAGE_ALLOWED_SUBCOMMANDS | {
            "freeze", "uninstall", "check", "download"
        } | PACKAGE_INSTALL_SUBCOMMANDS:
            return CommandVerdict(
                command, False, "engellendi",
                f"'pip {sub}' izin listesinde değil.", matched_rule=f"pip:{sub}",
            )

    ok, path_reason = check_paths(cmd)
    if not ok:
        return CommandVerdict(
            command, False, "engellendi",
            f"{path_reason} AI terminali yalnızca {workspace_root()} içinde çalışır.",
            matched_rule="yol_hapsi",
        )

    for pattern, label in ELEVATED_RISK_PATTERNS:
        if pattern.search(cmd):
            return CommandVerdict(
                command, True, "yuksek", f"İzin verildi ancak dikkat: {label}.",
                matched_rule=label,
            )

    risk = "orta" if exe in ("python", "py", "npm", "npx", "node", "alembic", "uvicorn") else "dusuk"
    return CommandVerdict(command, True, risk, "Komut güvenlik politikasına uygun.")


def assess_plan(commands: list[str], paths: list[str]) -> tuple[str, list[str], list[CommandVerdict]]:
    """Bir gorev planinin genel risk seviyesini belirler."""
    verdicts = [check_command(c) for c in commands]
    reasons: list[str] = []

    blocked = [v for v in verdicts if not v.allowed]
    for v in blocked:
        reasons.append(f"ENGELLENDİ — {v.command[:80]}: {v.reason}")

    outside = [p for p in paths if not is_within_workspace(p)]
    for p in outside:
        reasons.append(f"ENGELLENDİ — Çalışma alanı dışı yol: {p}")

    if blocked or outside:
        return "engellendi", reasons, verdicts

    high = [v for v in verdicts if v.risk == "yuksek"]
    for v in high:
        reasons.append(f"Yüksek risk — {v.command[:80]}: {v.reason}")

    sensitive_paths = [
        p
        for p in paths
        if any(
            marker in p.lower()
            for marker in (".env", "alembic/versions", "core/security", "core/crypto",
                           "agent/sandbox", "core/permissions")
        )
    ]
    for p in sensitive_paths:
        reasons.append(f"Hassas dosya değişikliği: {p}")

    if high or sensitive_paths:
        return "yuksek", reasons, verdicts
    if any(v.risk == "orta" for v in verdicts) or len(paths) > 8:
        return "orta", reasons or ["Kod değişikliği içeriyor."], verdicts
    return "dusuk", reasons or ["Yıkıcı işlem tespit edilmedi."], verdicts


def sandbox_info() -> dict:
    return {
        "workspace": str(workspace_root()),
        "enabled": settings.AGENT_ENABLED,
        "require_approval": settings.AGENT_REQUIRE_APPROVAL,
        "timeout_seconds": settings.AGENT_COMMAND_TIMEOUT_SECONDS,
        "max_output_bytes": settings.AGENT_MAX_OUTPUT_BYTES,
        "allowed_commands": sorted(ALLOWED_EXECUTABLES),
        "blocked_patterns": [label for _, label in BLOCKED_PATTERNS],
        "package_install_allowed": settings.AGENT_ALLOW_PACKAGE_INSTALL,
        # Kalan varsayim ACIKCA belirtilir: bu bir inceleme kapisidir,
        # bir kapsama (containment) sinirı degildir.
        "containment": (
            "Bu bir INCELEME KAPISIDIR, kapsama (containment) sinirı degildir. "
            "Calisma alani icinde yazilip calistirilan bir betik, isletim "
            "sistemi duzeyinde SIRADAN bir kullanici sureci olarak calisir: "
            "ag erisimi ve proje disi okuma yetkisi vardir. Guvenlik, "
            "degisikligin diff ekraninda BIR INSAN tarafindan incelenmesine "
            "dayanir."
        ),
    }
