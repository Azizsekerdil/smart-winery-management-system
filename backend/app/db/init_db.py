"""Veritabanini olustur ve demo verisini yukle (komut satiri)."""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.logging import configure_logging, get_logger
from app.db.base import Base
from app.db.session import SessionLocal, dispose_engine, engine
from app.models import *

log = get_logger("init_db")


async def create_tables(drop: bool = False) -> None:
    async with engine.begin() as conn:
        if drop:
            await conn.run_sync(Base.metadata.drop_all)
            log.warning("tablolar_silindi")
        await conn.run_sync(Base.metadata.create_all)
    log.info("tablolar_hazir", tablo_sayisi=len(Base.metadata.tables))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Şaraphane veritabanı kurulumu")
    parser.add_argument("--seed", action="store_true", help="Demo verisini yükle")
    parser.add_argument(
        "--force", action="store_true", help="Demo verisi zaten varsa yine de yükle"
    )
    parser.add_argument(
        "--drop", action="store_true", help="TÜM tabloları sil ve yeniden oluştur"
    )
    parser.add_argument(
        "--yes", action="store_true", help="--drop için onay sorusunu atla (betikler için)"
    )
    return parser.parse_args()


def confirm_drop(args: argparse.Namespace) -> bool:
    """Yıkıcı işlem onayı. Asenkron bağlamda `input()` çağrılmaz (bloklar)."""
    if not args.drop or args.yes:
        return True
    answer = input(
        "DİKKAT: Tüm tablolar silinecek ve veriler kaybolacak. "
        "Devam etmek için 'EVET' yazın: "
    )
    return answer.strip() == "EVET"


async def main(args: argparse.Namespace) -> int:
    configure_logging()
    await create_tables(drop=args.drop)

    if args.seed:
        from app.db.seed import DEMO_PASSWORD, seed_all

        async with SessionLocal() as session:
            stats = await seed_all(session, force=args.force or args.drop)
        if stats.get("atlandi"):
            print("Demo verisi zaten yüklü. Yeniden yüklemek için --force kullanın.")
        else:
            print("\nDemo verisi yüklendi:")
            for k, v in sorted(stats.items()):
                print(f"  {k:16s}: {v}")
            print(
                "\nDemo giriş bilgileri (YALNIZCA GELİŞTİRME İÇİN):\n"
                f"  Kullanıcılar : admin, mudur, enolog, bagci, lab, mahzen,\n"
                f"                 operator, siseleme, depo, satis, muhasebe, denetci\n"
                f"  Parola       : {DEMO_PASSWORD}\n"
                "  İlk girişte parola değiştirmeniz istenecektir.\n"
                "  ÜRETİM ORTAMINDA BU KULLANICILARI SİLİN veya parolalarını değiştirin."
            )

    await dispose_engine()
    return 0


if __name__ == "__main__":
    _args = parse_args()
    if not confirm_drop(_args):
        print("İşlem iptal edildi.")
        sys.exit(1)
    sys.exit(asyncio.run(main(_args)))
