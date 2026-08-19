# Katkıda bulunma — Contributing

## Katkı lisansı — Contribution licence

Proje MIT Lisansı ile dağıtılır. Bir katkı göndererek katkınızın aynı koşullarla
dağıtılmasını kabul etmiş olursunuz. Yalnızca gönderme hakkına sahip olduğunuz
çalışmaları ekleyin; gizli bilgi veya MIT ile uyumsuz üçüncü taraf kodu eklemeyin.

This project is distributed under the MIT License. By submitting a contribution,
you agree that it may be distributed under the same terms. Submit only work you
have the right to contribute, without secrets or incompatible third-party code.

## Şu anda yapabilecekleriniz

**Hata bildirimi ve fikir**, issue olarak memnuniyetle karşılanır. Yararlı bir
hata bildirimi şunları içerir:

- ne yapmaya çalıştığınız, ne olmasını beklediğiniz, ne olduğu,
- işletim sistemi, Python ve Node.js sürümleri,
- ilgili günlük çıktısı — **gizli değerleri temizleyerek**,
- mümkünse en küçük yeniden üretim adımları.

**Güvenlik açıklarını issue olarak açmayın.** Bkz. [SECURITY.md](SECURITY.md).

## Kod okuyorsanız — yerel kalite kapıları

Katkı kabul edilmese de, kodu kendi kopyanızda değerlendiriyorsanız aynı
kapıları çalıştırabilirsiniz:

```powershell
# Backend: lint + tip + testler
powershell -ExecutionPolicy Bypass -File scripts\testler.ps1

# Yalnızca pytest
python -m pytest

# Frontend: tip denetimi + üretim derlemesi
cd frontend
npm ci
npm run lint
npm run build
```

Bu depoda geçerli beklentiler:

- **Ruff** temiz geçmelidir (kod kalitesi + bandit güvenlik kuralları).
- Yeni davranışın **testi olmalıdır**. Bir testi geçirmek için testi zayıflatmak
  kabul edilmez; kodu düzeltin.
- Güvenlik sınırlarına (`backend/app/agent/sandbox.py`,
  `backend/app/core/deps.py`, `backend/app/core/security.py`,
  `backend/app/api/v1/auth.py`) dokunan değişiklikler ayrıca gerekçelendirilmelidir.
- Kod ve yorumlar **Türkçe**dir; mevcut adlandırma düzenini izleyin.
- Arayüz metinleri hem `tr.ts` hem `en.ts` içine eklenmelidir;
  `tests/test_ceviri_butunlugu.py` iki sözlüğün eşitliğini doğrular.
