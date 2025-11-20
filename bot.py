import logging
import json
import os
import uuid

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================== CONFIG ==================
BOT_TOKEN = "8591422077:AAF9ITJeatmFQSySRiTyZRJtncyoRb3_kNQ"  # @BotFather se token
ADMIN_ID = 7459732827  # yaha apna Telegram numeric ID (int)

PLANS_FILE = "plans.json"

# ================== LOGGING ==================
logging.basicConfig(level=logging.INFO)

# ================== BOT INIT ==================
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ================== DATA HELPERS ==================
def load_plans():
    if not os.path.exists(PLANS_FILE):
        return []
    try:
        with open(PLANS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.exception(e)
        return []

def save_plans(plans):
    try:
        with open(PLANS_FILE, "w", encoding="utf-8") as f:
            json.dump(plans, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.exception(e)

# Global list
VPS_PLANS = load_plans()

def get_plan_by_id(plan_id: str):
    for p in VPS_PLANS:
        if p["id"] == plan_id:
            return p
    return None

def get_plans_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    if not VPS_PLANS:
        return kb
    for plan in VPS_PLANS:
        kb.add(
            InlineKeyboardButton(
                text=f"{plan['name']} ({plan['price_per_month']}/month)",
                callback_data=f"plan_{plan['id']}"
            )
        )
    return kb

# ================== STATES ==================
class BuyVPS(StatesGroup):
    waiting_for_duration = State()
    waiting_for_details = State()
    waiting_for_payment_proof = State()

class AdminAddPlan(StatesGroup):
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_description = State()

class AdminChangePrice(StatesGroup):
    waiting_for_new_price = State()

# ================== COMMON HANDLERS ==================

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    text = (
        "👋 <b>Welcome to VPS Shop Bot</b>\n\n"
        "Yaha se aap apni zaroorat ke hisaab se VPS khareed sakte ho.\n\n"
        "👇 Neeche button se plans dekh sakte ho."
    )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🧾 View VPS Plans", callback_data="show_plans"))
    await message.answer(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "show_plans")
async def show_plans(callback_query: types.CallbackQuery):
    await callback_query.answer()
    if not VPS_PLANS:
        await callback_query.message.edit_text(
            "❗ Abhi koi VPS plan add nahi hai.\n\n"
            "Admin /admin se plan add kar sakta hai."
        )
        return

    text = "<b>Available VPS Plans:</b>\n\n"
    for plan in VPS_PLANS:
        text += (
            f"🔹 <b>{plan['name']}</b>\n"
            f"💵 Price: {plan['price_per_month']} / month\n"
            f"📝 {plan['description']}\n\n"
        )
    text += "Kisi plan ko select karne ke liye neeche se choose karo 👇"

    await callback_query.message.edit_text(text, reply_markup=get_plans_keyboard())


@dp.callback_query_handler(lambda c: c.data.startswith("plan_"))
async def choose_plan(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    plan_id = callback_query.data.split("plan_")[1]
    plan = get_plan_by_id(plan_id)

    if not plan:
        await callback_query.message.answer("❌ Plan not found, please try again.")
        return

    await state.update_data(selected_plan=plan)

    text = (
        f"✅ <b>{plan['name']}</b> select kiya.\n"
        f"Price: {plan['price_per_month']} / month\n\n"
        "⏱ Kitne month ke liye VPS chahiye? (Example: 1, 3, 6, 12)"
    )
    await BuyVPS.waiting_for_duration.set()
    await callback_query.message.answer(text)


@dp.message_handler(state=BuyVPS.waiting_for_duration)
async def set_duration(message: types.Message, state: FSMContext):
    try:
        months = int(message.text.strip())
        if months <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Please valid number likho (1, 3, 6, 12, ...)")
        return

    data = await state.get_data()
    plan = data.get("selected_plan")

    total_price = int(plan["price_per_month"]) * months
    await state.update_data(duration_months=months, total_price=total_price)

    text = (
        f"🧮 Duration: <b>{months} month(s)</b>\n"
        f"💰 Total Price: <b>{total_price}</b>\n\n"
        "Ab apni details bhejo, format me:\n"
        "<code>Email: ...\n"
        "OS: (Ubuntu/Debian/Windows etc.)\n"
        "Extra notes: (Agar kuch special chahiye)</code>"
    )
    await BuyVPS.waiting_for_details.set()
    await message.answer(text)


@dp.message_handler(state=BuyVPS.waiting_for_details)
async def get_details(message: types.Message, state: FSMContext):
    details_text = message.text
    data = await state.get_data()
    plan = data.get("selected_plan")
    months = data.get("duration_months")
    total_price = data.get("total_price")

    await state.update_data(details_text=details_text)

    summary = (
        "<b>Order Summary:</b>\n\n"
        f"👤 User: {message.from_user.full_name} (@{message.from_user.username})\n"
        f"🆔 User ID: <code>{message.from_user.id}</code>\n\n"
        f"📦 Plan: <b>{plan['name']}</b>\n"
        f"⏱ Duration: <b>{months} month(s)</b>\n"
        f"💰 Total: <b>{total_price}</b>\n\n"
        f"📄 Details:\n<code>{details_text}</code>\n\n"
    )

    payment_info = (
        "💳 <b>Payment Instructions:</b>\n"
        "Yaha apni UPI / Bank details likho (code me edit karo):\n\n"
        "<code>UPI: your-upi-id@bank\n"
        "Name: Your Name\n"
        "Note: VPS + apna Telegram username likho</code>\n\n"
        "Payment karne ke baad, yaha <b>payment ka screenshot</b> (photo) bhejo."
    )

    await BuyVPS.waiting_for_payment_proof.set()
    await message.answer(summary + payment_info)


@dp.message_handler(content_types=types.ContentType.PHOTO, state=BuyVPS.waiting_for_payment_proof)
async def receive_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    plan = data.get("selected_plan")
    months = data.get("duration_months")
    total_price = data.get("total_price")
    details_text = data.get("details_text")

    caption = (
        "🆕 <b>New VPS Order</b>\n\n"
        f"👤 User: {message.from_user.full_name} (@{message.from_user.username})\n"
        f"🆔 User ID: <code>{message.from_user.id}</code>\n\n"
        f"📦 Plan: <b>{plan['name']}</b>\n"
        f"⏱ Duration: <b>{months} month(s)</b>\n"
        f"💰 Total: <b>{total_price}</b>\n\n"
        f"📄 Details:\n<code>{details_text}</code>\n\n"
        "📎 Payment screenshot attached."
    )

    photo = message.photo[-1]
    try:
        await bot.send_photo(chat_id=ADMIN_ID, photo=photo.file_id, caption=caption)
    except Exception as e:
        logging.exception(e)
        await message.answer("⚠ Payment admin ko forward karne me error aaya. ADMIN_ID check karo.")

    await message.answer(
        "✅ <b>Payment screenshot received!</b>\n\n"
        "Admin payment verify karega aur VPS details aapko DM karega. "
        "Agar delay ho to direct admin se contact karo."
    )
    await state.finish()


@dp.message_handler(state=BuyVPS.waiting_for_payment_proof)
async def not_photo_warning(message: types.Message):
    await message.answer("❗ Payment proof ke liye <b>photo</b> (screenshot) bhejo.")


@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    text = (
        "<b>VPS Shop Bot Commands:</b>\n"
        "/start - Bot start / menu\n"
        "/help - Help message\n"
        "/admin - (sirf admin) VPS plans manage karne ke liye"
    )
    await message.answer(text)

# ================== ADMIN PANEL ==================

def admin_main_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Add VPS Plan", callback_data="admin_add_plan"),
        InlineKeyboardButton("📜 List Plans", callback_data="admin_list_plans"),
    )
    kb.add(
        InlineKeyboardButton("💰 Change Price", callback_data="admin_change_price"),
        InlineKeyboardButton("🗑 Delete Plan", callback_data="admin_delete_plan"),
    )
    return kb


@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Ye command sirf admin ke liye hai.")
        return
    await message.answer(
        "<b>Admin Panel</b>\n\nYaha se VPS plans manage karo:",
        reply_markup=admin_main_keyboard()
    )

# ---------- LIST PLANS ----------

@dp.callback_query_handler(lambda c: c.data == "admin_list_plans")
async def admin_list_plans(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Not allowed", show_alert=True)
        return

    await callback_query.answer()
    if not VPS_PLANS:
        await callback_query.message.answer("📜 Abhi koi plan nahi hai.")
        return

    text = "<b>Current VPS Plans:</b>\n\n"
    for p in VPS_PLANS:
        text += (
            f"ID: <code>{p['id']}</code>\n"
            f"Name: <b>{p['name']}</b>\n"
            f"Price: {p['price_per_month']} / month\n"
            f"Desc: {p['description']}\n\n"
        )
    await callback_query.message.answer(text)

# ---------- ADD PLAN FLOW ----------

@dp.callback_query_handler(lambda c: c.data == "admin_add_plan")
async def admin_add_plan_start(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Not allowed", show_alert=True)
        return

    await callback_query.answer()
    await AdminAddPlan.waiting_for_name.set()
    await callback_query.message.answer("🆕 <b>New VPS Plan</b>\n\nPlan ka <b>name</b> bhejo (example: VPS 2GB RAM).")


@dp.message_handler(state=AdminAddPlan.waiting_for_name)
async def admin_add_plan_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await AdminAddPlan.waiting_for_price.set()
    await message.answer("💰 Is plan ka <b>price per month</b> bhejo (sirf number, example: 7).")


@dp.message_handler(state=AdminAddPlan.waiting_for_price)
async def admin_add_plan_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Valid number bhejo (price per month).")
        return

    await state.update_data(price=price)
    await AdminAddPlan.waiting_for_description.set()
    await message.answer("✏ Plan ka <b>description</b> bhejo (specs: CPU, RAM, SSD, bandwidth...).")


@dp.message_handler(state=AdminAddPlan.waiting_for_description)
async def admin_add_plan_description(message: types.Message, state: FSMContext):
    global VPS_PLANS

    data = await state.get_data()
    name = data.get("name")
    price = data.get("price")
    desc = message.text.strip()

    new_plan = {
        "id": str(uuid.uuid4())[:8],  # short id
        "name": name,
        "price_per_month": price,
        "description": desc
    }

    VPS_PLANS.append(new_plan)
    save_plans(VPS_PLANS)

    await message.answer(
        "✅ <b>Plan added successfully!</b>\n\n"
        f"ID: <code>{new_plan['id']}</code>\n"
        f"Name: <b>{new_plan['name']}</b>\n"
        f"Price: {new_plan['price_per_month']} / month\n"
        f"Desc: {new_plan['description']}"
    )

    await state.finish()

# ---------- DELETE PLAN ----------

def delete_plan_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for p in VPS_PLANS:
        kb.add(
            InlineKeyboardButton(
                text=f"🗑 {p['name']} ({p['price_per_month']}/m)",
                callback_data=f"admin_del_{p['id']}"
            )
        )
    return kb


@dp.callback_query_handler(lambda c: c.data == "admin_delete_plan")
async def admin_delete_plan_menu(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Not allowed", show_alert=True)
        return
    await callback_query.answer()

    if not VPS_PLANS:
        await callback_query.message.answer("❗ Delete karne ke liye koi plan nahi hai.")
        return

    await callback_query.message.answer(
        "🗑 Jis plan ko delete karna hai, usko select karo:",
        reply_markup=delete_plan_keyboard()
    )


@dp.callback_query_handler(lambda c: c.data.startswith("admin_del_"))
async def admin_delete_plan(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Not allowed", show_alert=True)
        return

    await callback_query.answer()
    global VPS_PLANS

    plan_id = callback_query.data.split("admin_del_")[1]
    plan = get_plan_by_id(plan_id)

    if not plan:
        await callback_query.message.answer("❌ Plan already removed ya nahi mila.")
        return

    VPS_PLANS = [p for p in VPS_PLANS if p["id"] != plan_id]
    save_plans(VPS_PLANS)

    await callback_query.message.answer(f"✅ Plan <b>{plan['name']}</b> delete ho gaya.")

# ---------- CHANGE PRICE ----------

def change_price_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for p in VPS_PLANS:
        kb.add(
            InlineKeyboardButton(
                text=f"💰 {p['name']} ({p['price_per_month']}/m)",
                callback_data=f"admin_chp_{p['id']}"
            )
        )
    return kb


@dp.callback_query_handler(lambda c: c.data == "admin_change_price")
async def admin_change_price_menu(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Not allowed", show_alert=True)
        return
    await callback_query.answer()

    if not VPS_PLANS:
        await callback_query.message.answer("❗ Koi plan nahi hai jiska price change kare.")
        return

    await callback_query.message.answer(
        "💰 Jis plan ka price change karna hai, usko select karo:",
        reply_markup=change_price_keyboard()
    )


@dp.callback_query_handler(lambda c: c.data.startswith("admin_chp_"))
async def admin_change_price_select(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Not allowed", show_alert=True)
        return
    await callback_query.answer()

    plan_id = callback_query.data.split("admin_chp_")[1]
    plan = get_plan_by_id(plan_id)
    if not plan:
        await callback_query.message.answer("❌ Plan nahi mila.")
        return

    await state.update_data(change_price_plan_id=plan_id)
    await AdminChangePrice.waiting_for_new_price.set()
    await callback_query.message.answer(
        f"Plan: <b>{plan['name']}</b>\nCurrent price: <b>{plan['price_per_month']}</b>\n\n"
        "Naya price per month bhejo (sirf number)."
    )


@dp.message_handler(state=AdminChangePrice.waiting_for_new_price)
async def admin_change_price_set(message: types.Message, state: FSMContext):
    global VPS_PLANS

    try:
        new_price = float(message.text.strip())
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Valid number bhejo (naya price).")
        return

    data = await state.get_data()
    plan_id = data.get("change_price_plan_id")
    plan = get_plan_by_id(plan_id)

    if not plan:
        await message.answer("❌ Plan nahi mila (shayad delete ho gaya).")
        await state.finish()
        return

    old_price = plan["price_per_month"]
    plan["price_per_month"] = new_price
    save_plans(VPS_PLANS)

    await message.answer(
        f"✅ <b>Price updated!</b>\n\n"
        f"Plan: <b>{plan['name']}</b>\n"
        f"Old price: {old_price}\n"
        f"New price: {new_price}"
    )
    await state.finish()

# ================== MAIN ==================

if __name__ == "__main__":
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        print("❌ Please set your BOT_TOKEN in the code first!")
    else:
        executor.start_polling(dp, skip_updates=True)
