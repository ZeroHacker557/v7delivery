# Ishga tushirish qo'llanmasi

3-blokdagi xavfsizlik o'zgarishlaridan keyin loyiha uchta qismdan iborat:

| Qism | Qayerda ishlaydi | Vazifasi |
|---|---|---|
| Mini app | Vercel (statik) | Katalog, savat, buyurtma formasi |
| `/api/*` | Vercel (serverless) | Telegram imzosini tekshirish, buyurtma yaratish, promokod |
| Bot | Sizning kompyuteringiz | Admin panel, buyurtma xabarnomalari, to'lov cheklari |

---

## 0. V7 ga o'tish — almashtiriladigan qiymatlar

Loyiha V7™ brendiga moslandi. Yangi Firebase loyihasi, yangi bot va yangi
domen ulanganda **faqat quyidagi joylar** o'zgaradi:

| Nima | Qayerga |
|---|---|
| **Bot tokeni** | `bot/.env` (git'ga tushmaydi) **va** Vercel env `BOT_TOKEN` |
| Firebase service account JSON | Loyiha ildiziga fayl (git'ga tushmaydi) + Vercel env `FIREBASE_SERVICE_ACCOUNT` |
| Service account fayl nomi va bucket | `bot/config.py` → `FIREBASE_KEY_FILE`, `FIREBASE_STORAGE_BUCKET` |
| Firebase web config | `src/config/firebase.ts` |
| Bot username | `bot/config.py` → `BOT_USERNAME`, `src/config/brand.ts` → `botUsername` |
| Mini app domeni | `bot/config.py` → `MINI_APP_URL` + BotFather `/setdomain` |
| Admin Telegram ID | `bot/config.py` → `ADMIN_IDS` |
| Aloqa raqami / email / Telegram | `src/config/brand.ts` va `bot/config.py` |
| Dasturchi kontaktlari | `src/config/brand.ts` → `DEVELOPER` |
| To'lov kartasi | `bot/config.py` → `CARD_NUMBER`, `CARD_OWNER` (keyin Firestore `settings/payment`) |

> **Bot tokeni hech qachon git'ga tushmaydi.** U `bot/.env` da, `.gitignore`
> esa uni to'sadi. `bot/config.py` faqat `os.environ` dan o'qiydi. Yangi
> muhitda ishga tushirishdan oldin:
>
> ```
> cp bot/.env.example bot/.env
> ```
>
> va tokenni yozing. Token bo'lmasa bot tushunarli xabar bilan to'xtaydi.

> Firebase web config (`apiKey` va h.k.) maxfiy emas — Firebase uni brauzerga
> ataylab ochiq beradi, himoya Firestore Rules tomonida. Shuning uchun u env
> o'zgaruvchi emas, oddiy fayl.

> ⚠️ `src/config/firebase.ts` dagi `projectId` bot ishlatadigan service
> account bilan **bir xil loyihaga** tegishli bo'lishi shart. Aks holda bot
> bir bazaga yozadi, ilova boshqasidan o'qiydi — katalog bo'sh ko'rinadi.

Brend ranglari va shriftlari `src/styles.css` dagi CSS tokenlarida —
komponentlarda hex yozilmagan, shuning uchun rang o'zgartirish bitta joyda.

## 1. Bot tokeni

Token `bot/.env` da saqlanadi va git'ga tushmaydi. Uni almashtirish kerak
bo'lsa:

1. Telegram'da [@BotFather](https://t.me/BotFather) ni oching
2. `/mybots` → botni tanlang → **API Token**
3. Yangi tokenni `bot/.env` ga va Vercel env `BOT_TOKEN` ga yozing —
   **ikkalasi bir xil bo'lishi shart**

`initData` imzosi aynan shu token bilan tekshiriladi: token va Vercel'dagi
qiymat mos kelmasa, mini app "Tizimga kirilmagan" xatosini beradi.

> ⚠️ Eski `ecommercy_test_bot` tokeni git tarixida ochiq qolgan. O'sha bot
> endi ishlatilmasa ham, @BotFather → **Revoke current token** bilan uni
> bekor qilib qo'ying — aks holda tokenni topgan odam o'sha bot nomidan
> ish yurita oladi.

---

## 2. Vercel Environment Variables

Vercel loyihasi → **Settings** → **Environment Variables**. Ikkalasini ham
Production, Preview va Development uchun qo'shing.

### `BOT_TOKEN`
Yuqorida olingan yangi token.

### `FIREBASE_SERVICE_ACCOUNT`
Firebase Console → ⚙️ **Project Settings** → **Service accounts** →
**Generate new private key**. Yuklab olingan JSON faylni matn muharririda
oching va **butun mazmunini** (`{` dan `}` gacha) qiymat sifatida joylang.

> Bu kalit loyihadagi `ecommercytest-firebase-adminsdk-*.json` fayl bilan
> bir xil. U `.gitignore` da — git'ga tushmaydi va tushmasligi kerak.

Env o'zgaruvchilarni qo'shgandan keyin **qaytadan deploy qiling** —
Vercel ularni faqat yangi build'ga qo'llaydi.

---

## 3. Firebase Authentication'ni yoqing

Firebase Console → **Authentication** → **Get started**.

Custom token bilan kirish uchun alohida provider yoqish shart emas, lekin
Authentication bo'limi bir marta ishga tushirilgan bo'lishi kerak.

---

## 4. Firestore Rules'ni yangilang

Loyiha ildizidagi [`firestore.rules`](./firestore.rules) faylini oching va
mazmunini Firebase Console → **Firestore Database** → **Rules** ga nusxalab,
**Publish** bosing.

Yoki Firebase CLI bilan:

```bash
firebase deploy --only firestore:rules
```

Qoidalar nima qiladi:

- **products, categories** — hamma o'qiydi, hech kim yozmaydi (faqat bot)
- **orders** — foydalanuvchi faqat o'zinikini o'qiydi, yozish butunlay yopiq
  (buyurtmani `/api/orders` yaratadi)
- **users** — faqat o'z hujjati, faqat `first_name`, `last_name`, `phone`,
  `addresses` maydonlari
- **promocodes** — mijoz umuman ko'ra olmaydi
- **counters** — faqat server

> ⚠️ Rules'ni yangilashdan **oldin** yangi kodni deploy qiling. Aks holda
> eski mini app buyurtma yarata olmay qoladi (u to'g'ridan-to'g'ri yozardi).

---

## 5. To'g'ri tartib

```
1. Yangi kodni Vercel'ga deploy qiling (env o'zgaruvchilar bilan)
2. Mini appni ochib, buyurtma berib ko'ring — ishlashi kerak
3. Shundan keyin Firestore Rules'ni yangilang
4. Yana bir buyurtma berib tekshiring
5. bot/.env dagi tokenni tekshiring va botni qayta ishga tushiring
```

---

## 6. Tekshirish ro'yxati

- [ ] Mini app Telegram'da ochiladi, katalog ko'rinadi
- [ ] Brauzerda ochilsa "Telegram'da ochish" ekrani chiqadi
- [ ] Buyurtma berilganda adminga xabar keladi, raqami `#1001` ko'rinishida
- [ ] "Buyurtmalarim" bo'limida buyurtma ko'rinadi
- [ ] Promokod qo'llanganda chegirma to'g'ri hisoblanadi
- [ ] Bot o'chirilgan holda buyurtma berilsa, bot yoqilganda xabar keladi
- [ ] Karta bilan to'lovda chek yuborish oqimi ishlaydi

### Xatolarni qayerdan ko'rish

- **Mini app:** Telegram Desktop → mini app ustida o'ng tugma → Inspect
- **API:** Vercel → loyiha → **Logs** (`[auth]`, `[orders]`, `[promo]` teglari)
- **Bot:** terminal oynasidagi log

---

## Ma'lum cheklovlar

- **Bot shaxsiy kompyuterda ishlaydi** — kompyuter o'chsa, admin xabarnomalari
  kechikadi. Buyurtmalar yo'qolmaydi (`notified` bayrog'i tufayli), lekin
  admin ularni faqat bot yoqilganda ko'radi. Doimiy ishlashi kerak bo'lsa,
  botni VPS yoki Railway'ga ko'chirish kerak.
- **Bot lokal ishlaydi** — hozircha VPS'ga ko'chirilmagan. Ko'chirilganda
  `bot/.env` faylini ham birga olib o'tish kerak (u git'da yo'q).
