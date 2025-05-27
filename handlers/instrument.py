# handlers/instrument.py
import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import get_projects_list, get_instruments, record_instrument_transaction, caches
from utils import build_project_keyboard, build_instrument_keyboard

logger = logging.getLogger(__name__)

SELECT_PROJECT, TRANSACTION_TYPE, RECIPIENT, SELECT_INSTRUMENT, ENTER_QUANTITY, SUBMIT = range(1, 7)

async def start_instrument(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    role = context.user_data.get("role", "")
    user_id = update.effective_user.id
    projects = get_projects_list(role)
    logger.info(f"User {user_id}: Начало работы с инструментом, найдено {len(projects)} проектов")
    if not projects:
        await update.callback_query.edit_message_text("Нет доступных проектов.")
        return ConversationHandler.END
    reply_markup = build_project_keyboard(projects)
    await update.callback_query.edit_message_text("Выберите проект:", reply_markup=reply_markup)
    return SELECT_PROJECT

async def select_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    raw = decode_callback_data(query.data)
    tag = raw.replace("proj_", "")
    context.user_data["instrument_project"] = project
    keyboard = [
        [InlineKeyboardButton("Приход", callback_data="Приход")],
        [InlineKeyboardButton("Расход", callback_data="Расход")],
        [InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        f"Выбран проект: {project}. Выберите тип операции:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TRANSACTION_TYPE

async def transaction_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    context.user_data["transaction_type"] = query.data
    await query.edit_message_text("Введите кому выдан инструмент (ФИО):")
    return RECIPIENT

async def recipient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["recipient"] = update.message.text.strip()
    instruments = get_instruments()
    context.user_data["instruments_input"] = {}
    reply_markup = build_instrument_keyboard(instruments, context.user_data["instruments_input"])
    await update.message.reply_text("Выберите инструмент:", reply_markup=reply_markup)
    return SELECT_INSTRUMENT

async def select_instrument(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "submit":
        return await submit_instrument(update, context)
    instrument = query.data.replace("inst_", "")
    context.user_data["current_instrument"] = instrument
    instruments = get_instruments()
    unit = next((i["unit"] for i in instruments if i["name"] == instrument), "шт")
    await query.edit_message_text(f"Введите количество для {instrument} ({unit}):")
    return ENTER_QUANTITY

async def enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    try:
        quantity = float(update.message.text.strip().replace(",", "."))
        if quantity <= 0:
            await update.message.reply_text("Количество должно быть положительным.")
            return ENTER_QUANTITY
    except ValueError:
        await update.message.reply_text("Введите корректное число:")
        return ENTER_QUANTITY
    instrument = context.user_data.get("current_instrument", "")
    context.user_data.setdefault("instruments_input", {})[instrument] = quantity
    instruments = get_instruments()
    reply_markup = build_instrument_keyboard(instruments, context.user_data["instruments_input"])
    await update.message.reply_text("Выберите следующий инструмент или подтвердите:", reply_markup=reply_markup)
    return SELECT_INSTRUMENT

async def submit_instrument(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    instruments_input = context.user_data.get("instruments_input", {})
    project = context.user_data.get("instrument_project", "unknown")
    transaction_type = context.user_data.get("transaction_type", "Приход")
    recipient = context.user_data.get("recipient", "unknown")
    login = str(context.user_data.get("login", "unknown"))  # Приводим к строке
    employee_data = next((emp for emp in caches["employees"] if str(emp["Логин"]) == login), None)
    user = employee_data["Ф.И.О"] if employee_data else login  # ФИО или логин
    logger.debug(f"User {user_id}: Login={login}, Employee_data={employee_data}, User={user}")  # Отладка
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records = [
        [date, transaction_type, user, project, recipient, instrument, qty]
        for instrument, qty in instruments_input.items()
    ]
    if record_instrument_transaction(records):
        text = f"Инструменты успешно {'приняты' if transaction_type == 'Приход' else 'выданы'} для проекта {project}:\n" + "\n".join(
            f"{instrument}: {qty}" for instrument, qty in instruments_input.items()
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.info(f"User {user_id}: Инструменты {transaction_type} записаны для номера договора {project}")
    else:
        await query.edit_message_text(
            "Ошибка при записи операции с инструментами.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.error(f"User {user_id}: Ошибка записи операции с инструментами для проекта {project}")
    return ConversationHandler.END