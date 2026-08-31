# ==============================================================================
# 🐸 FROGMENSHOP BOT - Полный код магазина цифровых товаров
# ==============================================================================
# ⚠️ Токен и Ваш Admin ID уже прописаны!
# ==============================================================================

import asyncio
import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery,
    FSInputFile, InputMediaPhoto
)
from aiogram.client.session.aiohttp import AiohttpSession

# --- НАСТРОЙКИ БОТА ---
BOT_TOKEN = "8963205214:AAGqix3DyovsyklXjJ_EDKpvh0ToqzYs0zY"
ADMIN_ID = 6603375763
BANNER_PATH = "banner.jpg"

# 🌐 ПРОКСИ (Если Telegram блокируется вашим провайдером)
# Если у вас включен VPN или нет блокировок — оставьте None.
# Если вы используете прокси (например, SOCKS5 или HTTP), укажите ссылку на него:
# Пример: PROXY_URL = "http://127.0.0.1:1080" или "socks5://ip:port"
PROXY_URL = None  

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Инициализация сессии и бота
if PROXY_URL:
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    bot = Bot(token=BOT_TOKEN)

dp = Dispatcher(storage=MemoryStorage())

# ==============================================================================
# 💾 БАЗА ДАННЫХ SQLite
# ==============================================================================
def init_db():
    conn = sqlite3.connect('frogmenshop.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cat_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price INTEGER NOT NULL,
            content TEXT NOT NULL,
            stock INTEGER NOT NULL,
            FOREIGN KEY (cat_id) REFERENCES categories (id)
        )
    ''')
    conn.commit()
    conn.close()

def db_execute(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect('frogmenshop.db')
    cur = conn.cursor()
    cur.execute(query, params)
    res = None
    if fetchone:
        res = cur.fetchone()
    if fetchall:
        res = cur.fetchall()
    if commit:
        conn.commit()
    conn.close()
    return res

# ==============================================================================
# 🧠 СОСТОЯНИЯ (FSM)
# ==============================================================================
class ShopStates(StatesGroup):
    fill_balance = State()
    
    # Админ состояния
    add_cat = State()
    add_prod_name = State()
    add_prod_desc = State()
    add_prod_price = State()
    add_prod_content = State()
    add_prod_stock = State()
    
    give_bal_id = State()
    give_bal_amount = State()
    
    take_bal_id = State()
    take_bal_amount = State()
    
    ban_user_id = State()

# ==============================================================================
# 🎨 КЛАВИАТУРЫ И ВНОС КАРТИНКИ
# ==============================================================================
def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Приобрести", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="💎 Пополнить баланс", callback_data="deposit")]
    ])

def get_back_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")]
    ])

def get_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 Добавить ассортимент", callback_data="adm_add_cat")],
        [InlineKeyboardButton(text="🎁 Добавить товар", callback_data="adm_add_prod")],
        [InlineKeyboardButton(text="➕ Выдать баланс", callback_data="adm_give_bal")],
        [InlineKeyboardButton(text="➖ Забрать баланс", callback_data="adm_take_bal")],
        [InlineKeyboardButton(text="🚫 Заблокировать / Разбанить", callback_data="adm_ban")],
        [InlineKeyboardButton(text="❌ Закрыть панель", callback_data="adm_close")]
    ])

async def send_or_edit_banner(target, text, reply_markup=None, is_callback=False):
    """Универсальная функция для отправки фото с текстом под ним"""
    banner_exists = os.path.exists(BANNER_PATH)
    
    if is_callback:
        try:
            if banner_exists:
                await target.message.edit_media(
                    media=InputMediaPhoto(media=FSInputFile(BANNER_PATH), caption=text, parse_mode="HTML"),
                    reply_markup=reply_markup
                )
            else:
                await target.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
            return
        except Exception:
            try:
                await target.message.delete()
            except Exception:
                pass

    chat_id = target.message.chat.id if is_callback else target.chat.id
    
    if banner_exists:
        photo = FSInputFile(BANNER_PATH)
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

def is_user_blocked(user_id):
    res = db_execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    return res and res[0] == 1

# ==============================================================================
# 🚀 ХЕНДЛЕРЫ ПОЛЬЗОВАТЕЛЯ
# ==============================================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    user = db_execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user:
        db_execute("INSERT INTO users (user_id) VALUES (?)", (user_id,), commit=True)
        
    if is_user_blocked(user_id):
        await message.answer("🚫 <b>Вы заблокированы в магазине FrogmenShop!</b>", parse_mode="HTML")
        return

    text = (
        "<b>🐸 Добро пожаловать в FrogmenShop!</b>\n\n"
        "✨ Лучший магазин цифровых товаров и уникальных гайдов!\n"
        "⚡ Мгновенная выдача товаров сразу после оплаты.\n\n"
        "👇 <b>Выберите нужный раздел в меню ниже:</b>"
    )
    await send_or_edit_banner(message, text, reply_markup=get_main_kb())

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    if is_user_blocked(call.from_user.id):
        return await call.answer("🚫 Вы заблокированы!", show_alert=True)
        
    text = (
        "<b>🐸 Главное меню FrogmenShop</b>\n\n"
        "✨ Воспользуйтесь кнопками ниже для навигации по магазину:"
    )
    await send_or_edit_banner(call, text, reply_markup=get_main_kb(), is_callback=True)

# 👤 ПРОФИЛЬ
@dp.callback_query(F.data == "profile")
async def cb_profile(call: types.CallbackQuery):
    if is_user_blocked(call.from_user.id):
        return await call.answer("🚫 Вы заблокированы!", show_alert=True)

    user_data = db_execute("SELECT balance FROM users WHERE user_id = ?", (call.from_user.id,), fetchone=True)
    balance = user_data[0] if user_data else 0

    text = (
        "<b>👤 Личный кабинет</b>\n\n"
        f"🆔 <b>Ваш ID:</b> <code>{call.from_user.id}</code>\n"
        f"💎 <b>Баланс:</b> <code>{balance}</code> ⭐ (Telegram Stars)\n\n"
        "🚀 <i>Используйте свой баланс для мгновенных покупок цифровых товаров!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")]
    ])
    await send_or_edit_banner(call, text, reply_markup=kb, is_callback=True)

# 💎 ПОПОЛНЕНИЕ БАЛАНСА (STARS)
@dp.callback_query(F.data == "deposit")
async def cb_deposit(call: types.CallbackQuery, state: FSMContext):
    if is_user_blocked(call.from_user.id):
        return await call.answer("🚫 Вы заблокированы!", show_alert=True)

    await state.set_state(ShopStates.fill_balance)
    text = (
        "<b>💎 Пополнение баланса Telegram Stars</b>\n\n"
        "✍️ Введите количество звезд, на которое хотите пополнить счет:\n"
        "📌 <i>Минимум: 1 ⭐ | Максимум: 10 000 ⭐</i>"
    )
    await send_or_edit_banner(call, text, reply_markup=get_back_main_kb(), is_callback=True)

@dp.message(ShopStates.fill_balance)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    if is_user_blocked(message.from_user.id):
        return

    if not message.text.isdigit():
        text = "❌ <b>Ошибка!</b> Пожалуйста, введите целое число от 1 до 10000:"
        return await send_or_edit_banner(message, text, reply_markup=get_back_main_kb())

    amount = int(message.text)
    if amount < 1 or amount > 10000:
        text = "❌ <b>Сумма должна быть в диапазоне от 1 до 10000 звезд!</b> Введите снова:"
        return await send_or_edit_banner(message, text, reply_markup=get_back_main_kb())

    await state.clear()
    
    prices = [LabeledPrice(label=f"Пополнение {amount} ⭐", amount=amount)]
    await message.answer_invoice(
        title="🐸 Пополнение FrogmenShop",
        description=f"Зачисление {amount} ⭐ (Telegram Stars) на ваш личный баланс.",
        prices=prices,
        payload=f"stars_deposit_{amount}_{message.from_user.id}",
        currency="XTR",
        provider_token=""
    )

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    amount = message.successful_payment.total_amount
    user_id = message.from_user.id
    
    db_execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id), commit=True)
    
    user_data = db_execute("SELECT balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    new_bal = user_data[0] if user_data else amount
    
    text = (
        "<b>✅ Оплата прошла успешно!</b>\n\n"
        f"🎉 На ваш счет зачислено: <b>+{amount}</b> ⭐\n"
        f"💰 Ваш текущий баланс: <b>{new_bal}</b> ⭐\n\n"
        "🤝 Спасибо за покупку в FrogmenShop!"
    )
    await send_or_edit_banner(message, text, reply_markup=get_main_kb())

# 🛒 КАТАЛОГ И ПОКУПКА
@dp.callback_query(F.data == "catalog")
async def cb_catalog(call: types.CallbackQuery):
    if is_user_blocked(call.from_user.id):
        return await call.answer("🚫 Вы заблокированы!", show_alert=True)

    categories = db_execute("SELECT id, name FROM categories", fetchall=True)
    
    if not categories:
        text = "<b>📁 Ассортимент пуст!</b>\n\nАдминистратор еще не добавил категории товаров."
        return await send_or_edit_banner(call, text, reply_markup=get_back_main_kb(), is_callback=True)

    text = "<b>📁 Выберите категорию товаров:</b>"
    kb = []
    for cat_id, cat_name in categories:
        kb.append([InlineKeyboardButton(text=f"📂 {cat_name}", callback_data=f"cat_{cat_id}")])
    kb.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")])

    await send_or_edit_banner(call, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), is_callback=True)

@dp.callback_query(F.data.startswith("cat_"))
async def cb_products(call: types.CallbackQuery):
    if is_user_blocked(call.from_user.id):
        return await call.answer("🚫 Вы заблокированы!", show_alert=True)

    cat_id = int(call.data.split("_")[1])
    cat = db_execute("SELECT name FROM categories WHERE id = ?", (cat_id,), fetchone=True)
    products = db_execute("SELECT id, name, price, stock FROM products WHERE cat_id = ? AND stock > 0", (cat_id,), fetchall=True)

    if not products:
        await call.answer("😔 В этой категории сейчас нет доступных товаров!", show_alert=True)
        return

    text = f"<b>📂 Категория: {cat[0]}</b>\n\nВыберите нужный товар из списка ниже:"
    kb = []
    for p_id, p_name, p_price, p_stock in products:
        kb.append([InlineKeyboardButton(text=f"📦 {p_name} | {p_price} ⭐ ({p_stock} шт)", callback_data=f"prod_{p_id}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад в категории", callback_data="catalog")])

    await send_or_edit_banner(call, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), is_callback=True)

@dp.callback_query(F.data.startswith("prod_"))
async def cb_product_view(call: types.CallbackQuery):
    if is_user_blocked(call.from_user.id):
        return await call.answer("🚫 Вы заблокированы!", show_alert=True)

    p_id = int(call.data.split("_")[1])
    product = db_execute("SELECT id, cat_id, name, description, price, stock FROM products WHERE id = ?", (p_id,), fetchone=True)

    if not product or product[5] <= 0:
        await call.answer("❌ Товар временно отсутствует на складе!", show_alert=True)
        return

    p_id, cat_id, name, desc, price, stock = product

    text = (
        f"<b>📦 {name}</b>\n\n"
        f"📝 <b>Описание:</b>\n{desc}\n\n"
        f"💎 <b>Цена:</b> <code>{price}</code> ⭐\n"
        f"📦 <b>В наличии:</b> <code>{stock}</code> шт."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🛍 Купить за {price} ⭐", callback_data=f"buy_{p_id}")],
        [InlineKeyboardButton(text="⬅️ К товарам категории", callback_data=f"cat_{cat_id}")]
    ])
    await send_or_edit_banner(call, text, reply_markup=kb, is_callback=True)

@dp.callback_query(F.data.startswith("buy_"))
async def cb_buy_confirm(call: types.CallbackQuery):
    user_id = call.from_user.id
    if is_user_blocked(user_id):
        return await call.answer("🚫 Вы заблокированы!", show_alert=True)

    p_id = int(call.data.split("_")[1])
    product = db_execute("SELECT name, price, content, stock FROM products WHERE id = ?", (p_id,), fetchone=True)

    if not product or product[3] <= 0:
        return await call.answer("❌ Товар закончился!", show_alert=True)

    name, price, content, stock = product
    user_bal = db_execute("SELECT balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)[0]

    if user_bal < price:
        return await call.answer(f"❌ Недостаточно средств на балансе! Требуется {price} ⭐, а у вас {user_bal} ⭐", show_alert=True)

    new_bal = user_bal - price
    db_execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_bal, user_id), commit=True)
    db_execute("UPDATE products SET stock = stock - 1 WHERE id = ?", (p_id,), commit=True)

    text = (
        "<b>🎉 Покупка успешно завершена!</b>\n\n"
        f"📦 <b>Товар:</b> {name}\n"
        f"💰 <b>Списано:</b> {price} ⭐\n"
        f"💎 <b>Остаток баланса:</b> {new_bal} ⭐\n\n"
        "🎁 <b>Ваш товар / гайд:</b>\n"
        f"<code>{content}</code>"
    )
    await send_or_edit_banner(call, text, reply_markup=get_main_kb(), is_callback=True)

# ==============================================================================
# 🛠 АДМИН-ПАНЕЛЬ (/adminpanel)
# ==============================================================================

@dp.message(Command("adminpanel"))
async def cmd_admin_panel(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        return

    text = (
        "<b>🛠 Админ-панель FrogmenShop</b>\n\n"
        "⚡ Управление магазином, товарами и пользователями.\n"
        "Выберите нужное действие ниже:"
    )
    await send_or_edit_banner(message, text, reply_markup=get_admin_kb())

@dp.callback_query(F.data == "adm_close")
async def cb_adm_close(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.clear()
    await call.message.delete()

# --- ДОБАВЛЕНИЕ АССОРТИМЕНТА (КАТЕГОРИИ) ---
@dp.callback_query(F.data == "adm_add_cat")
async def cb_adm_add_cat(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(ShopStates.add_cat)
    text = "<b>📁 Пополнение ассортимента</b>\n\nВведите название новой категории (например: <code>Гайды</code>):"
    await send_or_edit_banner(call, text, reply_markup=get_admin_kb(), is_callback=True)

@dp.message(ShopStates.add_cat)
async def process_add_cat_name(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    cat_name = message.text.strip()
    db_execute("INSERT INTO categories (name) VALUES (?)", (cat_name,), commit=True)
    await state.clear()
    text = f"<b>✅ Категория «{cat_name}» успешно добавлена!</b>"
    await send_or_edit_banner(message, text, reply_markup=get_admin_kb())

# --- ДОБАВЛЕНИЕ ТОВАРА ---
@dp.callback_query(F.data == "adm_add_prod")
async def cb_adm_add_prod(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    categories = db_execute("SELECT id, name FROM categories", fetchall=True)
    if not categories:
        return await call.answer("⚠️ Сначала создайте хотя бы одну категорию!", show_alert=True)

    kb = []
    for c_id, c_name in categories:
        kb.append([InlineKeyboardButton(text=f"📂 {c_name}", callback_data=f"admcat_{c_id}")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="adm_close")])

    text = "<b>🎁 Добавление товара</b>\n\nВыберите категорию, в которую добавить товар:"
    await send_or_edit_banner(call, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), is_callback=True)

@dp.callback_query(F.data.startswith("admcat_"))
async def cb_adm_set_prod_cat(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    cat_id = int(call.data.split("_")[1])
    await state.update_data(cat_id=cat_id)
    await state.set_state(ShopStates.add_prod_name)
    text = "<b>🎁 Шаг 1/5: Название товара</b>\n\nВведите название товара:"
    await send_or_edit_banner(call, text, is_callback=True)

@dp.message(ShopStates.add_prod_name)
async def process_prod_name(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.update_data(name=message.text.strip())
    await state.set_state(ShopStates.add_prod_desc)
    text = "<b>🎁 Шаг 2/5: Описание товара</b>\n\nВведите подробное описание товара:"
    await send_or_edit_banner(message, text)

@dp.message(ShopStates.add_prod_desc)
async def process_prod_desc(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.update_data(desc=message.text.strip())
    await state.set_state(ShopStates.add_prod_price)
    text = "<b>🎁 Шаг 3/5: Цена товара</b>\n\nВведите цену в звездах ⭐ (число):"
    await send_or_edit_banner(message, text)

@dp.message(ShopStates.add_prod_price)
async def process_prod_price(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        return await send_or_edit_banner(message, "❌ <b>Введите число!</b> Попробуйте еще раз:")
    
    await state.update_data(price=int(message.text))
    await state.set_state(ShopStates.add_prod_content)
    text = "<b>🎁 Шаг 4/5: Содержимое товара</b>\n\nВведите то, что выдаст бот после покупки (ссылка, гайд, ключ или текст):"
    await send_or_edit_banner(message, text)

@dp.message(ShopStates.add_prod_content)
async def process_prod_content(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.update_data(content=message.text.strip())
    await state.set_state(ShopStates.add_prod_stock)
    text = "<b>🎁 Шаг 5/5: Наличие товара</b>\n\nВведите количество доступных штук (число):"
    await send_or_edit_banner(message, text)

@dp.message(ShopStates.add_prod_stock)
async def process_prod_stock(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        return await send_or_edit_banner(message, "❌ <b>Введите число!</b> Попробуйте еще раз:")

    stock = int(message.text)
    data = await state.get_data()

    db_execute(
        "INSERT INTO products (cat_id, name, description, price, content, stock) VALUES (?,?,?,?,?,?)",
        (data['cat_id'], data['name'], data['desc'], data['price'], data['content'], stock),
        commit=True
    )
    await state.clear()
    text = f"<b>✅ Товар «{data['name']}» успешно добавлен в магазин!</b>"
    await send_or_edit_banner(message, text, reply_markup=get_admin_kb())

# --- ВЫДАЧА И ЗАБОР БАЛАНСА ---
@dp.callback_query(F.data == "adm_give_bal")
async def cb_adm_give_bal(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(ShopStates.give_bal_id)
    text = "<b>➕ Выдача баланса</b>\n\nВведите ID пользователя:"
    await send_or_edit_banner(call, text, reply_markup=get_admin_kb(), is_callback=True)

@dp.message(ShopStates.give_bal_id)
async def process_give_bal_id(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        return await send_or_edit_banner(message, "❌ Введите корректный ID!")
    await state.update_data(target_id=int(message.text))
    await state.set_state(ShopStates.give_bal_amount)
    text = "<b>➕ Выдача баланса</b>\n\nВведите количество звезд ⭐ для начисления:"
    await send_or_edit_banner(message, text)

@dp.message(ShopStates.give_bal_amount)
async def process_give_bal_amount(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        return await send_or_edit_banner(message, "❌ Введите число звезд!")

    amount = int(message.text)
    data = await state.get_data()
    target_id = data['target_id']

    db_execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id), commit=True)
    await state.clear()
    text = f"<b>✅ Пользователю <code>{target_id}</code> начислено {amount} ⭐!</b>"
    await send_or_edit_banner(message, text, reply_markup=get_admin_kb())

@dp.callback_query(F.data == "adm_take_bal")
async def cb_adm_take_bal(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(ShopStates.take_bal_id)
    text = "<b>➖ Списание баланса</b>\n\nВведите ID пользователя:"
    await send_or_edit_banner(call, text, reply_markup=get_admin_kb(), is_callback=True)

@dp.message(ShopStates.take_bal_id)
async def process_take_bal_id(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        return await send_or_edit_banner(message, "❌ Введите корректный ID!")
    await state.update_data(target_id=int(message.text))
    await state.set_state(ShopStates.take_bal_amount)
    text = "<b>➖ Списание баланса</b>\n\nВведите количество звезд ⭐ для списания:"
    await send_or_edit_banner(message, text)

@dp.message(ShopStates.take_bal_amount)
async def process_take_bal_amount(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        return await send_or_edit_banner(message, "❌ Введите число звезд!")

    amount = int(message.text)
    data = await state.get_data()
    target_id = data['target_id']

    db_execute("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?", (amount, target_id), commit=True)
    await state.clear()
    text = f"<b>✅ У пользователя <code>{target_id}</code> списано {amount} ⭐!</b>"
    await send_or_edit_banner(message, text, reply_markup=get_admin_kb())

# --- БАН И РАЗБАН ---
@dp.callback_query(F.data == "adm_ban")
async def cb_adm_ban(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.set_state(ShopStates.ban_user_id)
    text = "<b>🚫 Блокировка / Разблокировка</b>\n\nВведите ID пользователя для изменения его статуса блокировки:"
    await send_or_edit_banner(call, text, reply_markup=get_admin_kb(), is_callback=True)

@dp.message(ShopStates.ban_user_id)
async def process_ban_user(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        return await send_or_edit_banner(message, "❌ Введите корректный ID!")

    target_id = int(message.text)
    user = db_execute("SELECT is_blocked FROM users WHERE user_id = ?", (target_id,), fetchone=True)

    if not user:
        db_execute("INSERT INTO users (user_id, is_blocked) VALUES (?, 1)", (target_id,), commit=True)
        status = "заблокирован"
    else:
        new_status = 0 if user[0] == 1 else 1
        db_execute("UPDATE users SET is_blocked = ? WHERE user_id = ?", (new_status, target_id), commit=True)
        status = "разблокирован" if new_status == 0 else "заблокирован"

    await state.clear()
    text = f"<b>✅ Пользователь <code>{target_id}</code> успешно {status}!</b>"
    await send_or_edit_banner(message, text, reply_markup=get_admin_kb())

# ==============================================================================
# 🏃 ЗАПУСК БОТА
# ==============================================================================
async def main():
    init_db()
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        print(f"⚠️ Предупреждение при удалении вебхука: {e}")
        
    print("🐸 Бот FrogmenShop запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
