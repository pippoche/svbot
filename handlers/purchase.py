# handlers/purchase.py
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from sheets import get_web_form_url
from utils import get_cancel_keyboard  # Импорт обязателен

logger = logging.getLogger(__name__)

async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    url = get_web_form_url("Закупка материалов")
    if not url:
        await update.callback_query.edit_message_text(
            "URL веб-формы не найден.",
            reply_markup=get_cancel_keyboard()
        )
        return
    await update.callback_query.edit_message_text(
        f"Перейдите по ссылке для закупки материалов:\n{url}",
        reply_markup=get_cancel_keyboard()
    )