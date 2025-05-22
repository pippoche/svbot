# handlers/delivery.py
import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import get_projects_list, record_delivery, caches
from utils import build_project_keyboard, decode_callback_data

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)  # Добавлено для подробных логов

SELECT_PROJECT, SELECT_DEPARTMENT, ENTER_AMOUNT, ENTER_NOTE, SUBMIT_DELIVERY = range(1, 6)

async def start_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    role = context.user_data.get("role", "")
    user_id = update.effective_user.id
    logger.info(f"User {user_id}: Начало доставки, роль={role}")
    projects = get_projects_list(role)
    logger.info(f"User {user_id}: Найдено {len(projects)} проектов для доставки")
    logger.debug(f"User {user_id}: Список проектов: {projects}")
    if not projects:
        await update.callback_query.message.reply_text("Нет доступных проектов для доставки.")
        logger.warning(f"User {user_id}: Проекты не найдены")
        return ConversationHandler.END
    reply_markup = build_project_keyboard(projects)
    # Преобразуем кортеж в список и добавляем "Накладные"
    keyboard = list(reply_markup.inline_keyboard)
    keyboard.append([InlineKeyboardButton("Накладные", callback_data="proj_Накладные")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("Выберите проект для доставки:", reply_markup=reply_markup)
    return SELECT_PROJECT

async def select_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    raw = decode_callback_data(query.data)
    project = raw.replace("proj_", "")
    context.user_data["delivery_project"] = project
    logger.info(f"User {user_id}: Выбран проект '{project}' для доставки")
    keyboard = [
        [InlineKeyboardButton("Строительство", callback_data="Строительство")],
        [InlineKeyboardButton("Производство", callback_data="Производство")],
        [InlineKeyboardButton("Накладные", callback_data="Накладные")],
        [InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    logger.debug(f"User {user_id}: Кнопка 'Вернуться в меню' в select_project: {'main_menu' in str(reply_markup)}")
    await query.message.reply_text("Выберите отдел для доставки:", reply_markup=reply_markup)  # Изменено на reply_text
    return SELECT_DEPARTMENT

async def select_department(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    department = query.data
    if department == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        logger.debug(f"User {user_id}: Нажата кнопка 'Вернуться в меню' в select_department")
        return ConversationHandler.END
    context.user_data["delivery_department"] = department
    logger.info(f"User {user_id}: Выбран отдел '{department}' для доставки")
    await query.message.reply_text("Введите сумму доставки (например, 5000):")  # Изменено на reply_text
    return ENTER_AMOUNT

async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    try:
        amount = float(update.message.text.strip().replace(",", "."))
        if amount <= 0:
            logger.warning(f"User {user_id}: Сумма {amount} не положительная")
            await update.message.reply_text("Сумма должна быть положительной.")
            return ENTER_AMOUNT
        context.user_data["delivery_amount"] = amount
        logger.info(f"User {user_id}: Введена сумма доставки: {amount}")
        keyboard = [
            [InlineKeyboardButton("Пропустить примечание", callback_data="skip_note")],
            [InlineKeyboardButton("Добавить примечание", callback_data="add_note")],
            [InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        logger.debug(f"User {user_id}: Кнопка 'Вернуться в меню' в enter_amount: {'main_menu' in str(reply_markup)}")
        await update.message.reply_text(f"Сумма доставки: {amount}. Хотите добавить примечание?", reply_markup=reply_markup)
        return ENTER_NOTE
    except ValueError:
        logger.warning(f"User {user_id}: Неверная сумма доставки: {update.message.text}")
        await update.message.reply_text("Введите корректное число (например, 5000):")
        return ENTER_AMOUNT

async def enter_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "skip_note":
        context.user_data["delivery_note"] = ""
        logger.info(f"User {user_id}: Пропущено примечание")
        return await submit_delivery(update, context)
    elif query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        logger.debug(f"User {user_id}: Нажата кнопка 'Вернуться в меню' в enter_note")
        return ConversationHandler.END
    else:
        logger.info(f"User {user_id}: Запрошено добавление примечания")
        await query.message.reply_text("Введите примечание (например, 'Макет стены на выставку'):")  # Изменено на reply_text
        return ENTER_NOTE

async def process_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    context.user_data["delivery_note"] = update.message.text.strip()
    logger.info(f"User {user_id}: Примечание добавлено: {context.user_data['delivery_note']}")
    return await submit_delivery(update, context, is_message=True)

async def submit_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE, is_message=False) -> int:
    user_id = update.effective_user.id
    if is_message:
        message = update.message
    else:
        query = update.callback_query
        await query.answer()
        message = query.message
    project = context.user_data.get("delivery_project", "unknown")
    amount = context.user_data.get("delivery_amount", 0)
    department = context.user_data.get("delivery_department", "Строительство")
    note = context.user_data.get("delivery_note", "")
    login = str(context.user_data.get("login", "unknown"))  # Приводим к строке
    employee_data = next((emp for emp in caches["employees"] if str(emp["Логин"]) == login), None)
    user = employee_data["Ф.И.О"] if employee_data else login  # ФИО или логин
    logger.debug(f"User {user_id}: Login={login}, Employee_data={employee_data}, User={user}")  # Отладка
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if project == "unknown" or amount <= 0:
        logger.error(f"User {user_id}: Ошибка доставки - проект: {project}, сумма: {amount}")
        await message.reply_text(
            "Ошибка: не указан проект или сумма доставки.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        return ConversationHandler.END
    record = [date, "Расход", user, "", department, "Доставка", 1, "", "", amount, project, note]
    if record_delivery([record]):
        text = f"Доставка на сумму {amount} для '{project}' ({department}) успешно записана!"
        if note:
            text += f"\nПримечание: {note}"
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.info(f"User {user_id}: Доставка записана для проекта {project}")
    else:
        await message.reply_text(
            "Ошибка при записи доставки.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.error(f"User {user_id}: Ошибка записи доставки для проекта {project}")
    return ConversationHandler.END