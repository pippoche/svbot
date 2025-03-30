# handlers/start.py
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import get_employee_data, get_role_permissions

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

LOGIN, PASSWORD = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    context.user_data.clear()
    logger.info(f"User {user_id}: Начало авторизации")
    await update.message.reply_text("Добро пожаловать! Введите ваш логин:")
    return LOGIN

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    context.user_data["login"] = update.message.text.strip()
    logger.info(f"User {user_id}: Логин введён: {context.user_data['login']}")
    await update.message.reply_text("Теперь введите ваш пароль:")
    return PASSWORD

async def password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    context.user_data["password"] = update.message.text.strip()
    logger.info(f"User {user_id}: Пароль введён для логина {context.user_data['login']}")
    role, department = get_employee_data(context.user_data["login"], context.user_data["password"])
    if not role:
        text = "Неверный логин или пароль. Попробуйте снова:\nВведите ваш логин:"
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Сбросить данные входа", callback_data="reset_login")]])
        await update.message.reply_text(text, reply_markup=reply_markup)
        return LOGIN
    context.user_data["role"] = role
    context.user_data["department"] = department
    await main_menu(update, context)
    logger.info(f"User {user_id}: Успешная авторизация, роль={role}")
    return ConversationHandler.END

async def reset_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    await update.callback_query.answer()
    context.user_data.clear()
    logger.info(f"User {user_id}: Сброс данных входа")
    await update.callback_query.message.reply_text("Данные входа сброшены. Нажмите /start для новой авторизации.")
    return ConversationHandler.END  # Завершаем текущий диалог, ждём /start

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    role = context.user_data.get("role")
    department = context.user_data.get("department")
    login = context.user_data.get("login")
    password = context.user_data.get("password")

    if not role or not department or not login or not password:
        logger.warning(f"User {user_id}: Нет полных данных для авторизации при вызове main_menu")
        text = "Пожалуйста, авторизуйтесь.\nВведите ваш логин:"
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Сбросить данные входа", callback_data="reset_login")]])
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
        return LOGIN

    permissions = get_role_permissions(role)
    keyboard = []
    if permissions.get("Смена статуса проекта", False):
        keyboard.append([InlineKeyboardButton("Смена статуса проекта", callback_data="change_status")])
    if permissions.get("Создать проект", False):
        keyboard.append([InlineKeyboardButton("Создать проект", callback_data="create_project")])
    if permissions.get("Списать материалы", False):
        keyboard.append([InlineKeyboardButton("Списать материалы", callback_data="write_off")])
    if permissions.get("Списание материалов (веб-форма)", False):
        keyboard.append([InlineKeyboardButton("Списание материалов (веб-форма)", callback_data="web_write_off")])
    if permissions.get("Списать материалы на фермы", False):
        keyboard.append([InlineKeyboardButton("Списать материалы на фермы", callback_data="ferma_write_off")])
    if permissions.get("Добавить расход", False):
        keyboard.append([InlineKeyboardButton("Добавить расход", callback_data="add_expense")])
    if permissions.get("Доставка", False):
        keyboard.append([InlineKeyboardButton("Доставка", callback_data="delivery")])
    if permissions.get("Инструмент", False):
        keyboard.append([InlineKeyboardButton("Инструмент", callback_data="instrument")])
    if permissions.get("Новый инструмент", False):
        keyboard.append([InlineKeyboardButton("Новый инструмент", callback_data="new_instrument")])
    if permissions.get("Закупка материалов", False):
        keyboard.append([InlineKeyboardButton("Закупка материалов", callback_data="purchase")])
    if permissions.get("Внести объемы материалов", False):
        keyboard.append([InlineKeyboardButton("Внести объемы материалов", callback_data="volumes")])
    if permissions.get("Обновление КЭШ-а", False):
        keyboard.append([InlineKeyboardButton("Обновление КЭШ-а", callback_data="refresh_cache")])
    # Добавлена кнопка "Сообщить о проблеме" с проверкой разрешения
    if permissions.get("Сообщить о проблеме", False):
        keyboard.append([InlineKeyboardButton("Сообщить о проблеме", callback_data="report_issue")])
    keyboard.append([InlineKeyboardButton("Сбросить данные входа", callback_data="reset_login")])
    text = f"Добро пожаловать, {role}! Выберите действие:"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    logger.info(f"User {update.effective_user.id}: Возврат в меню")
    await main_menu(update, context)
    return ConversationHandler.END

async def refresh_cache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    from sheets import load_caches
    load_caches(force=True)
    logger.info(f"User {update.effective_user.id}: Кэш обновлён")
    await update.callback_query.edit_message_text(
        "Кэш успешно обновлён!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
    )
    return ConversationHandler.END