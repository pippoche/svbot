# handlers/expense.py
import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import get_projects_list, record_expense, get_project_direction, get_role_permissions, caches  # Добавлен caches
from utils import build_project_keyboard

logger = logging.getLogger(__name__)

SELECT_PROJECT, ENTER_DETAILS, SUBMIT_EXPENSE = range(1, 4)

async def start_add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    role = context.user_data.get("role", "")
    user_id = update.effective_user.id
    logger.info(f"User {user_id}: Начало добавления расхода, роль={role}")
    projects = get_projects_list(role)
    logger.info(f"User {user_id}: Найдено {len(projects)} проектов для добавления расхода")
    keyboard = [
        [InlineKeyboardButton(f"{p['Номер договора']} ({p['Ф.И.О заказчика']})", callback_data=f"proj_{p['Номер договора']}")]
        for p in projects if p.get('Номер договора')
    ]
    keyboard.append([InlineKeyboardButton("Накладные", callback_data="proj_Накладные")])  # Добавляем "Накладные"
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "Выберите проект или категорию для расхода:", reply_markup=reply_markup
    )
    return SELECT_PROJECT

async def select_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    project_tag = query.data.replace("proj_", "")
    role = context.user_data.get("role", "")
    if project_tag == "Накладные":
        context.user_data["expense_project"] = "Накладные"  # Без проверки разрешения
    else:
        project = next((p for p in get_projects_list(role) if str(p["Номер договора"]) == str(project_tag)), None)
        if not project:
            logger.warning(f"User {user_id}: Проект '{project_tag}' не найден")
            await query.edit_message_text(
                f"Проект '{project_tag}' не найден.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
            )
            return ConversationHandler.END
        context.user_data["expense_project"] = project_tag
    logger.info(f"User {user_id}: Выбран проект '{project_tag}' для расхода")
    await query.edit_message_text("Введите данные расхода (например, 'Клавиатура, 1, шт, 1000'):")
    return ENTER_DETAILS

async def enter_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    text = update.message.text.strip()
    logger.info(f"User {user_id}: Введены данные расхода: {text}")
    parts = [p.strip() for p in text.split(",", 3)]
    if len(parts) != 4:
        logger.warning(f"User {user_id}: Неверный формат данных расхода: {text}")
        await update.message.reply_text(
            "Неверный формат. Используйте: Название, количество, ед.изм, цена (например, 'Клавиатура, 1, шт, 1000')"
        )
        return ENTER_DETAILS
    name, qty, unit, price = parts
    try:
        quantity = float(qty.replace(",", "."))
        amount = float(price.replace(",", "."))
        if quantity <= 0 or amount < 0:
            logger.warning(f"User {user_id}: Неверные значения: количество={quantity}, цена={amount}")
            await update.message.reply_text("Количество должно быть положительным, цена не отрицательной.")
            return ENTER_DETAILS
        context.user_data["expense_details"] = {"name": name, "quantity": quantity, "unit": unit, "amount": amount}
        logger.info(f"User {user_id}: Данные расхода введены: {name}, {quantity} {unit}, {amount} руб.")
        keyboard = [
            [InlineKeyboardButton("Подтвердить", callback_data="submit")],
            [InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]
        ]
        await update.message.reply_text(
            f"Расход: {name}, {quantity} {unit}, {amount} руб. Подтвердите:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SUBMIT_EXPENSE
    except ValueError:
        logger.warning(f"User {user_id}: Неверные числа в данных расхода: {text}")
        await update.message.reply_text("Введите корректные числа для количества и цены:")
        return ENTER_DETAILS

async def submit_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    project = context.user_data.get("expense_project", "unknown")
    details = context.user_data.get("expense_details", {})
    login = str(context.user_data.get("login", "unknown"))  # Приводим к строке
    employee_data = next((emp for emp in caches["employees"] if str(emp["Логин"]) == login), None)
    user = employee_data["Ф.И.О"] if employee_data else login  # ФИО или логин
    logger.debug(f"User {user_id}: Login={login}, Employee_data={employee_data}, User={user}")  # Отладка
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_price = details["quantity"] * details["amount"]
    direction = "Накладные" if project == "Накладные" else context.user_data.get("department", "Строительство")
    record = [
        date, "Расход", user, "Наличные", direction, details["name"], details["quantity"], details["unit"], "", details["amount"], project
    ]
    if record_expense([record]):
        await query.edit_message_text(
            f"Расход '{details['name']}' на сумму {total_price} для '{project}' (отдел: {direction}) успешно записан!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.info(f"User {user_id}: Расход записан для проекта {project}")
        context.user_data.clear()  # Очищаем данные после успеха
    else:
        await query.edit_message_text(
            "Ошибка при записи расхода.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.error(f"User {user_id}: Ошибка записи расхода для проекта {project}")
        context.user_data.clear()  # Очищаем данные при ошибке
    return ConversationHandler.END