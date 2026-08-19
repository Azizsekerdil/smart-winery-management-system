# Üçüncü taraf bileşenler — Third-party notices

Bu dosya **makine tarafından** üretilmiştir: kaynağı bu depodaki
[`sbom.cdx.json`](sbom.cdx.json) (CycloneDX) ve
[`sbom.spdx.json`](sbom.spdx.json) (SPDX) dosyalarıdır. Bu iki SBOM,
[Syft](https://github.com/anchore/syft) ile doğrudan kaynak ağacından
üretilmiştir.

Lisans **gerekçeleri** ve seçim kararları ayrı bir belgededir:
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

> Aşağıdaki lisans alanları SBOM'da bildirilen değerlerdir. Bir bileşenin
> lisansı boşsa, bu "lisansı yok" demek değildir — yalnızca SBOM üreticisi
> paket meta verisinden okuyamamıştır. Hukuki bir değerlendirme için paketin
> kendi lisans metnine bakın.

## Özet

| Ekosistem | Bileşen sayısı |
|---|---|
| Python (PyPI) | 25 |
| JavaScript (npm) | 49 |
| Diğer | 5 |
| **Toplam** | **79** |

Bilinen lisans dağılımı:

| Lisans | Adet |
|---|---|
| MIT | 43 |
| (SBOM'da belirtilmemis) | 31 |
| ISC | 2 |
| Apache-2.0 | 1 |
| 0BSD | 1 |
| BSD-3-Clause | 1 |

**GPL / AGPL / LGPL lisanslı bileşen yoktur.** Bu, kapalı kaynak ticari
dağıtımın mümkün kalması için bilinçli bir tasarım kısıtıdır; ayrıntı ve
gerekçeler (ör. `psycopg` yerine `asyncpg`) THIRD_PARTY_LICENSES.md içindedir.

## Python (PyPI) — 25 bileşen

| Paket | Sürüm | Lisans (SBOM) |
|---|---|---|
| `aiosqlite` | 0.22.1 | (SBOM'da belirtilmemis) |
| `alembic` | 1.19.1 | (SBOM'da belirtilmemis) |
| `argon2-cffi` | 25.1.0 | (SBOM'da belirtilmemis) |
| `asyncpg` | 0.31.0 | (SBOM'da belirtilmemis) |
| `cryptography` | 50.0.0 | (SBOM'da belirtilmemis) |
| `email-validator` | 2.3.0 | (SBOM'da belirtilmemis) |
| `fastapi` | 0.141.1 | (SBOM'da belirtilmemis) |
| `greenlet` | 3.5.5 | (SBOM'da belirtilmemis) |
| `httpx` | 0.28.1 | (SBOM'da belirtilmemis) |
| `mypy` | 2.3.0 | (SBOM'da belirtilmemis) |
| `openpyxl` | 3.1.5 | (SBOM'da belirtilmemis) |
| `pillow` | 12.3.0 | (SBOM'da belirtilmemis) |
| `pydantic` | 2.13.4 | (SBOM'da belirtilmemis) |
| `pydantic-settings` | 2.15.0 | (SBOM'da belirtilmemis) |
| `pyjwt` | 2.13.0 | (SBOM'da belirtilmemis) |
| `pytest` | 9.1.1 | (SBOM'da belirtilmemis) |
| `pytest-asyncio` | 1.4.0 | (SBOM'da belirtilmemis) |
| `pytest-cov` | 7.1.0 | (SBOM'da belirtilmemis) |
| `python-multipart` | 0.0.32 | (SBOM'da belirtilmemis) |
| `qrcode` | 8.2 | (SBOM'da belirtilmemis) |
| `reportlab` | 5.0.0 | (SBOM'da belirtilmemis) |
| `ruff` | 0.16.3 | (SBOM'da belirtilmemis) |
| `sqlalchemy` | 2.0.52 | (SBOM'da belirtilmemis) |
| `structlog` | 26.1.0 | (SBOM'da belirtilmemis) |
| `uvicorn` | 0.52.3 | (SBOM'da belirtilmemis) |

## JavaScript (npm) — 49 bileşen

| Paket | Sürüm | Lisans (SBOM) |
|---|---|---|
| `@tanstack/query-core` | 5.101.4 | MIT |
| `@tanstack/react-query` | 5.101.4 | MIT |
| `@types/react` | 19.2.18 | MIT |
| `agent-base` | 6.0.2 | MIT |
| `asynckit` | 0.4.0 | MIT |
| `axios` | 1.19.0 | MIT |
| `call-bind-apply-helpers` | 1.0.2 | MIT |
| `clsx` | 2.1.1 | MIT |
| `combined-stream` | 1.0.8 | MIT |
| `cookie` | 1.1.1 | MIT |
| `csstype` | 3.2.3 | MIT |
| `date-fns` | 4.4.0 | MIT |
| `debug` | 4.4.3 | MIT |
| `delayed-stream` | 1.0.0 | MIT |
| `dunder-proto` | 1.0.1 | MIT |
| `echarts` | 6.1.0 | Apache-2.0 |
| `echarts-for-react` | 3.0.6 | MIT |
| `es-define-property` | 1.0.1 | MIT |
| `es-errors` | 1.3.0 | MIT |
| `es-object-atoms` | 1.1.2 | MIT |
| `es-set-tostringtag` | 2.1.0 | MIT |
| `fast-deep-equal` | 3.1.3 | MIT |
| `follow-redirects` | 1.16.0 | MIT |
| `form-data` | 4.0.6 | MIT |
| `frontend` | 0.0.0 | (SBOM'da belirtilmemis) |
| `function-bind` | 1.1.2 | MIT |
| `get-intrinsic` | 1.3.0 | MIT |
| `get-proto` | 1.0.1 | MIT |
| `gopd` | 1.2.0 | MIT |
| `has-symbols` | 1.1.0 | MIT |
| `has-tostringtag` | 1.0.2 | MIT |
| `hasown` | 2.0.4 | MIT |
| `https-proxy-agent` | 5.0.1 | MIT |
| `lucide-react` | 1.31.0 | ISC |
| `math-intrinsics` | 1.1.0 | MIT |
| `mime-db` | 1.52.0 | MIT |
| `mime-types` | 2.1.35 | MIT |
| `ms` | 2.1.3 | MIT |
| `proxy-from-env` | 2.1.0 | MIT |
| `react` | 19.2.8 | MIT |
| `react-dom` | 19.2.8 | MIT |
| `react-router` | 7.18.2 | MIT |
| `react-router-dom` | 7.18.2 | MIT |
| `scheduler` | 0.27.0 | MIT |
| `set-cookie-parser` | 2.7.2 | MIT |
| `size-sensor` | 1.0.3 | ISC |
| `tslib` | 2.3.0 | 0BSD |
| `zrender` | 6.1.0 | BSD-3-Clause |
| `zustand` | 5.0.15 | MIT |

## Diğer — 5 bileşen

| Paket | Sürüm | Lisans (SBOM) |
|---|---|---|
| `actions/checkout` | v4 | (SBOM'da belirtilmemis) |
| `actions/setup-node` | v4 | (SBOM'da belirtilmemis) |
| `actions/setup-python` | v5 | (SBOM'da belirtilmemis) |
| `actions/upload-artifact` | v4 | (SBOM'da belirtilmemis) |
| `gitleaks/gitleaks-action` | v2 | (SBOM'da belirtilmemis) |

## Yazı tipleri ve görseller

- Arayüz, kullanıcının işletim sistemindeki **sistem yazı tipi yığınını**
  kullanır; depoda gömülü ticari yazı tipi **yoktur**.
- Simgeler: [Lucide](https://lucide.dev) (ISC lisansı), `lucide-react` paketi
  üzerinden.
- Grafikler: [Apache ECharts](https://echarts.apache.org) (Apache-2.0).
- `docs/screenshots/` altındaki görüntüler bu projeye aittir ve **yalnızca
  kurgusal demo verisi** içerir.
