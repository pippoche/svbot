import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from sheets import add_new_instrument

logger = logging.getLogger(__name__)

ENTER_DETAILS = 1

async def start_new_instrument(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Введите данные инструмента (например, 'Долото, шт, 1'):"
    )
    return ENTER_DETAILS

async def enter_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    parts = [p.strip() for p in text.split(",", 2)]
    if len(parts) != 3:
        await update.message.reply_text(
            "Неверный формат. Используйте: Название, ед.изм, количество (например, 'Долото, шт, 1')"
        )
        return ENTER_DETAILS
    name, unit, qty = parts
    try:
        quantity = float(qty.replace(",", "."))
        if quantity <= 0:
            await update.message.reply_text("Количество должно быть положительным.")
            return ENTER_DETAILS
    except ValueError:
        await update.message.reply_text("Введите корректное число для количества:")
        return ENTER_DETAILS
    if add_new_instrument(name, unit, quantity):
        await update.message.reply_text(
            f"Инструмент '{name}' ({quantity} {unit}) успешно добавлен!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.info(f"User {update.effective_user.id}: Добавлен инструмент {name}")
    else:
        await update.message.reply_text(
            "Ошибка при добавлении инструмента.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.error(f"User {update.effective_user.id}: Ошибка добавления инструмента {name}")
    return ConversationHandler.END
