# ═══════════════════════════════════════════════════════════
# V7 Shop — bot sozlamalari
#
# Yangi bot tokeni / domen kelganda faqat shu blok o'zgaradi.
# Frontend tomonidagi mos fayl: src/config/brand.ts
# ═══════════════════════════════════════════════════════════

# ── Telegram ──
BOT_TOKEN    = "8943083942:AAF5JH5QOBUnln8v489MrXkiFiezKAXUlrI"
BOT_USERNAME = "ecommercy_test_bot"
ADMIN_IDS    = {7203124812}   # Barcha adminlar
MINI_APP_URL = "https://ecommercy.vercel.app"

# ── Kompaniya aloqa ma'lumotlari (bot javoblarida ko'rinadi) ──
COMPANY_NAME     = "V7"
COMPANY_TAGLINE  = "Vitamin Sparkling Drink"
SUPPORT_PHONE    = "+998 78 777 07 07"
SUPPORT_EMAIL    = "info@v7.uz"
SUPPORT_TELEGRAM = "@v7uz"
COMPANY_CITY     = "Toshkent, O'zbekiston"
WORK_HOURS       = "09:00 — 20:00"

# ── Firebase ──
# Service account JSON fayli (loyiha ildizida yoki bot/ papkasida).
# Firebase Console → Project Settings → Service accounts →
# "Generate new private key".
FIREBASE_KEY_FILE       = "ecommercytest-firebase-adminsdk-fbsvc-645304f3a0.json"
# Storage bucket — mahsulot rasmlari shu yerga yuklanadi.
# Console → Storage → bucket nomi (odatda <project-id>.firebasestorage.app).
FIREBASE_STORAGE_BUCKET = "ecommercytest.firebasestorage.app"

# ── Server ──
API_HOST     = "0.0.0.0"
API_PORT     = 8080
IMAGES_DIR   = "images"
DB_FILE      = "database.json"

# To'lov sozlamalari — faqat BOSHLANG'ICH qiymat.
# Bot birinchi ishga tushganda bular Firestore'dagi settings/payment
# hujjatiga ko'chiriladi. Undan keyin haqiqiy manba — o'sha hujjat (F-07).
CARD_NUMBER = "5614 6818 1872 7921"
CARD_OWNER  = "Abubakir Abdulbositov"
