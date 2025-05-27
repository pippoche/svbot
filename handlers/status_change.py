# handlers/status_change.py
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import get_projects_list, update_project_status

logger = logging.getLogger(__name__)

STATUS_TAG, STATUS_CHANGE = range(2)

async def start_status_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    role = context.user_data.get("role", "")
    user_id = update.effective_user.id
    projects = get_projects_list(role)
    logger.info(f"User {user_id}: Начало смены статуса, найдено {len(projects)} проектов")
    if not projects:
        await update.callback_query.edit_message_text("Нет доступных проектов.")
        return ConversationHandler.END
    keyboard = [
        [InlineKeyboardButton(f"{p['Номер договора']} ({p['Статус']})", callback_data=f"proj_{p['Номер договора']}")]
        for p in projects
    ]
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("Выберите проект для смены статуса:", reply_markup=reply_markup)
    return STATUS_TAG

async def status_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    raw = decode_callback_data(query.data)
    tag = raw.replace("proj_", "")
    if tag == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    # Добавляем str() для корректного сравнения строки и числа
    project = next((p for p in get_projects_list(context.user_data.get("role", "")) if str(p["Номер договора"]) == str(tag)), None)
    if not project:
        logger.warning(f"User {user_id}: Проект '{tag}' не найден")
        await query.edit_message_text(
            f"Проект '{tag}' не найден.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        return ConversationHandler.END
    context.user_data["status_tag"] = tag
    keyboard = [
        [InlineKeyboardButton("В работе", callback_data="В работе")],
        [InlineKeyboardButton("Продукция готова", callback_data="Продукция готова")],
        [InlineKeyboardButton("Строительство", callback_data="Строительство")],
        [InlineKeyboardButton("Приостановлен", callback_data="Приостановлен")],
        [InlineKeyboardButton("Готов", callback_data="готов")],
        [InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        f"Текущий статус '{tag}': {project['Статус']}. Выберите новый статус:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATUS_CHANGE

async def status_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    new_status = query.data
    tag = context.user_data.get("status_tag", "")
    if update_project_status(tag, new_status):
        await query.edit_message_text(
            f"Статус номера договора '{tag}' изменён на '{new_status}'.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.info(f"User {user_id}: Статус номера договора {tag} изменён на {new_status}")
    else:
        await query.edit_message_text(
            f"Ошибка при смене статуса для '{tag}'.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.error(f"User {user_id}: Ошибка смены статуса для {tag}")
    return ConversationHandler.END