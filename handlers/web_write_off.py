# handlers/web_write_off.py
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from sheets import get_web_form_url
from utils import get_cancel_keyboard  # Импорт обязателен

logger = logging.getLogger(__name__)

async def start_web_write_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    pattern = update.callback_query.data
    action = "Списание материалов (веб-форма)" if pattern == "web_write_off" else "Внести объемы материалов"
    url = get_web_form_url(action)
    if not url:
        await update.callback_query.edit_message_text(
            "URL веб-формы не найден.", reply_markup=get_cancel_keyboard()
        )
        return
    await update.callback_query.edit_message_text(
        f"Перейдите по ссылке для {action.lower()}:\n{url}",
        reply_markup=get_cancel_keyboard()
    )