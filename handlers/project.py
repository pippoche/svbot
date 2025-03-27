# handlers/project.py
import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import create_project_record

logger = logging.getLogger(__name__)

PROJECT_CUSTOMER, PROJECT_TAG, PROJECT_DIRECTION = range(3)

async def project_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Введите ФИО заказчика:")
    return PROJECT_CUSTOMER

async def project_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["customer"] = update.message.text.strip()
    await update.message.reply_text("Введите номер договора:")
    return PROJECT_TAG

async def project_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["tag"] = update.message.text.strip()
    # Полный список типов сделок из таблицы "Действия и разрешения"
    directions = [
        "Фермы", "Домокомплект", "Ангар", "Фахверк комплект",
        "Строительство", "Продажа ПМ", "Проектная деятельность", "Накладные"
    ]
    keyboard = [[InlineKeyboardButton(direction, callback_data=direction)] for direction in directions]
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    await update.message.reply_text(
        "Выберите направление проекта:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PROJECT_DIRECTION

async def project_direction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    direction = query.data
    customer = context.user_data.get("customer", "")
    tag = context.user_data.get("tag", "")
    if create_project_record(customer, tag, direction):
        await query.edit_message_text(
            f"Проект с номером договора '{tag}' успешно создан с направлением '{direction}'.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.info(f"User {user_id}: Создан проект с номером договора {tag}")
    else:
        await query.edit_message_text(
            "Ошибка при создании проекта.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.error(f"User {user_id}: Ошибка создания проекта с номером договора {tag}")
    return ConversationHandler.END