# handlers/report_issue.py
import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import record_expense  # Используем record_expense вместо append_row_to_sheet

logger = logging.getLogger(__name__)

async def start_report_issue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    user_id = update.effective_user.id
    logger.info(f"User {user_id}: Начало сообщения о проблеме")
    await update.callback_query.edit_message_text("Опишите проблему:")
    return 1

async def save_issue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    issue_text = update.message.text
    username = update.effective_user.username or "unknown"
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    login = str(context.user_data.get("login", "unknown"))
    # Получаем ФИО сотрудника, как в других модулях
    employee_data = next((emp for emp in caches["employees"] if str(emp["Логин"]) == login), None)
    user = employee_data["Ф.И.О"] if employee_data else login
    # Формат записи совместим с record_expense (как в expense.py)
    record = [date, "Ошибка", user, "", "", issue_text, "", "", "", "", str(user_id)]
    record_expense([record])
    logger.info(f"User {user_id}: Проблема сохранена: {issue_text}")
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
    await update.message.reply_text("Проблема записана!", reply_markup=reply_markup)
    return ConversationHandler.END

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from handlers.start import back_to_menu
    await back_to_menu(update, context)
    return ConversationHandler.END