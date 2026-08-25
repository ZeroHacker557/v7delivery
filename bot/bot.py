"""
V7 Shop Telegram Bot — Admin panel + Mini App + To'lov tizimi

V7 (Vitamin Sparkling Drink) ichimliklari do'koni.
"""
import asyncio
import json
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, WebAppInfo, InlineKeyboardButton,
    InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton,
    MenuButtonWebApp, CallbackQuery
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties

# Karta ma'lumoti config.py dan emas, settings/payment hujjatidan olinadi (F-07)
from config import (
    BOT_TOKEN, MINI_APP_URL,
    SUPPORT_PHONE, SUPPORT_EMAIL, SUPPORT_TELEGRAM, COMPANY_CITY, WORK_HOURS,
)
# Adminlar ro'yxati dinamik — panel orqali qo'shiladi/o'chiriladi
from admins import all_admins, is_admin
from admin import router as admin_router
import firebase_db as db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Token bot/.env dan keladi. Bo'lmasa aiogram tushunarsiz xato beradi —
# shuning uchun oldindan aniq xabar bilan to'xtatamiz.
if not BOT_TOKEN:
    raise SystemExit(
        "BOT_TOKEN topilmadi.\n"
        "bot/.env faylini yarating va tokenni yozing:\n"
        "    cp bot/.env.example bot/.env\n"
        "Token @BotFather dan olinadi."
    )

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp  = Dispatcher(storage=MemoryStorage())
dp.include_router(admin_router)


# ─── FSM ─────────────────────────────────────────────────────

class PaymentUpload(StatesGroup):
    waiting_photo = State()


# ─── Status emoji map ─────────────────────────────────────────

STATUS_EMOJI = {
    "Qabul qilindi":  "🟢",
    "Yetkazilmoqda":  "🚚",
    "Yetkazildi":     "🎉",
    "Rad etildi":     "🔴",
    "Bekor qilingan": "🔴",
}


# ─── Klaviaturalar ────────────────────────────────────────────

def main_kb(admin: bool = False):
    rows = [
        # Oddiy tugma — bosilganda pastdagi menyu tugmasiga yo'naltiradi.
        # Mini app faqat yozuv maydoni yonidagi "🛍 Katalog" orqali ochiladi.
        [KeyboardButton(text="🥤 Katalogni ochish")],
        [KeyboardButton(text="📦 Buyurtmalarim")],
        [KeyboardButton(text="📞 Biz bilan aloqa"), KeyboardButton(text="ℹ️ Yordam")]
    ]
    if admin:
        rows.append([KeyboardButton(text="🛠 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def contact_kb() -> ReplyKeyboardMarkup:
    """Telefon raqamini bir bosishda olish uchun (F-26)."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def location_button(order_id: str) -> InlineKeyboardButton:
    """
    Bosilganda mijoz manzilini HAQIQIY Telegram lokatsiyasi sifatida
    yuboradi (havola emas). Uni kuryerga oddiy forward qilish mumkin.
    """
    return InlineKeyboardButton(
        text="📍 Lokatsiyani olish",
        callback_data=f"loc:{order_id}",
    )


def order_action_kb(order_id: str, has_location: bool = False) -> InlineKeyboardMarkup:
    """Admin uchun status tugmalari (+ lokatsiya, agar bo'lsa)"""
    rows = [
        [
            InlineKeyboardButton(text="✅ Qabul",     callback_data=f"os:Qabul qilindi:{order_id}"),
            InlineKeyboardButton(text="🚚 Yetkazish", callback_data=f"os:Yetkazilmoqda:{order_id}")
        ],
        [
            InlineKeyboardButton(text="🎉 Bajarildi", callback_data=f"os:Yetkazildi:{order_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"os:Rad etildi:{order_id}")
        ],
    ]
    if has_location:
        rows.append([location_button(order_id)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_has_location(order: dict | None) -> bool:
    loc = (order or {}).get("customer", {}).get("location") or {}
    return isinstance(loc, dict) and loc.get("lat") is not None and loc.get("lng") is not None


def receipt_kb(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To'lov chekini yuborish", callback_data=f"receipt:{order_id}")]
    ])


def resend_receipt_kb(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Qayta chek yuborish", callback_data=f"receipt:{order_id}")]
    ])


def payment_confirm_kb(order_id: str, user_id: int, has_location: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"pconf:ok:{order_id}:{user_id}"),
            InlineKeyboardButton(text="❌ Rad etish",  callback_data=f"pconf:no:{order_id}:{user_id}")
        ],
    ]
    if has_location:
        rows.append([location_button(order_id)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def mini_app_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Buyurtmalarimni ko'rish", web_app=WebAppInfo(url=MINI_APP_URL))]
    ])


# ─── Yordamchi funksiyalar ────────────────────────────────────

def get_display_name(order_data: dict) -> str:
    raw = order_data.get("username", "")
    if raw and " " not in raw.strip():
        return f"@{raw}"
    return raw or order_data.get("customer", {}).get("name", "—")


def get_products_text(products: list) -> str:
    lines = ""
    for i, p in enumerate(products, 1):
        qty      = p.get("quantity", 1)
        size     = p.get("size")
        color    = p.get("color")
        prod     = p.get("product") or p
        name     = prod.get("name", "—")
        price    = prod.get("price", 0)
        item_sum = db.format_price(price * qty)
        
        variant_info = []
        if size: variant_info.append(f"Hajm: {size}")
        if color: variant_info.append(f"Ta'm: {color}")
        var_text = f" ({', '.join(variant_info)})" if variant_info else ""
        
        lines += f"  <b>{i}. {name}</b>{var_text}\n"
        lines += f"     └ {qty} ta × {db.format_price(price)} = <b>{item_sum}</b>\n"
    return lines


# Telegram rasm izohi (caption) uchun chegara
CAPTION_LIMIT = 1024


def current_caption(msg) -> str:
    """Rasmli xabarning HTML izohi (formatlash saqlanadi)."""
    try:
        return msg.html_text or ""
    except Exception:
        return msg.caption or ""


def build_receipt_caption(order: dict | None, display_id: str) -> str:
    """
    Adminga yuboriladigan chek izohi: mijoz ma'lumotlari, mahsulotlar
    (rang va o'lcham bilan) hamda to'liq hisob-kitob.

    Telegram izohni 1024 belgi bilan cheklaydi — sig'masa mahsulotlar
    ro'yxati qisqartiriladi, mijoz ma'lumotlari esa doim to'liq qoladi.
    """
    head = "💳 <b>TO'LOV CHEKI</b>\n" + "━" * 22 + "\n\n"
    head += f"🧾 <b>Buyurtma:</b> {display_id}\n"

    if not order:
        return head + "\n⚠️ Buyurtma ma'lumotlari topilmadi."

    customer = order.get("customer", {})
    head += f"📅 {db.order_date_text(order)}\n\n"
    head += f"👤 <b>Ism:</b> {customer.get('name', '—')}\n"
    head += f"📱 <b>Telegram:</b> {get_display_name(order)}\n"
    head += f"📞 <b>Tel:</b> <code>{customer.get('phone', '—')}</code>\n"
    head += f"📍 <b>Manzil:</b> {customer.get('address', '—')}\n"
    if customer.get("comment"):
        head += f"💬 <b>Izoh:</b> {customer['comment']}\n"

    # ── Hisob-kitob ──
    tail = "\n" + "━" * 22 + "\n"
    subtotal = order.get("subtotal")
    discount = order.get("discount") or 0
    delivery_fee = order.get("deliveryFee") or 0
    if isinstance(subtotal, (int, float)) and (discount or delivery_fee):
        tail += f"🧾 Mahsulotlar: {db.format_price(subtotal)}\n"
        if discount:
            promo = order.get("promoCode")
            promo_text = f" ({promo})" if promo else ""
            tail += f"🏷 Chegirma{promo_text}: -{db.format_price(discount)}\n"
        if delivery_fee:
            tail += f"🚚 Yetkazish: {db.format_price(delivery_fee)}\n"
        else:
            tail += "🚚 Yetkazish: bepul\n"

    total = order.get("total", 0)
    total_str = db.format_price(total) if isinstance(total, (int, float)) else str(total)
    tail += f"💰 <b>To'langan summa: {total_str}</b>"

    # ── Mahsulotlar ──
    products = order.get("products", [])
    lines = []
    for i, item in enumerate(products, 1):
        qty = item.get("quantity", 1)
        prod = item.get("product") or item
        name = prod.get("name", "—")
        price = prod.get("price", 0)

        variant = []
        if item.get("size"):
            variant.append(f"Hajm: {item['size']}")
        if item.get("color"):
            variant.append(f"Ta'm: {item['color']}")
        var_text = f" ({', '.join(variant)})" if variant else ""

        lines.append(
            f"  <b>{i}. {name}</b>{var_text}\n"
            f"     └ {qty} ta × {db.format_price(price)} = <b>{db.format_price(price * qty)}</b>\n"
        )

    body_header = "\n📦 <b>Mahsulotlar:</b>\n"
    shown = list(lines)
    while shown:
        hidden = len(lines) - len(shown)
        more = f"  <i>...va yana {hidden} ta mahsulot</i>\n" if hidden else ""
        caption = head + body_header + "".join(shown) + more + tail
        if len(caption) <= CAPTION_LIMIT:
            return caption
        shown.pop()

    return head + body_header + f"  <i>{len(lines)} ta mahsulot</i>\n" + tail


# ─── Yangi buyurtma: Admin + User bildirishnomasi ─────────────

async def notify_admin_order(order_data: dict):
    try:
        customer   = order_data.get("customer", {})
        products   = order_data.get("products", [])
        total      = order_data.get("total", 0)
        # Tugmalar uchun — Firestore hujjat id'si; matn uchun — ko'rsatish raqami (F-03)
        doc_id     = order_data.get("_doc_id") or order_data.get("id", "")
        order_id   = db.order_display_id(order_data)
        pay_method = order_data.get("paymentMethod", "Naqd")
        user_id    = order_data.get("userId")
        total_str  = db.format_price(total) if isinstance(total, (int, float)) else str(total)
        tg_name    = get_display_name(order_data)
        has_location = order_has_location(order_data)
        pay_label  = "💵 Naqd (yetkazganda)" if pay_method == "Naqd" else "💳 Karta o'tkazmasi"

        # ── ADMIN XABARI ──────────────────────────────────────
        text  = f"🛒 <b>YANGI BUYURTMA ({order_id})</b>\n"
        text += "━" * 22 + "\n\n"
        text += f"📱 <b>Telegram:</b> {tg_name}\n"
        text += f"👤 <b>Ism:</b> {customer.get('name', '—')}\n"
        text += f"📞 <b>Tel:</b> <code>{customer.get('phone', '—')}</code>\n"
        text += f"📍 <b>Manzil:</b> {customer.get('address', '—')}\n"

        if customer.get("location"):
            lat = customer["location"].get("lat")
            lng = customer["location"].get("lng")
            if lat and lng:
                text += f"🗺 <a href='https://www.google.com/maps?q={lat},{lng}'>Xaritada ko'rish</a>\n"

        if customer.get("comment"):
            text += f"💬 <b>Izoh:</b> {customer['comment']}\n"

        text += f"\n💳 <b>To'lov:</b> {pay_label}\n"
        text += f"\n📦 <b>Mahsulotlar:</b>\n{get_products_text(products)}"
        text += "━" * 22 + "\n"

        subtotal = order_data.get("subtotal")
        discount = order_data.get("discount") or 0
        delivery_fee = order_data.get("deliveryFee") or 0
        if isinstance(subtotal, (int, float)) and (discount or delivery_fee):
            text += f"🧾 Mahsulotlar: {db.format_price(subtotal)}\n"
            if discount:
                promo = order_data.get("promoCode")
                promo_text = f" ({promo})" if promo else ""
                text += f"🏷 Chegirma{promo_text}: -{db.format_price(discount)}\n"
            if delivery_fee:
                text += f"🚚 Yetkazib berish: {db.format_price(delivery_fee)}\n"
            else:
                text += "🚚 Yetkazib berish: bepul\n"

        text += f"💰 <b>Jami: {total_str}</b>\n"
        text += "⏰ <b>Status:</b> 🟡 Yangi"
        if pay_method == "Karta":
            text += "\n💳 <b>To'lov:</b> ⏳ Chek kutilmoqda"

        for admin_id in all_admins():
            try:
                await bot.send_message(admin_id, text,
                                       reply_markup=order_action_kb(doc_id, has_location),
                                       disable_web_page_preview=True)
            except Exception as e:
                logger.warning(f"[ADMIN] {admin_id} ga yuborib bo'lmadi: {e}")
        logger.info(f"[ADMIN] Yuborildi: {order_id} | {pay_method}")

        # ── USER XABARI (faqat Karta) ─────────────────────────
        if pay_method == "Karta":
            if not user_id:
                logger.warning(f"[USER] userId yo'q — xabar yuborib bo'lmaydi ({order_id})")
                return
            u_text  = "🎉 <b>Buyurtmangiz qabul qilindi!</b>\n"
            u_text += "━" * 22 + "\n\n"
            u_text += f"🆔 Buyurtma: <b>{order_id}</b>\n"
            u_text += "📦 <b>Mahsulotlar:</b>\n"
            for p in products:
                qty  = p.get("quantity", 1)
                prod = p.get("product") or p
                u_text += f"  • {prod.get('name', '—')} × {qty}\n"
            u_text += f"\n💰 Jami: <b>{total_str}</b>\n"
            u_text += "━" * 22 + "\n\n"
            pay_cfg = db.get_payment_settings()
            u_text += "💳 <b>To'lov uchun karta:</b>\n"
            u_text += f"<code>{pay_cfg['cardNumber']}</code>\n"
            u_text += f"👤 Egasi: <b>{pay_cfg['cardOwner']}</b>\n\n"
            u_text += (
                "📸 Kartaga o'tkazma qilgandan so'ng "
                "pastdagi tugmani bosib <b>chekni (screenshot)</b> yuboring.\n"
                "Admin tekshirib tasdiqlaydi ✅"
            )
            try:
                await bot.send_message(user_id, u_text, reply_markup=receipt_kb(doc_id))
                logger.info(f"[USER] Karta xabari yuborildi → {user_id} ({order_id})")
            except Exception as e:
                logger.error(f"[USER] Xabar yuborib bo'lmadi {user_id}: {e}")

    except Exception as e:
        logger.error(f"[ADMIN] notify_admin_order xatosi: {e}", exc_info=True)
        # Bayroqni qaytaramiz — buyurtma keyingi urinishda qayta yuboriladi (F-21)
        failed_doc_id = order_data.get("_doc_id")
        if failed_doc_id:
            db.release_order_notification(failed_doc_id)


async def notify_admin_cancel(order_data: dict):
    """Mijoz buyurtmani bekor qilganda adminga xabar (5-band)."""
    try:
        customer = order_data.get("customer", {})
        display_id = db.order_display_id(order_data)
        total = order_data.get("total", 0)
        total_str = db.format_price(total) if isinstance(total, (int, float)) else str(total)

        cust_name = customer.get("name") or "—"
        cust_phone = customer.get("phone") or "—"

        text = f"\u274c <b>BUYURTMA BEKOR QILINDI</b>\n"
        text += "\u2501" * 22 + "\n\n"
        text += f"\U0001f9fe Buyurtma: <b>{display_id}</b>\n"
        text += f"\U0001f464 Mijoz: {cust_name}\n"
        text += f"\U0001f4de Tel: <code>{cust_phone}</code>\n"
        text += f"\U0001f4b0 Summa: <b>{total_str}</b>\n\n"
        text += "\U0001f4e6 <b>Mahsulotlar:</b>\n"
        for item in order_data.get("products", []):
            prod = item.get("product") or item
            text += f"  \u2022 {prod.get('name', '?')} \u00d7 {item.get('quantity', 1)}\n"
        text += "\n<i>Mijozning o'zi bekor qildi. Ombor qoldig'i qaytarildi.</i>"

        for admin_id in all_admins():
            try:
                await bot.send_message(admin_id, text)
            except Exception as e:
                logger.warning(f"[CANCEL] {admin_id} ga yuborib bo'lmadi: {e}")

        logger.info(f"[CANCEL] {display_id} bekor qilindi")
    except Exception as e:
        logger.error(f"[CANCEL] xato: {e}", exc_info=True)


# ─── Status o'zgartirish → Usergа xabar ──────────────────────

@dp.callback_query(F.data.startswith("os:"))
async def cb_order_status(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    # order_id — Firestore hujjat id'si (F-03)
    _, status, order_id = callback.data.split(":", 2)

    if not db.update_order_status(order_id, status):
        await callback.answer("❌ Firestore yangilanmadi", show_alert=True)
        return

    emoji = STATUS_EMOJI.get(status, "ℹ️")

    # User'ga xabar
    order = db.get_order_by_id(order_id)
    display_id = db.order_display_id(order) if order else order_id
    if order and order.get("userId"):
        try:
            u_text  = "📦 <b>Buyurtmangiz yangilandi!</b>\n"
            u_text += "━" * 22 + "\n\n"
            u_text += f"🆔 Buyurtma: <b>{display_id}</b>\n"
            u_text += f"⏰ Yangi status: {emoji} <b>{status}</b>\n\n"
            u_text += "Batafsil ko'rish uchun 👇"
            await bot.send_message(order["userId"], u_text, reply_markup=mini_app_kb())
        except Exception as e:
            logger.warning(f"[USER] Status xabar xatosi: {e}")

    # Admin xabarini yangilash
    old = callback.message.html_text
    if "⏰ <b>Status:</b>" in old:
        new = old.split("⏰ <b>Status:</b>")[0] + f"⏰ <b>Status:</b> {emoji} {status}"
    else:
        new = old + f"\n⏰ <b>Status:</b> {emoji} {status}"

    # Xabar rasmli bo'lishi mumkin (chek tasdiqlangandan keyin status
    # tugmalari o'sha rasmga qo'shiladi) — u holda izohni tahrirlaymiz.
    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=new, reply_markup=callback.message.reply_markup
            )
        else:
            await callback.message.edit_text(
                new, reply_markup=callback.message.reply_markup,
                disable_web_page_preview=True,
            )
    except Exception as e:
        logger.warning(f"[STATUS] Admin xabarini yangilab bo'lmadi: {e}")
    await callback.answer(f"✅ {status}")


# ─── Chek yuborish ────────────────────────────────────────────

@dp.callback_query(F.data.startswith("receipt:"))
async def cb_start_receipt(callback: CallbackQuery, state: FSMContext):
    order_id = callback.data.split("receipt:", 1)[-1]
    await state.update_data(receipt_order_id=order_id)
    await state.set_state(PaymentUpload.waiting_photo)
    await callback.message.answer(
        "📸 <b>To'lov chekini yuboring</b>\n\n"
        "Pul o'tkazilganini tasdiqlovchi <b>screenshot yoki rasmni</b> yuboring:"
    )
    await callback.answer()


@dp.message(PaymentUpload.waiting_photo, F.photo)
async def handle_receipt_photo(message: Message, state: FSMContext):
    data     = await state.get_data()
    order_id = data.get("receipt_order_id", "—")
    user_id  = message.from_user.id

    order   = db.get_order_by_id(order_id) if order_id != "—" else None
    display_id = db.order_display_id(order) if order else order_id
    caption = build_receipt_caption(order, display_id)

    try:
        for admin_id in all_admins():
            try:
                await bot.send_photo(admin_id,
                                     photo=message.photo[-1].file_id,
                                     caption=caption,
                                     reply_markup=payment_confirm_kb(
                                         order_id, user_id, order_has_location(order)))
            except Exception as e:
                logger.warning(f"[RECEIPT] Admin {admin_id} ga yuborib bo'lmadi: {e}")
        logger.info(f"[RECEIPT] Adminga yo'naltirildi: {order_id} ← {user_id}")
    except Exception as e:
        logger.error(f"[RECEIPT] Adminga yuborib bo'lmadi: {e}")

    await state.clear()
    await message.answer(
        "✅ <b>Chekingiz yuborildi!</b>\n\n"
        "Admin tekshirib, tez orada xabar beramiz 📬"
    )


@dp.message(PaymentUpload.waiting_photo)
async def handle_receipt_wrong(message: Message):
    await message.answer("❌ Iltimos, to'lov chekini <b>rasm (foto)</b> sifatida yuboring.")


# ─── Admin: To'lovni tasdiqlash / rad etish ──────────────────

@dp.callback_query(F.data.startswith("pconf:"))
async def cb_payment_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q", show_alert=True)
        return

    parts    = callback.data.split(":")
    action   = parts[1]        # ok | no
    order_id = parts[2]        # Firestore hujjat id'si
    user_id  = int(parts[3])

    order      = db.get_order_by_id(order_id)
    display_id = db.order_display_id(order) if order else order_id

    # Ikkinchi admin ham xuddi shu chekni olgan bo'ladi. U kechroq
    # tugma bossa, mijozga takroriy xabar ketmasligi kerak.
    current = (order or {}).get("paymentStatus")
    if current in ("Tolangan", "Rad etildi"):
        already = "tasdiqlangan" if current == "Tolangan" else "rad etilgan"
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.answer(f"Bu chek allaqachon {already}", show_alert=True)
        return

    approved = action == "ok"
    db.update_payment_status(order_id, "Tolangan" if approved else "Rad etildi")
    logger.info(f"[PAY] {'Tasdiqlandi' if approved else 'Rad etildi'}: {order_id}")

    # ── Mijozga xabar (bitta, faqat bir marta) ──
    try:
        if approved:
            u_text  = "✅ <b>To'lovingiz tasdiqlandi!</b>\n"
            u_text += "━" * 22 + "\n\n"
            u_text += f"🧾 Buyurtma: <b>{display_id}</b>\n"
            u_text += "💰 To'lov qabul qilindi! Tez orada yetkaziladi 🚀"
            await bot.send_message(user_id, u_text, reply_markup=mini_app_kb())
        else:
            u_text  = "❌ <b>To'lov cheki rad etildi</b>\n"
            u_text += "━" * 22 + "\n\n"
            u_text += f"🧾 Buyurtma: <b>{display_id}</b>\n"
            u_text += "Iltimos, to'g'ri chekni qayta yuboring."
            await bot.send_message(user_id, u_text, reply_markup=resend_receipt_kb(order_id))
    except Exception as e:
        logger.warning(f"[PAY] Mijozga xabar yuborilmadi: {e}")

    # ── Chek xabarini SHU YERNING O'ZIDA yangilaymiz ──
    # Ilgari bu yerda har bir adminga alohida "statusni o'zgartiring"
    # xabari yuborilardi. Natijada tasdiqlashdan keyin ortiqcha xabarlar
    # to'planib qolardi, holbuki status tugmalari shu xabarga sig'adi.
    mark = "✅ <b>TO'LOV TASDIQLANDI</b>" if approved else "❌ <b>CHEK RAD ETILDI</b>"
    hint = "Endi buyurtma holatini belgilang 👇" if approved else "Mijoz yangi chek yuborishi kutilmoqda."
    try:
        await callback.message.edit_caption(
            caption=current_caption(callback.message) + f"\n\n{mark}\n{hint}",
            reply_markup=order_action_kb(order_id, order_has_location(order)) if approved else None,
        )
    except Exception as e:
        logger.warning(f"[PAY] Chek xabarini yangilab bo'lmadi: {e}")

    await callback.answer("✅ Tasdiqlandi" if approved else "❌ Rad etildi")


# ─── Lokatsiyani yuborish ────────────────────────────────────

@dp.callback_query(F.data.startswith("loc:"))
async def cb_send_location(callback: CallbackQuery):
    """
    Mijoz manzilini haqiqiy Telegram lokatsiyasi sifatida yuboradi.

    Havola emas, venue xabari — uni kuryerga oddiy forward qilish
    mumkin va u xaritada ochiladi.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q", show_alert=True)
        return

    order_id = callback.data[len("loc:"):]
    order = db.get_order_by_id(order_id)

    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return

    customer = order.get("customer", {})
    loc = customer.get("location") or {}
    lat, lng = loc.get("lat"), loc.get("lng")

    if lat is None or lng is None:
        await callback.answer("Bu buyurtmada lokatsiya yo'q", show_alert=True)
        return

    display_id = db.order_display_id(order)
    title = f"{customer.get('name') or 'Mijoz'} — {display_id}"
    address = customer.get("address") or "Manzil ko'rsatilmagan"

    try:
        # send_venue — pin + nom + manzil. Forward qilinadi, xaritada ochiladi.
        await bot.send_venue(
            callback.from_user.id,
            latitude=float(lat),
            longitude=float(lng),
            title=title[:255],
            address=address[:255],
        )
        await callback.answer("Lokatsiya yuborildi")
        logger.info(f"[LOC] {display_id} -> {callback.from_user.id}")
    except Exception as e:
        logger.error(f"[LOC] yuborilmadi: {e}")
        await callback.answer("Lokatsiyani yuborib bo'lmadi", show_alert=True)


# ─── Buyurtmalarim ───────────────────────────────────────────

@dp.message(F.text == "📦 Buyurtmalarim")
async def handle_my_orders(message: Message):
    user_id = message.from_user.id
    orders  = db.get_user_orders(user_id)

    if not orders:
        await message.answer(
            "📦 <b>Sizda hozircha buyurtmalar mavjud emas.</b>\n\n"
            "Katalogdan yoqqan ta'mingizni tanlab, birinchi buyurtmangizni bering! 🥤"
        )
        return

    text = f"📦 <b>Buyurtmalarim</b> ({len(orders)} ta)\n" + "━" * 22 + "\n\n"
    btns = []

    for o in orders[:10]:
        # oid — ko'rsatish uchun, doc_id — tugmalar uchun (F-03)
        oid    = db.order_display_id(o)
        doc_id = o.get("_doc_id", "")
        tot  = o.get("total", 0)
        st   = o.get("status", "Yangi")
        pm   = o.get("paymentMethod", "Naqd")
        ps   = o.get("paymentStatus", "")
        e    = STATUS_EMOJI.get(st, "🟡")
        tstr = db.format_price(tot) if isinstance(tot, (int, float)) else str(tot)

        date_str = db.order_date_text(o)
        
        text += f"🧾 <b>Buyurtma:</b> {oid}\n"
        if date_str != "—": text += f"📅 <b>Sana:</b> {date_str}\n"
        text += f"📊 <b>Holat:</b> {e} {st}\n"
        
        if pm == "Karta":
            if ps == "Tolangan":
                text += "💳 <b>To'lov turi:</b> Karta (✅ Tasdiqlangan)\n"
            elif ps == "Rad etildi":
                text += "💳 <b>To'lov turi:</b> Karta (❌ Rad etilgan)\n"
                btns.append([InlineKeyboardButton(
                    text=f"💳 {oid} — qayta chek",
                    callback_data=f"receipt:{doc_id}"
                )])
            else:
                text += "💳 <b>To'lov turi:</b> Karta (⏳ Chek kutilmoqda)\n"
                btns.append([InlineKeyboardButton(
                    text=f"💳 {oid} — chek yuborish",
                    callback_data=f"receipt:{doc_id}"
                )])
        else:
            text += "💳 <b>To'lov turi:</b> 💵 Naqd (yetkazganda)\n"

        text += "\n🛍 <b>Mahsulotlar:</b>\n"
        
        products = o.get("products", [])
        for idx, p in enumerate(products, 1):
            qty   = p.get("quantity", 1)
            size  = p.get("size")
            color = p.get("color")
            prod  = p.get("product") or p
            name  = prod.get("name", "—")
            
            variant = []
            if size: variant.append(f"Hajm: {size}")
            if color: variant.append(f"Ta'm: {color}")
            v_text = f" ({', '.join(variant)})" if variant else ""
            
            text += f"  {idx}. {name}{v_text} — <b>{qty} ta</b>\n"
            
        text += f"\n💰 <b>Jami summa:</b> {tstr}\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=btns) if btns else None
    await message.answer(text, reply_markup=kb)


# ─── /start ──────────────────────────────────────────────────

@dp.message(F.text.startswith("/start"))
async def cmd_start(message: Message, state: FSMContext):
    user     = message.from_user
    admin = is_admin(user.id)

    # ── Deep link: /start receipt_<hujjat_id> ──
    # Yangi havolalar Firestore hujjat id'sini yuboradi. Eski havolalarda
    # "#" siz raqam kelardi — u ham ishlashda davom etadi (F-03).
    parts = message.text.split(" ", 1)
    if len(parts) > 1 and parts[1].startswith("receipt_"):
        raw_id = parts[1].replace("receipt_", "").strip()

        order = db.get_order_by_id(raw_id) or db.get_order_by_id(f"#{raw_id}")
        if order:
            order_id   = order.get("_doc_id", raw_id)
            display_id = db.order_display_id(order)
            products  = order.get("products", [])
            total     = order.get("total", 0)
            total_str = db.format_price(total) if isinstance(total, (int, float)) else str(total)

            await state.update_data(receipt_order_id=order_id)
            await state.set_state(PaymentUpload.waiting_photo)

            u_text  = "💳 <b>To'lov ma'lumotlari</b>\n"
            u_text += "━" * 22 + "\n\n"
            u_text += f"🆔 Buyurtma ID: <b>{display_id}</b>\n"
            u_text += "📦 <b>Mahsulotlar:</b>\n"
            for p in products:
                qty   = p.get("quantity", 1)
                size  = p.get("size")
                color = p.get("color")
                prod  = p.get("product") or p
                name  = prod.get("name", "—")
                
                variant_info = []
                if size: variant_info.append(f"Hajm: {size}")
                if color: variant_info.append(f"Ta'm: {color}")
                var_text = f" ({', '.join(variant_info)})" if variant_info else ""
                
                u_text += f"  • {name}{var_text} × {qty}\n"
            u_text += f"\n💰 Jami: <b>{total_str}</b>\n"
            u_text += "━" * 22 + "\n\n"
            pay_cfg = db.get_payment_settings()
            u_text += "💳 <b>Karta raqami:</b>\n"
            u_text += f"<code>{pay_cfg['cardNumber']}</code>\n"
            u_text += f"👤 Egasi: <b>{pay_cfg['cardOwner']}</b>\n\n"
            u_text += "📸 Pul o'tkazgandan so'ng <b>to'lov chekini (screenshot)</b> yuboring:"
            await message.answer(u_text, reply_markup=main_kb(admin))
        else:
            await message.answer(
                "❌ Buyurtma topilmadi.\n"
                "Iltimos, mini appdagi «To'lov chekini yuborish» tugmasini qayta bosing.",
                reply_markup=main_kb(admin)
            )
        return

    # ── Oddiy /start ──
    text = (
        f"Assalomu alaykum, <b>{user.first_name}</b>! 👋\n\n"
        "🥤 <b>V7 rasmiy do'koniga xush kelibsiz!</b>\n"
        "<i>Vitamin Sparkling Drink — 100% tabiiy ta'm, 300 ml.</i>\n\n"
        "🍋 <b>9 xil ta'm, 3 ta liniya:</b> Vitamin Sparkling, Super Soda va Flavored Malt.\n\n"
        "👇 <i>Buyurtmani boshlash uchun quyidagi tugmani bosing:</i>"
    )
    await message.answer(text, reply_markup=main_kb(admin))

    # Telefon raqami hali saqlanmagan bo'lsa, bir bosishda so'raymiz.
    # Mini app buni buyurtma formasiga avtomatik qo'yadi (F-26).
    saved = db.get_user(user.id) or {}
    if not saved.get("phone"):
        await message.answer(
            "📱 <b>Telefon raqamingizni qoldiring</b>\n\n"
            "Buyurtma berganingizda uni qayta yozib o'tirmaysiz, "
            "kuryer esa siz bilan tez bog'lana oladi.\n\n"
            "<i>Ixtiyoriy — keyinroq ilovaning «Shaxsiy ma'lumotlar» "
            "bo'limidan ham kiritish mumkin.</i>",
            reply_markup=contact_kb(),
        )


@dp.message(F.contact)
async def handle_contact(message: Message):
    """Foydalanuvchi «Raqamni yuborish» tugmasini bosganda (F-26)."""
    contact = message.contact

    # Faqat o'z raqamini qabul qilamiz — boshqa odamning kontaktini emas
    if contact.user_id != message.from_user.id:
        await message.answer(
            "❌ Iltimos, <b>o'zingizning</b> raqamingizni yuboring.",
            reply_markup=contact_kb(),
        )
        return

    admin = is_admin(message.from_user.id)
    phone = contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"

    if db.set_user_phone(message.from_user.id, phone):
        await message.answer(
            f"✅ Raqamingiz saqlandi: <code>{phone}</code>\n\n"
            "Endi buyurtma berishda u avtomatik to'ldiriladi.",
            reply_markup=main_kb(admin),
        )
    else:
        await message.answer(
            "❌ Raqamni saqlab bo'lmadi. Keyinroq qayta urinib ko'ring.",
            reply_markup=main_kb(admin),
        )


@dp.message(F.text == "🛠 Admin Panel")
async def handle_admin_btn(message: Message, state: FSMContext):
    from admin import cmd_admin
    await cmd_admin(message, state)


@dp.message(F.text == "🥤 Katalogni ochish")
async def handle_open_catalog(message: Message):
    """
    Katalog tugmasi bosilganda mini appni qayerdan ochishni ko'rsatadi.
    Tugmaning o'ziga web_app biriktirilmagan — do'kon yozuv maydoni
    yonidagi doimiy menyu tugmasi orqali ochiladi.
    """
    text = "🥤 <b>V7 KATALOGI</b>\n"
    text += "━" * 22 + "\n\n"
    text += "Do'konimiz Telegram ilovasi ichida ochiladi.\n\n"
    text += "👇 Pastda, <b>yozuv maydonining chap tomonida</b>\n"
    text += "   <b>«🥤 Katalog»</b> tugmasi turibdi.\n\n"
    text += "Shu tugmani bosing — do'kon shu yerning o'zida ochiladi.\n\n"
    text += "━" * 22 + "\n"
    text += "✨ <i>To'qqizta ta'mni ko'ring, savatga qo'shing va\n"
    text += "bir necha bosishda buyurtma bering.</i>"

    await message.answer(text)


@dp.message(F.text == "📞 Biz bilan aloqa")
async def cmd_contact(message: Message):
    await message.answer(
        "📞 <b>V7 bilan bog'lanish:</b>\n\n"
        f"💬 <b>Mijozlar xizmati:</b> {SUPPORT_TELEGRAM}\n"
        f"📞 <b>Telefon raqam:</b> {SUPPORT_PHONE}\n"
        f"✉️ <b>Email:</b> {SUPPORT_EMAIL}\n"
        f"📍 <b>Manzil:</b> {COMPANY_CITY}\n"
        f"⏰ <b>Ish vaqti:</b> {WORK_HOURS}\n\n"
        "<i>Ulgurji xarid va hamkorlik bo'yicha ham shu raqamga murojaat qiling.</i>"
    )


@dp.message(F.text.in_({"ℹ️ Yordam", "/help"}))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ <b>Botdan qanday foydalanish mumkin?</b>\n\n"
        "1️⃣ Yozuv maydoni yonidagi <b>«🥤 Katalog»</b> tugmasini bosib, "
        "V7 ta'mlari bilan tanishing.\n"
        "2️⃣ O'zingizga yoqqan ta'mlarni <b>Savatga</b> qo'shing.\n"
        "3️⃣ Buyurtmani rasmiylashtirishda <b>Naqd</b> yoki <b>Karta</b> orqali to'lov usulini tanlang.\n"
        "4️⃣ Agar karta orqali to'lov qilsangiz, to'lov chekini botga yuboring.\n"
        "5️⃣ Buyurtmangiz holatini <b>Buyurtmalarim</b> bo'limidan kuzatib boring.\n\n"
        "<i>Qo'shimcha savollar uchun <b>'📞 Biz bilan aloqa'</b> bo'limiga murojaat qiling.</i>"
    )


# ─── WebApp sendData (fallback) ───────────────────────────────

@dp.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    try:
        data       = json.loads(message.web_app_data.data)
        pay_method = data.get("paymentMethod", "Naqd")
        order_id   = data.get("id", "")
        await notify_admin_order(data)
        if pay_method == "Naqd":
            await message.answer(
                f"🎉 <b>Buyurtmangiz qabul qilindi!</b>\n"
                f"🆔 Buyurtma: <b>{order_id}</b>\n"
                "💵 To'lov: Naqd (yetkazganda)\n\n"
                "Operatorimiz tez orada bog'lanadi 📞"
            )
    except Exception as e:
        logger.error(f"WebApp data: {e}")
        await message.answer("❌ Xatolik. Qayta urinib ko'ring.")


# ─── Main ─────────────────────────────────────────────────────

async def main():
    # Sozlama hujjatlari hali yo'q bo'lsa, boshlang'ich qiymatlar bilan yaratamiz
    db.ensure_payment_settings()
    db.ensure_delivery_settings()

    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="🥤 Katalog", web_app=WebAppInfo(url=MINI_APP_URL))
        )
    except Exception as e:
        logger.warning(f"Menu button: {e}")

    loop = asyncio.get_running_loop()

    def on_new_order(order_data):
        asyncio.run_coroutine_threadsafe(notify_admin_order(order_data), loop)

    def on_order_cancelled(order_data):
        asyncio.run_coroutine_threadsafe(notify_admin_cancel(order_data), loop)

    watch = db.listen_to_new_orders(on_new_order, on_order_cancelled)
    logger.info("[BOT] Ishga tushdi ✅")

    try:
        await dp.start_polling(bot)
    finally:
        watch.unsubscribe()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
