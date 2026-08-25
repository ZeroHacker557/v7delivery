"""
Admin panel — Telegram inline keyboard orqali mahsulot va kategoriya boshqaruvi.
"""
import asyncio
import os
import uuid
from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import IMAGES_DIR
import firebase_db as db

router = Router()


# ─── FSM States ──────────────────────────────────────────────

class AddCategory(StatesGroup):
    name = State()


class RenameCategory(StatesGroup):
    name = State()


class AddAdmin(StatesGroup):
    query = State()

class BroadcastMenu(StatesGroup):
    message = State()

class AddPromo(StatesGroup):
    code = State()
    discount = State()


class AddProduct(StatesGroup):
    category = State()
    name = State()
    price = State()
    old_price = State()
    description = State()
    sizes = State()
    color = State()
    discount = State()
    stock = State()
    image = State()
    more_images = State()


class EditProduct(StatesGroup):
    value = State()
    image = State()


class DeliverySettings(StatesGroup):
    fee = State()
    free_from = State()


# ─── Helpers ─────────────────────────────────────────────────

# is_admin va boshqalar admins.py da — ro'yxat Firestore'dan keladi
import admins as admins_module  # noqa: E402
from admins import all_admins, is_admin, is_owner  # noqa: E402


def admin_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Buyurtmalar", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📦 Mahsulotlar", callback_data="admin_products"),
         InlineKeyboardButton(text="📂 Kategoriyalar", callback_data="admin_categories")],
        [InlineKeyboardButton(text="➕ Mahsulot qo'shish", callback_data="admin_add_product")],
        [InlineKeyboardButton(text="➕ Kategoriya qo'shish", callback_data="admin_add_category")],
        [InlineKeyboardButton(text="🎟 Promokodlar", callback_data="admin_promocodes"),
         InlineKeyboardButton(text="📢 Xabarnoma", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🚚 Yetkazib berish", callback_data="admin_delivery"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📈 Sotuv hisoboti", callback_data="report_7"),
         InlineKeyboardButton(text="👀 Analitika", callback_data="analytics_7")],
        [InlineKeyboardButton(text="👥 Adminlar", callback_data="admin_admins")],
    ])


def back_to_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")]
    ])


async def safe_edit_msg(callback: CallbackQuery, text: str, reply_markup=None,
                        parse_mode: str | None = "HTML", **kwargs):
    """
    Xabarni xavfsiz tahrirlaydi.

    Mahsulot rasm bilan ko'rsatilgandan keyin har qanday "orqaga" tugmasi
    o'sha RASMLI xabarni tahrirlashga urinadi, Telegram esa
    "there is no text in the message to edit" deb rad etadi. Bunday holatda
    eski xabarni o'chirib, yangisini yuboramiz.

    "message is not modified" xatosi ham zararsiz — e'tiborsiz qoldiriladi.
    """
    try:
        await callback.message.edit_text(
            text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs
        )
        return
    except TelegramBadRequest as e:
        detail = str(e).lower()
        if "message is not modified" in detail:
            return
        if not ("no text in the message" in detail
                or "message can't be edited" in detail
                or "message to edit not found" in detail):
            raise
    except Exception:
        pass

    # Tahrirlab bo'lmadi — eskisini o'chirib yangisini yuboramiz
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs
    )


async def safe_edit(callback: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None):
    """Qisqa yozuv: safe_edit_msg ustidan."""
    await safe_edit_msg(callback, text, reply_markup=kb, parse_mode="HTML")


def stock_mark(product: dict) -> str:
    """Ro'yxatdagi qoldiq belgisi."""
    stock = product.get("stock")
    if not isinstance(stock, int):
        return "\U0001f4e6"
    if stock == 0:
        return "\U0001f534"
    if stock <= 5:
        return "\U0001f7e1"
    return "\U0001f7e2"


def product_edit_kb(prod_id) -> InlineKeyboardMarkup:
    """Mahsulotning barcha maydonlarini tahrirlash."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Nom", callback_data=f"pedit_name_{prod_id}"),
         InlineKeyboardButton(text="💰 Narx", callback_data=f"pedit_price_{prod_id}")],
        [InlineKeyboardButton(text="🏷 Eski narx", callback_data=f"pedit_oldPrice_{prod_id}"),
         InlineKeyboardButton(text="🎯 Chegirma", callback_data=f"pedit_discount_{prod_id}")],
        [InlineKeyboardButton(text="📦 Qoldiq", callback_data=f"pedit_stock_{prod_id}"),
         InlineKeyboardButton(text="📝 Tavsif", callback_data=f"pedit_description_{prod_id}")],
        [InlineKeyboardButton(text="🥤 Hajmlar", callback_data=f"pedit_sizes_{prod_id}"),
         InlineKeyboardButton(text="🍋 Ta'mlar", callback_data=f"pedit_color_{prod_id}")],
        [InlineKeyboardButton(text="📂 Kategoriya", callback_data=f"pcat_{prod_id}"),
         InlineKeyboardButton(text="🖼 Rasmlar", callback_data=f"pimg_{prod_id}")],
        [InlineKeyboardButton(text="🗑 Mahsulotni o'chirish", callback_data=f"prod_del_{prod_id}")],
        [InlineKeyboardButton(text="◀️ Mahsulotlar", callback_data="admin_products")],
    ])


def skip_kb(next_step: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"skip_{next_step}")]
    ])


# ─── Admin Menu ──────────────────────────────────────────────

@router.message(F.text == "/admin")
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return
    await state.clear()
    await message.answer(
        "🛠 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await safe_edit_msg(callback, 
        "🛠 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )


# ─── Statistics ──────────────────────────────────────────────

@router.callback_query(F.data == "admin_stats")
async def cb_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    products = db.get_products()
    categories = db.get_categories()
    users = db.get_all_users()
    
    docs = db.db.collection("orders").get()
    orders = [doc.to_dict() for doc in docs]
    
    total_revenue = sum(o.get('total', 0) for o in orders if o.get('status') == 'Yetkazildi')
    active_orders = sum(1 for o in orders if o.get('status') in ['Yangi', 'Qabul qilindi', 'Yetkazilmoqda'])
    
    await safe_edit_msg(callback, 
        f"📊 <b>Batafsil Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{len(users)}</b>\n"
        f"📦 Mahsulotlar: <b>{len(products)}</b>\n"
        f"📂 Kategoriyalar: <b>{len(categories)}</b>\n"
        f"🛒 Barcha buyurtmalar: <b>{len(orders)}</b>\n"
        f"🔄 Faol buyurtmalar: <b>{active_orders}</b>\n"
        f"💰 Umumiy daromad: <b>{db.format_price(total_revenue)}</b>\n",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )


# ─── Categories ──────────────────────────────────────────────

@router.callback_query(F.data == "admin_categories")
async def cb_categories(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cats = db.get_categories()
    if not cats:
        await safe_edit_msg(callback, 
            "📂 <b>Kategoriyalar</b>\n\nHali kategoriya qo'shilmagan.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Kategoriya qo'shish", callback_data="admin_add_category")],
                [InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")]
            ]),
            parse_mode="HTML"
        )
        return

    buttons = []
    for c in cats:
        count = db.count_products_in_category(c["name"])
        buttons.append([
            InlineKeyboardButton(
                text=f"✏️ {c['name']} ({count})",
                callback_data=f"cat_edit_{c['id']}",
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"cat_del_{c['id']}")
        ])
    buttons.append([InlineKeyboardButton(text="➕ Kategoriya qo'shish", callback_data="admin_add_category")])
    buttons.append([InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")])

    await safe_edit_msg(
        callback,
        f"📂 <b>Kategoriyalar</b> ({len(cats)} ta)\n\n"
        "Nomini o'zgartirish uchun kategoriya ustiga, o'chirish uchun 🗑 bosing.\n"
        "<i>Qavs ichida — shu kategoriyadagi mahsulotlar soni.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_add_category")
async def cb_add_category(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddCategory.name)
    await safe_edit_msg(callback, 
        "📂 <b>Yangi kategoriya</b>\n\nKategoriya nomini yozing:",
        parse_mode="HTML"
    )


@router.message(AddCategory.name)
async def process_category_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    cat = db.add_category(message.text.strip())
    await state.clear()
    await message.answer(
        f"✅ Kategoriya qo'shildi: <b>{cat['name']}</b>",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("cat_edit_"))
async def cb_rename_category(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    cat_id = callback.data[len("cat_edit_"):]
    cat = db.get_category_by_id(cat_id)
    if not cat:
        await callback.answer("Kategoriya topilmadi", show_alert=True)
        return

    count = db.count_products_in_category(cat["name"])

    await state.update_data(rename_cat_id=cat_id)
    await state.set_state(RenameCategory.name)

    text = f"✏️ <b>Kategoriya nomini o'zgartirish</b>\n\n"
    text += f"Hozirgi nom: <b>{cat['name']}</b>\n"
    text += f"Mahsulotlar: <b>{count}</b> ta\n\n"
    text += "Yangi nomni yozing:"
    if count:
        text += (
            f"\n\n<i>Nom o'zgarganda shu kategoriyadagi {count} ta mahsulot "
            "ham avtomatik yangilanadi.</i>"
        )
    text += "\n\n<i>Bekor qilish uchun /cancel</i>"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.message(RenameCategory.name)
async def process_rename_category(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    raw = (message.text or "").strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=back_to_menu_kb())
        return

    if not raw:
        await message.answer("Nom bo'sh bo'lmasligi kerak.")
        return
    if len(raw) > 60:
        await message.answer("Nom juda uzun — 60 belgidan oshmasin.")
        return

    data = await state.get_data()
    cat_id = data.get("rename_cat_id")
    cat = db.get_category_by_id(cat_id)
    if not cat:
        await state.clear()
        await message.answer("Kategoriya topilmadi.", reply_markup=back_to_menu_kb())
        return

    # Bir xil nomli kategoriya bormi?
    for other in db.get_categories():
        if str(other["id"]) != str(cat_id) and other["name"].lower() == raw.lower():
            await message.answer("Bunday nomli kategoriya allaqachon bor. Boshqa nom kiriting.")
            return

    old_name = cat["name"]
    updated = db.rename_category(cat_id, raw)
    await state.clear()

    text = f"✅ Kategoriya nomi o'zgartirildi:\n<b>{old_name}</b> → <b>{raw}</b>"
    if updated:
        text += f"\n\n📦 {updated} ta mahsulot yangi nomga o'tkazildi."

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📂 Kategoriyalar", callback_data="admin_categories")],
            [InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")],
        ]),
    )


@router.callback_query(F.data.startswith("cat_del_"))
async def cb_delete_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cat_id = callback.data.split("cat_del_")[-1]
    cat = db.get_category_by_id(cat_id)
    name = cat["name"] if cat else "Noma'lum"
    db.delete_category(cat_id)
    await callback.answer(f"🗑 {name} o'chirildi")
    # Refresh list
    await cb_categories(callback)


# ─── Products List ───────────────────────────────────────────

@router.callback_query(F.data == "admin_products")
async def cb_products(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    products = db.get_products()
    if not products:
        await safe_edit_msg(callback, 
            "📦 <b>Mahsulotlar</b>\n\nHali mahsulot qo'shilmagan.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Mahsulot qo'shish", callback_data="admin_add_product")],
                [InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")]
            ]),
            parse_mode="HTML"
        )
        return

    buttons = []
    for p in products[-20:]:  # Last 20
        buttons.append([
            InlineKeyboardButton(
                text=f"{stock_mark(p)} {p['name'][:26]} — {db.format_price(p['price'])}",
                callback_data=f"prod_view_{p['id']}"
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"prod_del_{p['id']}")
        ])
    buttons.append([InlineKeyboardButton(text="➕ Mahsulot qo'shish", callback_data="admin_add_product")])
    buttons.append([InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")])

    await safe_edit_msg(callback, 
        f"📦 <b>Mahsulotlar</b> ({len(products)} ta)\n\nKo'rish yoki o'chirish:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("prod_view_"))
async def cb_view_product(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    prod_id = callback.data.split("prod_view_")[-1]
    p = db.get_product_by_id(prod_id)
    if not p:
        await callback.answer("Mahsulot topilmadi")
        return

    text = (
        f"📦 <b>{p['name']}</b>\n\n"
        f"💰 Narx: <b>{db.format_price(p['price'])}</b>\n"
    )
    if p.get("oldPrice"):
        text += f"💰 Eski narx: <s>{db.format_price(p['oldPrice'])}</s>\n"
    text += f"📂 Kategoriya: {p['category']}\n"
    if p.get("color"):
        text += f"🍋 Ta'm: {p['color']}\n"
    if p.get("sizes"):
        text += f"🥤 Hajm: {', '.join(p['sizes'])}\n"
    if p.get("discount"):
        text += f"🏷 Chegirma: {p['discount']}\n"
    if p.get("description"):
        text += f"\n📝 {p['description'][:200]}\n"
    stock = p.get("stock")
    if isinstance(stock, int):
        mark = "🔴" if stock == 0 else ("🟡" if stock <= 5 else "🟢")
        text += f"📦 Omborda: {mark} <b>{stock}</b> ta\n"
    text += f"\n⭐ {p['rating']} ({p['reviews']} baho)"

    kb = product_edit_kb(p["id"])

    # Rasm Firebase Storage'da (to'liq URL) yoki eski lokal fayl bo'lishi mumkin
    images = p.get("images") or []
    if images:
        first = images[0]
        try:
            if str(first).startswith("http"):
                await callback.message.delete()
                await bot.send_photo(
                    callback.from_user.id, photo=first,
                    caption=text, reply_markup=kb, parse_mode="HTML"
                )
                return
            img_path = os.path.join(IMAGES_DIR, first)
            if os.path.exists(img_path):
                await callback.message.delete()
                await bot.send_photo(
                    callback.from_user.id, photo=FSInputFile(img_path),
                    caption=text, reply_markup=kb, parse_mode="HTML"
                )
                return
        except Exception as e:
            print(f"[WARN] Mahsulot rasmini yuborib bo'lmadi: {e}")

    await safe_edit(callback, text, kb)


@router.callback_query(F.data.startswith("prod_del_"))
async def cb_delete_product(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    prod_id = callback.data.split("prod_del_")[-1]
    p = db.get_product_by_id(prod_id)
    name = p["name"] if p else "Noma'lum"
    db.delete_product(prod_id)
    await callback.answer(f"🗑 {name} o'chirildi")
    await cb_products(callback)


# ─── Add Product Flow ────────────────────────────────────────

@router.callback_query(F.data == "admin_add_product")
async def cb_add_product_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    cats = db.get_categories()
    if not cats:
        await safe_edit_msg(callback, 
            "⚠️ Avval kamida bitta kategoriya qo'shing!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Kategoriya qo'shish", callback_data="admin_add_category")],
                [InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")]
            ]),
            parse_mode="HTML"
        )
        return

    buttons = [[InlineKeyboardButton(text=c["name"], callback_data=f"addprod_cat_{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_menu")])

    await safe_edit_msg(callback, 
        "📦 <b>Yangi mahsulot</b>\n\n1️⃣ Kategoriyani tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("addprod_cat_"))
async def cb_add_product_category(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    cat_id = callback.data.split("addprod_cat_")[-1]
    cat = db.get_category_by_id(cat_id)
    if not cat:
        await callback.answer("Kategoriya topilmadi")
        return

    await state.update_data(category=cat["name"], images=[])
    await state.set_state(AddProduct.name)
    await safe_edit_msg(callback, 
        f"📦 <b>Yangi mahsulot</b>\n\n"
        f"📂 Kategoriya: <b>{cat['name']}</b>\n\n"
        f"2️⃣ Mahsulot nomini yozing:",
        parse_mode="HTML"
    )


@router.message(AddProduct.name)
async def process_product_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProduct.price)
    await message.answer(
        f"✅ Nom: <b>{message.text.strip()}</b>\n\n"
        f"3️⃣ Narxni kiriting (faqat raqam, so'mda):\n"
        f"Masalan: <code>150000</code>",
        parse_mode="HTML"
    )


@router.message(AddProduct.price)
async def process_product_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting! Masalan: 150000")
        return
    await state.update_data(price=price)
    await state.set_state(AddProduct.old_price)
    await message.answer(
        f"✅ Narx: <b>{db.format_price(price)}</b>\n\n"
        f"4️⃣ Eski narxni kiriting (chegirma uchun).",
        reply_markup=skip_kb("old_price"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "skip_old_price")
async def cb_skip_old_price(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.update_data(oldPrice=None)
    await state.set_state(AddProduct.description)
    await safe_edit_msg(callback, callback.message.html_text)
    await callback.message.answer(
        "5️⃣ Mahsulot tavsifini yozing:",
        reply_markup=skip_kb("desc"),
        parse_mode="HTML"
    )


@router.message(AddProduct.old_price)
async def process_old_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    old_price = None
    if text != "-":
        try:
            old_price = int(text.replace(" ", "").replace(",", ""))
        except ValueError:
            await message.answer("❌ Faqat raqam kiriting!")
            return
    await state.update_data(oldPrice=old_price)
    await state.set_state(AddProduct.description)
    await message.answer(
        "5️⃣ Mahsulot tavsifini yozing:",
        reply_markup=skip_kb("desc"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "skip_desc")
async def cb_skip_desc(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.update_data(description="")
    await state.set_state(AddProduct.sizes)
    await safe_edit_msg(callback, callback.message.html_text)
    await callback.message.answer(
        "6️⃣ Hajmlarni vergul bilan yozing.\nMasalan: <code>300 ml, 500 ml</code>",
        reply_markup=skip_kb("sizes"),
        parse_mode="HTML"
    )


@router.message(AddProduct.description)
async def process_description(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    desc = text if text != "-" else ""
    await state.update_data(description=desc)
    await state.set_state(AddProduct.sizes)
    await message.answer(
        "6️⃣ Hajmlarni vergul bilan yozing.\nMasalan: <code>300 ml, 500 ml</code>",
        reply_markup=skip_kb("sizes"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "skip_sizes")
async def cb_skip_sizes(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.update_data(sizes=[])
    await state.set_state(AddProduct.color)
    await safe_edit_msg(callback, callback.message.html_text)
    await callback.message.answer(
        "7️⃣ Ta'mlarni vergul bilan yozing.\nMasalan: <code>Limon-Yalpiz, Anor, Kola</code>",
        reply_markup=skip_kb("color"),
        parse_mode="HTML"
    )


@router.message(AddProduct.sizes)
async def process_sizes(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    sizes = [s.strip() for s in text.split(",")] if text != "-" else []
    await state.update_data(sizes=sizes)
    await state.set_state(AddProduct.color)
    await message.answer(
        "7️⃣ Ta'mlarni vergul bilan yozing.\nMasalan: <code>Limon-Yalpiz, Anor, Kola</code>",
        reply_markup=skip_kb("color"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "skip_color")
async def cb_skip_color(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.update_data(color="")
    await state.set_state(AddProduct.discount)
    await safe_edit_msg(callback, callback.message.html_text)
    await callback.message.answer(
        "8️⃣ Chegirma foizini yozing.\nMasalan: <code>-20%</code>",
        reply_markup=skip_kb("discount"),
        parse_mode="HTML"
    )


@router.message(AddProduct.color)
async def process_color(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    color = text if text != "-" else ""
    await state.update_data(color=color)
    await state.set_state(AddProduct.discount)
    await message.answer(
        "8️⃣ Chegirma foizini yozing.\nMasalan: <code>-20%</code>",
        reply_markup=skip_kb("discount"),
        parse_mode="HTML"
    )


ASK_STOCK = "9\ufe0f\u20e3 Omborda nechta bor? (faqat raqam)\nMasalan: <code>25</code>"
ASK_IMAGE = (
    "\U0001f51f Mahsulot rasmini yuboring \u2014 bu asosiy rasm bo'ladi.\n\n"
    "\u26a0\ufe0f <b>Fon shaffof (PNG) bo'lsa \u2014 albatta FAYL qilib yuboring:</b>\n"
    "\U0001f4ce \u2192 <b>Fayl</b> (Telegram Desktop'da \u00abRasmni siqish\u00bb belgisini olib tashlang).\n\n"
    "<i>Foto sifatida yuborilsa Telegram rasmni JPEG'ga siqadi va shaffof "
    "fonni OQ rangga aylantiradi \u2014 buni keyin tiklab bo'lmaydi.</i>"
)

# Foto sifatida kelgan rasmda shaffoflik allaqachon yo'qolgan bo'ladi.
COMPRESSED_WARNING = (
    "\u26a0\ufe0f <b>Diqqat:</b> rasm <b>foto</b> sifatida yuborildi. "
    "Telegram uni siqdi, shuning uchun shaffof fon <b>oq</b> bo'lib qoldi.\n\n"
    "Shaffofligi saqlanishi uchun o'sha rasmni <b>\U0001f4ce \u2192 Fayl</b> "
    "qilib qayta yuboring."
)


@router.callback_query(F.data == "skip_discount")
async def cb_skip_discount(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    await state.update_data(discount="")
    await state.set_state(AddProduct.stock)
    await safe_edit_msg(callback, callback.message.html_text)
    await callback.message.answer(ASK_STOCK, parse_mode="HTML")
    await callback.answer()


@router.message(AddProduct.discount)
async def process_discount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    discount = text if text != "-" else ""
    await state.update_data(discount=discount)
    await state.set_state(AddProduct.stock)
    await message.answer(ASK_STOCK, parse_mode="HTML")


@router.message(AddProduct.stock)
async def process_stock(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        stock = int(message.text.strip().replace(" ", ""))
        if stock < 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("Manfiy bo'lmagan butun son kiriting. Masalan: 25")
        return
    await state.update_data(stock=stock)
    await state.set_state(AddProduct.image)
    await message.answer(ASK_IMAGE, parse_mode="HTML")


# Rasm fayl sifatida ham yuborilishi mumkin — u holda Telegram uni
# siqmaydi va sifat saqlanadi. Shuning uchun ikkalasini ham qabul qilamiz.
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _looks_like_image(message: Message) -> bool:
    """Xabarda rasm bormi — foto yoki rasm fayli."""
    if message.photo:
        return True
    doc = message.document
    if not doc:
        return False
    if (doc.mime_type or "").startswith("image/"):
        return True
    name = (doc.file_name or "").lower()
    return any(name.endswith(ext) for ext in IMAGE_EXTENSIONS)


async def _download_image(message: Message, bot: Bot) -> str | None:
    """
    Rasmni yuklab, saqlangan fayl nomini qaytaradi.
    Foto ham, rasm fayli (document) ham qo'llab-quvvatlanadi.
    """
    ext = "jpg"

    if message.photo:
        file_id = message.photo[-1].file_id       # eng yuqori sifat
    elif message.document:
        file_id = message.document.file_id
        name = (message.document.file_name or "").lower()
        for candidate in IMAGE_EXTENSIONS:
            if name.endswith(candidate):
                ext = candidate.lstrip(".")
                break
    else:
        return None

    try:
        file = await bot.get_file(file_id)
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)
        await bot.download_file(file.file_path, filepath)
        return filename
    except Exception as e:
        print(f"[ERR] Rasmni yuklab bo'lmadi: {e}")
        return None


async def _accept_image(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    filename = await _download_image(message, bot)
    if not filename:
        await message.answer(
            "Rasmni yuklab bo'lmadi. Fayl juda katta bo'lmasin (20 MB gacha) "
            "va qaytadan yuboring."
        )
        return

    data = await state.get_data()
    images = data.get("images", [])
    images.append(filename)
    await state.update_data(images=images)

    # Foto sifatida kelgan bo'lsa shaffoflik yo'qolgan — jim o'tib ketmaymiz
    if message.photo:
        await message.answer(COMPRESSED_WARNING, parse_mode="HTML")

    await state.set_state(AddProduct.more_images)
    await message.answer(
        f"\u2705 Rasm saqlandi! ({len(images)} ta rasm)\n\nYana rasm qo'shmoqchimisiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="\U0001f4f7 Yana rasm qo'shish", callback_data="addprod_more_img")],
            [InlineKeyboardButton(text="\u2705 Tayyor \u2014 saqlash", callback_data="addprod_save")],
        ]),
        parse_mode="HTML",
    )


@router.message(AddProduct.image, F.photo)
async def process_image_photo(message: Message, state: FSMContext, bot: Bot):
    await _accept_image(message, state, bot)


@router.message(AddProduct.image, F.document)
async def process_image_document(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if not _looks_like_image(message):
        await message.answer(
            "Bu rasm fayli emas. JPG, PNG yoki WEBP yuboring."
        )
        return
    await _accept_image(message, state, bot)


@router.message(AddProduct.image)
async def process_image_invalid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "Iltimos, mahsulot rasmini yuboring.\n"
        "Rasm sifatida ham, fayl sifatida ham yuborsangiz bo'ladi "
        "(fayl sifatida yuborsangiz sifat yaxshiroq saqlanadi)."
    )


@router.callback_query(F.data == "addprod_more_img")
async def cb_more_images(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    await state.set_state(AddProduct.image)
    await safe_edit_msg(callback, 
        "\U0001f4f7 Keyingi rasmni yuboring.\n\n"
        "\u26a0\ufe0f Fon shaffof bo'lsa \u2014 \U0001f4ce \u2192 <b>Fayl</b> qilib yuboring, "
        "aks holda fon oq bo'lib qoladi.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddProduct.more_images, F.photo)
async def process_more_image_photo(message: Message, state: FSMContext, bot: Bot):
    await _accept_image(message, state, bot)


@router.message(AddProduct.more_images, F.document)
async def process_more_image_document(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if not _looks_like_image(message):
        await message.answer("Bu rasm fayli emas. JPG, PNG yoki WEBP yuboring.")
        return
    await _accept_image(message, state, bot)


@router.callback_query(F.data == "addprod_save")
async def cb_save_product(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    product = db.add_product(data)
    await state.clear()

    text = (
        f"✅ <b>Mahsulot qo'shildi!</b>\n\n"
        f"📦 {product['name']}\n"
        f"💰 {db.format_price(product['price'])}\n"
        f"📂 {product['category']}\n"
        f"🖼 {len(product.get('images', []))} ta rasm\n"
    )

    await safe_edit_msg(callback, 
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Yana mahsulot qo'shish", callback_data="admin_add_product")],
            [InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")],
        ]),
        parse_mode="HTML"
    )


# ─── Broadcast (Ommaviy xabar) ───────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(BroadcastMenu.message)
    await safe_edit_msg(callback, 
        "📢 <b>Ommaviy xabarnoma</b>\n\nFoydalanuvchilarga yubormoqchi bo'lgan xabarni kiriting (yoki /cancel yozing):",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )

@router.message(BroadcastMenu.message)
async def process_broadcast_message(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")]]))
        return

    body = message.html_text or message.text or ""
    if not body.strip():
        await message.answer("Xabar matni bo'sh. Qaytadan yozing yoki /cancel.")
        return

    users = db.get_all_users()
    await state.clear()

    progress = await message.answer(f"Yuborilmoqda... (0/{len(users)})")

    sent = blocked = failed = 0
    for i, u in enumerate(users, 1):
        user_id = u.get("id")
        if not user_id:
            continue
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            continue

        # 1) Mini appdagi bildirishnomalar ro'yxatiga
        try:
            db.send_notification(uid, "Xabarnoma", message.text or body, "system")
        except Exception as e:
            print(f"[BROADCAST] notification xatosi {uid}: {e}")

        # 2) Telegram xabari — avval buni qilmasdik, admin esa
        #    "yuborildi" degan yolg'on tasdiq olardi (F-22)
        try:
            await bot.send_message(uid, body, parse_mode="HTML")
            sent += 1
        except TelegramForbiddenError:
            blocked += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(uid, body, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
        except Exception as e:
            print(f"[BROADCAST] {uid}: {e}")
            failed += 1

        # Telegram limiti ~30 xabar/sekund
        await asyncio.sleep(0.05)

        if i % 25 == 0:
            try:
                await progress.edit_text(f"Yuborilmoqda... ({i}/{len(users)})")
            except Exception:
                pass

    report = (
        "\U0001f4e2 <b>Xabarnoma yakunlandi</b>\n\n"
        f"\u2705 Yetkazildi: <b>{sent}</b>\n"
        f"\U0001f6ab Botni bloklagan: <b>{blocked}</b>\n"
        f"\u26a0\ufe0f Xatolik: <b>{failed}</b>\n\n"
        "<i>Barchasi mini appdagi bildirishnomalarda ham ko'rinadi.</i>"
    )
    try:
        await progress.edit_text(report, parse_mode="HTML", reply_markup=back_to_menu_kb())
    except Exception:
        await message.answer(report, parse_mode="HTML", reply_markup=back_to_menu_kb())


# ─── Promocodes (Promokodlar) ────────────────────────────────

@router.callback_query(F.data == "admin_promocodes")
async def cb_promocodes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    codes = db.get_promocodes()
    text = "🎟 <b>Promokodlar</b>\n\n"
    if not codes:
        text += "Hozircha promokodlar yo'q."
    else:
        for c in codes:
            text += f"▪️ <b>{c.get('code', '')}</b> - {c.get('discountPercent', 0)}% chegirma (Faol: {'✅' if c.get('active', True) else '❌'})\n"
    
    buttons = [
        [InlineKeyboardButton(text="➕ Promokod qo'shish", callback_data="admin_add_promo")],
        [InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")]
    ]
    await safe_edit_msg(callback, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data == "admin_add_promo")
async def cb_add_promo(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddPromo.code)
    await safe_edit_msg(callback, "🎟 Yangi promokodni kiriting (masalan: NEWYEAR2026):", reply_markup=back_to_menu_kb())


@router.message(AddPromo.code)
async def process_promo_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(code=message.text.upper())
    await state.set_state(AddPromo.discount)
    await message.answer("Endi chegirma foizini kiriting (raqamda, masalan: 10):")


@router.message(AddPromo.discount)
async def process_promo_discount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        discount = int(message.text)
    except ValueError:
        await message.answer("Iltimos, faqat raqam kiriting!")
        return

    data = await state.get_data()
    db.add_promocode(data['code'], discount)
    await state.clear()
    await message.answer(f"✅ Promokod <b>{data['code']}</b> ({discount}%) saqlandi!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Admin panel", callback_data="admin_menu")]]))


# ─── Mahsulotni tahrirlash (F-24) ────────────────────────────
#
# Ilgari narxni o'zgartirish uchun mahsulotni o'chirib, 9 bosqichli
# formani boshidan to'ldirish kerak edi — rasmlarini ham qaytadan.

# maydon -> (so'rov matni, ko'rsatiladigan nom, turi)
#   turi: "text" | "int" | "list" | "int_or_empty"
EDIT_FIELDS = {
    "name": ("Yangi nomni yozing:", "Nom", "text"),
    "price": ("Yangi narxni yozing (faqat raqam):", "Narx", "int"),
    "oldPrice": (
        "Eski narxni yozing (chegirmani ko'rsatish uchun).\n"
        "Olib tashlash uchun <code>-</code> yuboring:",
        "Eski narx", "int_or_empty",
    ),
    "stock": ("Ombordagi yangi qoldiqni yozing (faqat raqam):", "Qoldiq", "int"),
    "description": ("Yangi tavsifni yozing:", "Tavsif", "text"),
    "discount": (
        "Chegirma yorlig'ini yozing, masalan <code>-20%</code>.\n"
        "Olib tashlash uchun <code>-</code> yuboring:",
        "Chegirma", "text_or_empty",
    ),
    "sizes": (
        "Hajmlarni vergul bilan yozing, masalan <code>300 ml, 500 ml</code>.\n"
        "Olib tashlash uchun <code>-</code> yuboring:",
        "Hajmlar", "list",
    ),
    "color": (
        "Ta'mlarni vergul bilan yozing, masalan <code>Limon-Yalpiz, Anor</code>.\n"
        "Olib tashlash uchun <code>-</code> yuboring:",
        "Ta'mlar", "text_or_empty",
    ),
}


def format_field_value(field: str, value) -> str:
    """Maydonning hozirgi qiymatini o'qiladigan ko'rinishda."""
    if value in (None, "", []):
        return "—"
    if field in ("price", "oldPrice"):
        return db.format_price(value)
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


@router.callback_query(F.data.startswith("pedit_"))
async def cb_edit_product_field(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    rest = callback.data[len("pedit_"):]
    field, _, prod_id = rest.partition("_")
    if field not in EDIT_FIELDS:
        await callback.answer("Noma'lum maydon")
        return

    product = db.get_product_by_id(prod_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    prompt, label, _kind = EDIT_FIELDS[field]
    shown_current = format_field_value(field, product.get(field))
    product_name = product.get("name", "")

    await state.update_data(edit_prod_id=prod_id, edit_field=field)
    await state.set_state(EditProduct.value)

    await callback.message.answer(
        f"\u270f\ufe0f <b>{product_name}</b>\n"
        f"{label} \u2014 hozirgi qiymat: <b>{shown_current}</b>\n\n"
        f"{prompt}\n\n<i>Bekor qilish uchun /cancel</i>",
        parse_mode="HTML",
    )
    await callback.answer()


def parse_field_value(field: str, raw: str):
    """
    Kiritilgan matnni maydon turiga qarab tekshiradi.
    (qiymat, xato_matni) qaytaradi — xato bo'lsa qiymat None.
    """
    _prompt, _label, kind = EDIT_FIELDS[field]
    cleared = raw.strip() == "-"

    if kind == "int":
        try:
            value = int(raw.replace(" ", "").replace(",", ""))
            if value < 0:
                raise ValueError
            return value, None
        except ValueError:
            return None, "Manfiy bo'lmagan butun son kiriting."

    if kind == "int_or_empty":
        if cleared:
            return None, None          # maydon tozalanadi
        try:
            value = int(raw.replace(" ", "").replace(",", ""))
            if value < 0:
                raise ValueError
            return value, None
        except ValueError:
            return None, "Raqam kiriting yoki tozalash uchun - yuboring."

    if kind == "list":
        if cleared:
            return [], None
        items = [x.strip() for x in raw.split(",") if x.strip()]
        if not items:
            return None, "Kamida bitta qiymat kiriting yoki - yuboring."
        return items, None

    if kind == "text_or_empty":
        return ("" if cleared else raw), None

    # oddiy matn
    if not raw:
        return None, "Bo'sh qiymat qabul qilinmaydi."
    return raw, None


@router.message(EditProduct.value)
async def process_edit_value(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    raw = (message.text or "").strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=back_to_menu_kb())
        return

    data = await state.get_data()
    prod_id = data.get("edit_prod_id")
    field = data.get("edit_field")

    if field not in EDIT_FIELDS:
        await state.clear()
        await message.answer("Tahrirlash bekor qilindi.", reply_markup=back_to_menu_kb())
        return

    value, error = parse_field_value(field, raw)
    if error:
        await message.answer(error)
        return

    if not db.update_product(prod_id, {field: value}):
        await state.clear()
        await message.answer("Mahsulot topilmadi yoki yangilanmadi.", reply_markup=back_to_menu_kb())
        return

    await state.clear()
    await message.answer(
        f"\u2705 <b>{EDIT_FIELDS[field][1]}</b> yangilandi: "
        f"<b>{format_field_value(field, value)}</b>\n\n"
        "<i>O'zgarish mini appda darhol ko'rinadi.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="\U0001f4e6 Mahsulotga qaytish", callback_data=f"prod_view_{prod_id}")],
            [InlineKeyboardButton(text="\u25c0\ufe0f Admin panel", callback_data="admin_menu")],
        ]),
    )


# ─── Kategoriyani o'zgartirish ───────────────────────────────

@router.callback_query(F.data.startswith("pcat_"))
async def cb_edit_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    prod_id = callback.data[len("pcat_"):]
    product = db.get_product_by_id(prod_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    cats = db.get_categories()
    if not cats:
        await callback.answer("Avval kategoriya qo'shing", show_alert=True)
        return

    current = product.get("category", "")
    rows = []
    for c in cats:
        mark = "\u2713 " if c["name"] == current else ""
        rows.append([InlineKeyboardButton(
            text=f"{mark}{c['name']}",
            callback_data=f"pcatset_{c['id']}_{prod_id}",
        )])
    rows.append([InlineKeyboardButton(text="\u21a9\ufe0f Orqaga", callback_data=f"prod_view_{prod_id}")])

    product_name = product.get("name", "")
    current_label = current or "—"

    await safe_edit(
        callback,
        f"📂 <b>{product_name}</b>\n\n"
        f"Hozirgi kategoriya: <b>{current_label}</b>\n\nYangisini tanlang:",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pcatset_"))
async def cb_set_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    rest = callback.data[len("pcatset_"):]
    cat_id, _, prod_id = rest.partition("_")

    cat = db.get_category_by_id(cat_id)
    if not cat:
        await callback.answer("Kategoriya topilmadi", show_alert=True)
        return

    if db.update_product(prod_id, {"category": cat["name"]}):
        await callback.answer(f"Kategoriya: {cat['name']}")
    else:
        await callback.answer("Yangilanmadi", show_alert=True)

    await cb_view_product(callback, callback.bot)


# ─── Rasmlarni boshqarish ────────────────────────────────────

@router.callback_query(F.data.startswith("pimg_"))
async def cb_edit_images(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    prod_id = callback.data[len("pimg_"):]
    product = db.get_product_by_id(prod_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    images = product.get("images") or []
    rows = []
    for i, _img in enumerate(images):
        label = "Asosiy rasm" if i == 0 else f"{i + 1}-rasm"
        row = [InlineKeyboardButton(text=f"\U0001f5d1 {label}", callback_data=f"pimgdel_{i}_{prod_id}")]
        if i > 0:
            row.append(InlineKeyboardButton(text="\u2b06\ufe0f Asosiy qilish", callback_data=f"pimgmain_{i}_{prod_id}"))
        rows.append(row)

    rows.append([InlineKeyboardButton(text="\u2795 Rasm qo'shish", callback_data=f"pimgadd_{prod_id}")])
    rows.append([InlineKeyboardButton(text="\u21a9\ufe0f Orqaga", callback_data=f"prod_view_{prod_id}")])

    text = f"\U0001f5bc <b>{product.get('name', '')}</b>\n\n"
    text += f"Rasmlar soni: <b>{len(images)}</b>\n\n"
    text += "<i>Birinchi rasm katalogda ko'rinadi. O'chirish uchun rasm nomini bosing.</i>"

    await safe_edit(callback, text, InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("pimgdel_"))
async def cb_delete_image(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    rest = callback.data[len("pimgdel_"):]
    index_str, _, prod_id = rest.partition("_")

    product = db.get_product_by_id(prod_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    images = list(product.get("images") or [])
    try:
        index = int(index_str)
        images.pop(index)
    except (ValueError, IndexError):
        await callback.answer("Rasm topilmadi", show_alert=True)
        return

    if not images:
        await callback.answer("Kamida bitta rasm qolishi kerak", show_alert=True)
        return

    db.update_product(prod_id, {"images": images})
    await callback.answer("Rasm o'chirildi")
    await cb_edit_images(callback, None)


@router.callback_query(F.data.startswith("pimgmain_"))
async def cb_make_main_image(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    rest = callback.data[len("pimgmain_"):]
    index_str, _, prod_id = rest.partition("_")

    product = db.get_product_by_id(prod_id)
    if not product:
        await callback.answer("Mahsulot topilmadi", show_alert=True)
        return

    images = list(product.get("images") or [])
    try:
        index = int(index_str)
        images.insert(0, images.pop(index))
    except (ValueError, IndexError):
        await callback.answer("Rasm topilmadi", show_alert=True)
        return

    db.update_product(prod_id, {"images": images})
    await callback.answer("Asosiy rasm o'zgartirildi")
    await cb_edit_images(callback, None)


@router.callback_query(F.data.startswith("pimgadd_"))
async def cb_add_image_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    prod_id = callback.data[len("pimgadd_"):]
    await state.update_data(image_prod_id=prod_id)
    await state.set_state(EditProduct.image)
    await callback.message.answer(
        "\U0001f4f7 Yangi rasmni yuboring.\n\n"
        "\u26a0\ufe0f Fon shaffof (PNG) bo'lsa \u2014 \U0001f4ce \u2192 <b>Fayl</b> qilib "
        "yuboring, aks holda Telegram uni siqib fonni oq qilib qo'yadi.\n\n"
        "<i>Bekor qilish uchun /cancel</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(EditProduct.image, F.photo | F.document)
async def process_new_image(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    if message.document and not _looks_like_image(message):
        await message.answer("Bu rasm fayli emas. JPG, PNG yoki WEBP yuboring.")
        return

    if message.photo:
        await message.answer(COMPRESSED_WARNING, parse_mode="HTML")

    data = await state.get_data()
    prod_id = data.get("image_prod_id")
    product = db.get_product_by_id(prod_id)
    if not product:
        await state.clear()
        await message.answer("Mahsulot topilmadi.", reply_markup=back_to_menu_kb())
        return

    filename = await _download_image(message, bot)
    if not filename:
        await message.answer("Rasmni yuklab bo'lmadi. Qaytadan urinib ko'ring.")
        return

    # Lokal fayl Firebase Storage'ga yuklanadi va URL saqlanadi
    url = db.upload_image_to_firebase(os.path.join(IMAGES_DIR, filename))
    if not url:
        await message.answer("Rasmni saqlab bo'lmadi. Qaytadan urinib ko'ring.")
        return

    images = list(product.get("images") or []) + [url]
    db.update_product(prod_id, {"images": images})

    await state.clear()
    await message.answer(
        f"\u2705 Rasm qo'shildi. Jami: <b>{len(images)}</b> ta",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="\U0001f5bc Rasmlar", callback_data=f"pimg_{prod_id}")],
            [InlineKeyboardButton(text="\U0001f4e6 Mahsulotga qaytish", callback_data=f"prod_view_{prod_id}")],
        ]),
    )


@router.message(EditProduct.image)
async def process_new_image_invalid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if (message.text or "").strip() == "/cancel":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=back_to_menu_kb())
        return
    await message.answer("Rasm yuboring (rasm yoki fayl sifatida) yoki /cancel.")


# ─── Buyurtmalar ro'yxati (F-24) ─────────────────────────────

ORDER_STATUS_FILTERS = [
    ("all", "Barchasi"),
    ("Yangi", "\U0001f7e1 Yangi"),
    ("Qabul qilindi", "\U0001f7e2 Qabul qilingan"),
    ("Yetkazilmoqda", "\U0001f69a Yo'lda"),
    ("Yetkazildi", "\U0001f389 Yetkazilgan"),
]


def orders_filter_kb(active: str) -> InlineKeyboardMarkup:
    rows, row = [], []
    for value, label in ORDER_STATUS_FILTERS:
        mark = "\u2022 " if value == active else ""
        row.append(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"orders_{value}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="\u25c0\ufe0f Admin panel", callback_data="admin_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "admin_orders")
async def cb_orders(callback: CallbackQuery):
    await show_orders(callback, "all")


@router.callback_query(F.data.startswith("orders_"))
async def cb_orders_filtered(callback: CallbackQuery):
    await show_orders(callback, callback.data[len("orders_"):])


async def show_orders(callback: CallbackQuery, status: str):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    orders = db.get_orders(None if status == "all" else status, limit=10)

    label = dict(ORDER_STATUS_FILTERS).get(status, "Barchasi")
    text = f"\U0001f6d2 <b>Buyurtmalar \u2014 {label}</b>\n"
    text += "\u2501" * 22 + "\n\n"

    if not orders:
        text += "Bu bo'limda buyurtma yo'q."
    else:
        for o in orders:
            total = o.get("total", 0)
            total_str = db.format_price(total) if isinstance(total, (int, float)) else str(total)
            customer = o.get("customer", {})
            text += f"\U0001f9fe <b>{db.order_display_id(o)}</b> \u2014 {o.get('status', 'Yangi')}\n"
            text += f"\U0001f4c5 {db.order_date_text(o)}\n"
            cust_name = customer.get("name") or "—"
            cust_phone = customer.get("phone") or "—"
            text += f"👤 {cust_name} • <code>{cust_phone}</code>\n"
            text += f"\U0001f4b0 <b>{total_str}</b>"
            if o.get("paymentMethod") == "Karta":
                pay = o.get("paymentStatus") or "Kutilmoqda"
                text += f" \u2022 \U0001f4b3 {pay}"
            text += "\n\n"
        text += f"<i>Oxirgi {len(orders)} ta ko'rsatildi.</i>"

    kb = orders_filter_kb(status)
    if orders:
        # Har bir buyurtma uchun ochish tugmasi — ro'yxatning tepasiga
        rows = []
        for o in orders:
            rows.append([InlineKeyboardButton(
                text=f"{db.order_display_id(o)} \u2014 {o.get('status', 'Yangi')}",
                callback_data=f"ordv_{o.get('_doc_id', '')}",
            )])
        kb = InlineKeyboardMarkup(inline_keyboard=rows + kb.inline_keyboard)

    try:
        await safe_edit_msg(callback, text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ─── Bitta buyurtma: tafsilot va o'chirish ───────────────────

@router.callback_query(F.data.startswith("ordv_"))
async def cb_order_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    doc_id = callback.data[len("ordv_"):]
    order = db.get_order_by_id(doc_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return

    customer = order.get("customer", {})
    total = order.get("total", 0)
    total_str = db.format_price(total) if isinstance(total, (int, float)) else str(total)

    text = f"\U0001f9fe <b>Buyurtma {db.order_display_id(order)}</b>\n"
    text += "\u2501" * 22 + "\n\n"
    text += f"\U0001f4c5 {db.order_date_text(order)}\n"
    text += f"\U0001f4ca Holat: <b>{order.get('status', 'Yangi')}</b>\n"

    if order.get("paymentMethod") == "Karta":
        text += f"\U0001f4b3 To'lov: Karta \u2014 {order.get('paymentStatus') or 'Kutilmoqda'}\n"
    else:
        text += "\U0001f4b5 To'lov: Naqd (yetkazganda)\n"

    cust_name = customer.get("name") or "\u2014"
    cust_phone = customer.get("phone") or "\u2014"
    cust_addr = customer.get("address") or "\u2014"
    text += f"\n\U0001f464 <b>Ism:</b> {cust_name}\n"
    text += f"\U0001f4de <b>Tel:</b> <code>{cust_phone}</code>\n"
    text += f"\U0001f4cd <b>Manzil:</b> {cust_addr}\n"
    if customer.get("comment"):
        text += f"\U0001f4ac <b>Izoh:</b> {customer['comment']}\n"

    text += "\n\U0001f4e6 <b>Mahsulotlar:</b>\n"
    for i, item in enumerate(order.get("products", []), 1):
        prod = item.get("product") or item
        variant = []
        if item.get("size"):
            variant.append(f"Hajm: {item['size']}")
        if item.get("color"):
            variant.append(f"Ta'm: {item['color']}")
        var_text = f" ({', '.join(variant)})" if variant else ""
        qty = item.get("quantity", 1)
        price = prod.get("price", 0)
        text += f"  {i}. {prod.get('name', '?')}{var_text} \u2014 {qty} ta \u00d7 {db.format_price(price)}\n"

    text += "\n" + "\u2501" * 22 + "\n"
    text += f"\U0001f4b0 <b>Jami: {total_str}</b>\n"
    text += f"\n<code>{doc_id}</code>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001f5d1 O'chirish", callback_data=f"orddel_{doc_id}")],
        [InlineKeyboardButton(text="\u25c0\ufe0f Buyurtmalar", callback_data="admin_orders")],
    ])

    try:
        await safe_edit_msg(callback, text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("orddel_"))
async def cb_order_delete_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    doc_id = callback.data[len("orddel_"):]
    order = db.get_order_by_id(doc_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return

    await safe_edit_msg(callback, 
        f"\u26a0\ufe0f <b>Buyurtma {db.order_display_id(order)} o'chirilsinmi?</b>\n\n"
        "Bu amalni ortga qaytarib bo'lmaydi \u2014 buyurtma butunlay o'chadi.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="\U0001f5d1 Ha, o'chirilsin", callback_data=f"orddelok_{doc_id}")],
            [InlineKeyboardButton(text="\u21a9\ufe0f Bekor qilish", callback_data=f"ordv_{doc_id}")],
        ]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("orddelok_"))
async def cb_order_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    doc_id = callback.data[len("orddelok_"):]
    if db.delete_order(doc_id):
        await callback.answer("O'chirildi", show_alert=True)
    else:
        await callback.answer("Buyurtma topilmadi", show_alert=True)

    await show_orders(callback, "all")


# ─── Yetkazib berish sozlamalari ─────────────────────────────

@router.callback_query(F.data == "admin_delivery")
async def cb_delivery(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    settings = db.get_delivery_settings()
    fee = settings["fee"]
    free_from = settings["freeFrom"]

    text = "\U0001f69a <b>Yetkazib berish</b>\n\n"
    text += f"Narx: <b>{db.format_price(fee) if fee else 'Bepul'}</b>\n"
    if free_from:
        text += f"Bepul yetkazish: <b>{db.format_price(free_from)}</b>dan yuqori buyurtmalarga\n"
    else:
        text += "Bepul yetkazish chegarasi: <b>yo'q</b>\n"
    text += "\n<i>Bu qiymatlar mini appdagi hisob-kitobda va buyurtma summasida ishlatiladi.</i>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\u270f\ufe0f O'zgartirish", callback_data="delivery_edit")],
        [InlineKeyboardButton(text="\u25c0\ufe0f Admin panel", callback_data="admin_menu")],
    ])
    try:
        await safe_edit_msg(callback, text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "delivery_edit")
async def cb_delivery_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    await state.set_state(DeliverySettings.fee)
    await callback.message.answer(
        "\U0001f69a Yetkazib berish narxini yozing (so'mda, faqat raqam).\n"
        "Bepul bo'lsa <code>0</code> yozing:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(DeliverySettings.fee)
async def process_delivery_fee(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        fee = int((message.text or "").strip().replace(" ", "").replace(",", ""))
        if fee < 0:
            raise ValueError
    except ValueError:
        await message.answer("Manfiy bo'lmagan butun son kiriting.")
        return

    await state.update_data(fee=fee)
    await state.set_state(DeliverySettings.free_from)
    await message.answer(
        "Endi bepul yetkazish chegarasini yozing.\n"
        "Masalan <code>500000</code> \u2014 shu summadan yuqori buyurtmalar bepul.\n"
        "Chegara kerak bo'lmasa <code>0</code> yozing:",
        parse_mode="HTML",
    )


@router.message(DeliverySettings.free_from)
async def process_delivery_free_from(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        free_from = int((message.text or "").strip().replace(" ", "").replace(",", ""))
        if free_from < 0:
            raise ValueError
    except ValueError:
        await message.answer("Manfiy bo'lmagan butun son kiriting.")
        return

    data = await state.get_data()
    fee = data.get("fee", 0)
    db.update_delivery_settings(fee, free_from)
    await state.clear()

    text = "\u2705 <b>Yetkazib berish sozlamalari saqlandi</b>\n\n"
    text += f"Narx: <b>{db.format_price(fee) if fee else 'Bepul'}</b>\n"
    if free_from:
        text += f"Bepul: <b>{db.format_price(free_from)}</b>dan yuqori buyurtmalarga"
    else:
        text += "Bepul yetkazish chegarasi: yo'q"

    await message.answer(text, parse_mode="HTML", reply_markup=back_to_menu_kb())


# ─── Sotuv hisoboti ──────────────────────────────────────────

REPORT_PERIODS = [(1, "Bugun"), (7, "7 kun"), (30, "30 kun")]


def report_kb(active: int) -> InlineKeyboardMarkup:
    row = []
    for days, label in REPORT_PERIODS:
        mark = "\u2022 " if days == active else ""
        row.append(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"report_{days}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        row,
        [InlineKeyboardButton(text="\u25c0\ufe0f Admin panel", callback_data="admin_menu")],
    ])


@router.callback_query(F.data.startswith("report_"))
async def cb_sales_report(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    try:
        days = int(callback.data[len("report_"):])
    except ValueError:
        days = 7

    await callback.answer("Hisoblanmoqda...")
    r = db.get_sales_report(days)

    label = dict(REPORT_PERIODS).get(days, f"{days} kun")

    text = f"\U0001f4c8 <b>Sotuv hisoboti \u2014 {label}</b>\n"
    text += "\u2501" * 22 + "\n\n"

    if r["orders"] == 0:
        text += "Bu davrda buyurtma bo'lmagan."
        await safe_edit(callback, text, report_kb(days))
        return

    text += f"\U0001f6d2 Buyurtmalar: <b>{r['orders']}</b>\n"
    text += f"\U0001f389 Yetkazilgan: <b>{r['delivered']}</b>\n"
    text += f"\u23f3 Jarayonda: <b>{r['pending']}</b>\n"
    if r["cancelled"]:
        text += f"\u274c Bekor qilingan: <b>{r['cancelled']}</b>\n"

    text += f"\n\U0001f465 Xaridorlar: <b>{r['new_customers']}</b>\n"
    text += f"\U0001f4b0 Savdo: <b>{db.format_price(r['revenue'])}</b>\n"
    if r["avg_check"]:
        text += f"\U0001f9fe O'rtacha chek: <b>{db.format_price(r['avg_check'])}</b>\n"

    if r["top_products"]:
        text += "\n\U0001f3c6 <b>Eng ko'p sotilgan:</b>\n"
        for i, item in enumerate(r["top_products"], 1):
            text += f"  {i}. {item['name']} \u2014 <b>{item['qty']} ta</b>"
            text += f" ({db.format_price(item['sum'])})\n"

    text += "\n<i>Savdo summasi faqat yetkazilgan buyurtmalar bo'yicha.</i>"

    await safe_edit(callback, text, report_kb(days))


# ─── Analitika (12-band) ─────────────────────────────────────

@router.callback_query(F.data.startswith("analytics_"))
async def cb_analytics(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    try:
        days = int(callback.data[len("analytics_"):])
    except ValueError:
        days = 7

    await callback.answer("Hisoblanmoqda...")
    a = db.get_analytics(days)

    label = dict(REPORT_PERIODS).get(days, f"{days} kun")

    text = f"\U0001f440 <b>Analitika \u2014 {label}</b>\n"
    text += "\u2501" * 22 + "\n\n"

    if not a["view"]:
        text += (
            "Hozircha ma'lumot yig'ilmagan.\n\n"
            "<i>Mijozlar mini appda mahsulotlarni ko'ra boshlagach "
            "shu yerda statistika paydo bo'ladi.</i>"
        )
        await safe_edit(callback, text, analytics_kb(days))
        return

    text += f"\U0001f441 Mahsulot ko'rishlar: <b>{a['view']}</b>\n"
    text += f"\U0001f6d2 Savatga qo'shishlar: <b>{a['cart_add']}</b>\n"
    text += f"\U0001f4b3 Rasmiylashtirishga o'tish: <b>{a['checkout_start']}</b>\n"

    if a["conversion"]:
        text += f"\n\U0001f4c9 Ko'rishdan savatga: <b>{a['conversion']}%</b>\n"

    if a["top_viewed"]:
        text += "\n\U0001f525 <b>Eng ko'p ko'rilgan:</b>\n"
        for i, item in enumerate(a["top_viewed"], 1):
            text += f"  {i}. {item['name']} \u2014 <b>{item['views']}</b> ko'rish"
            if item["cart_add"]:
                text += f", {item['cart_add']} savatga"
            text += "\n"

    await safe_edit(callback, text, analytics_kb(days))


def analytics_kb(active: int) -> InlineKeyboardMarkup:
    row = []
    for days, label in REPORT_PERIODS:
        mark = "\u2022 " if days == active else ""
        row.append(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"analytics_{days}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        row,
        [InlineKeyboardButton(text="\u25c0\ufe0f Admin panel", callback_data="admin_menu")],
    ])


# ─── Adminlarni boshqarish ───────────────────────────────────

def describe_user(user: dict) -> str:
    """Foydalanuvchini ko'rsatish uchun qisqa nom."""
    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    username = user.get("username")
    if name and username:
        return f"{name} (@{username})"
    if username:
        return f"@{username}"
    return name or f"ID {user.get('id')}"


@router.callback_query(F.data == "admin_admins")
async def cb_admins(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    await state.clear()
    ids = sorted(all_admins())

    text = f"\U0001f465 <b>Adminlar</b> ({len(ids)} ta)\n"
    text += "\u2501" * 22 + "\n\n"

    rows = []
    for uid in ids:
        user = db.get_user(uid) or {}
        label = describe_user({**user, "id": uid})
        owner = is_owner(uid)

        mark = "👑" if owner else "👤"
        text += mark + " " + label + "\n"
        text += "    <code>" + str(uid) + "</code>\n"

        if not owner:
            rows.append([InlineKeyboardButton(
                text=f"\U0001f5d1 {label[:28]}",
                callback_data=f"admdel_{uid}",
            )])

    text += "\n<i>\U0001f451 \u2014 egasi, uni o'chirib bo'lmaydi.</i>"

    rows.append([InlineKeyboardButton(text="\u2795 Admin qo'shish", callback_data="admin_add_admin")])
    rows.append([InlineKeyboardButton(text="\u25c0\ufe0f Admin panel", callback_data="admin_menu")])

    await safe_edit(callback, text, InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data == "admin_add_admin")
async def cb_add_admin(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    await state.set_state(AddAdmin.query)
    await callback.message.answer(
        "\u2795 <b>Admin qo'shish</b>\n\n"
        "Quyidagilardan birini yuboring:\n\n"
        "\u2022 Foydalanuvchi <b>ismi</b> yoki <b>@username</b> \u2014 "
        "botdan foydalanganlar ichidan qidiraman\n"
        "\u2022 Telegram <b>ID raqami</b>\n"
        "\u2022 O'sha odamning xabarini <b>forward</b> qiling\n\n"
        "<i>Bekor qilish uchun /cancel</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddAdmin.query)
async def process_add_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    raw = (message.text or "").strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=back_to_menu_kb())
        return

    # Forward qilingan xabardan
    forwarded = getattr(message, "forward_from", None)
    if forwarded:
        await finish_add_admin(message, state, forwarded.id, describe_user({
            "first_name": forwarded.first_name,
            "last_name": forwarded.last_name,
            "username": forwarded.username,
            "id": forwarded.id,
        }))
        return

    if not raw:
        await message.answer("Ism, @username yoki ID yuboring.")
        return

    # To'g'ridan-to'g'ri ID
    if raw.isdigit():
        uid = int(raw)
        user = db.get_user(uid) or {"id": uid}
        await finish_add_admin(message, state, uid, describe_user(user))
        return

    # Nom yoki username bo'yicha qidiramiz
    found = db.find_users(raw, limit=8)
    if not found:
        await message.answer(
            "Bunday foydalanuvchi topilmadi.\n\n"
            "<i>Faqat botdan foydalangan odamlarni qidira olaman. "
            "Topilmasa, uning Telegram ID raqamini yuboring yoki "
            "xabarini forward qiling.</i>",
            parse_mode="HTML",
        )
        return

    rows = [
        [InlineKeyboardButton(
            text=describe_user(u)[:40],
            callback_data=f"admadd_{u.get('id')}",
        )]
        for u in found
    ]
    rows.append([InlineKeyboardButton(text="\u274c Bekor qilish", callback_data="admin_admins")])

    await state.clear()
    await message.answer(
        f"\U0001f50d <b>{len(found)} ta foydalanuvchi topildi</b>\n\nAdmin qilmoqchi bo'lganingizni tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


async def finish_add_admin(message: Message, state: FSMContext, uid: int, label: str):
    await state.clear()

    if not admins_module.add(uid):
        await message.answer(
            f"<b>{label}</b> allaqachon admin.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        return

    await message.answer(
        f"\u2705 <b>{label}</b> admin qilindi.\n\n"
        "<i>U /start bosganda admin paneli tugmasi paydo bo'ladi.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="\U0001f465 Adminlar", callback_data="admin_admins")],
            [InlineKeyboardButton(text="\u25c0\ufe0f Admin panel", callback_data="admin_menu")],
        ]),
    )


@router.callback_query(F.data.startswith("admadd_"))
async def cb_confirm_add_admin(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    try:
        uid = int(callback.data[len("admadd_"):])
    except ValueError:
        await callback.answer("Noto'g'ri ID", show_alert=True)
        return

    user = db.get_user(uid) or {"id": uid}
    if admins_module.add(uid):
        await callback.answer(f"{describe_user(user)} admin qilindi")
    else:
        await callback.answer("Allaqachon admin", show_alert=True)

    await state.clear()
    await cb_admins(callback, state)


@router.callback_query(F.data.startswith("admdel_"))
async def cb_remove_admin(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    try:
        uid = int(callback.data[len("admdel_"):])
    except ValueError:
        await callback.answer("Noto'g'ri ID", show_alert=True)
        return

    if is_owner(uid):
        await callback.answer("Egani o'chirib bo'lmaydi", show_alert=True)
        return

    user = db.get_user(uid) or {"id": uid}
    if admins_module.remove(uid):
        await callback.answer(f"{describe_user(user)} adminlikdan olindi")
    else:
        await callback.answer("O'chirilmadi", show_alert=True)

    await cb_admins(callback, state)
