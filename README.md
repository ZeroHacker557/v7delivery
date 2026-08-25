# V7™ Shop — Telegram Mini App

V7 (Vitamin Sparkling Drink) ichimliklari uchun Telegram mini app do'koni:
React + TypeScript + Tailwind CSS frontend, Vercel serverless API va aiogram
asosidagi Telegram bot.

## Brend

| Element | Qiymat |
| --- | --- |
| Asosiy rang | `#008743` (logo yashili) |
| Aksent | `#C79A32` / `#E3B341` (V7 oltini) |
| Shriftlar | Archivo Black (sarlavha), Montserrat (matn) |
| Logotip | `src/images/v7-mark.png`, `v7-mark-white.png`, `v7-logo-full.webp` |
| Hero rasm | `src/images/hero-can.webp` (Lemon Mint — Immune Support) |

Kompaniya ma'lumotlari (telefon, email, Telegram, bot username) bitta joyda:
[`src/config/brand.ts`](src/config/brand.ts). Bot tomonida — `bot/config.py`.

Ranglar `src/styles.css` dagi CSS o'zgaruvchilarida. Komponentlarda hex
yozilmaydi — faqat `var(--brand)` kabi tokenlar, shu tufayli qorong'i rejim
bitta blokda hal bo'ladi.

## Tuzilma

- `src/pages` — ekranlar: bosh sahifa, katalog, profil, buyurtmalar, mahsulot detali.
- `src/components/brand` — logotip komponenti.
- `src/components` — qayta ishlatiluvchi layout, UI, mahsulot va buyurtma komponentlari.
- `src/config/brand.ts` — brend va aloqa konstantalari.
- `src/hooks` — ilovaning UI holati va biznes harakatlari.
- `src/i18n` — o'zbekcha (asosiy) va ruscha lug'atlar.
- `src/types` — markazlashtirilgan TypeScript domen turlari.
- `api/` — Vercel serverless funksiyalari (auth, orders, reviews, promo).
- `bot/` — aiogram bot va admin panel.
- `public/images/flavors` — 9 ta ta'm bankasining rasmlari (mahsulot qo'shishda).

## Buyruqlar

```bash
npm install
```

```bash
npm run dev
```

```bash
npm run build
```

```bash
npm run lint
```

Mahsulotlar bazadan (Firestore) keladi va bot admin paneli orqali qo'shiladi —
`src/data.ts` bo'sh ro'yxat qaytaradi.
