# handlers/write_off.py
import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import get_projects_list, get_project_direction, get_materials_by_direction, record_write_off, caches
from utils import build_project_keyboard, build_material_keyboard

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

SELECT_PROJECT, SELECT_MATERIAL, ENTER_QUANTITY, SUBMIT = range(1, 5)

async def start_write_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    role = context.user_data.get("role", "")
    user_id = update.effective_user.id
    logger.info(f"User {user_id}: Начало списания материалов, роль={role}")
    projects = get_projects_list(role)
    logger.info(f"User {user_id}: Найдено {len(projects)} проектов для списания")
    logger.debug(f"User {user_id}: Список проектов: {projects}")
    if not projects:
        await update.callback_query.message.reply_text("Нет доступных проектов для списания.")
        logger.warning(f"User {user_id}: Проекты не найдены")
        return ConversationHandler.END
    reply_markup = build_project_keyboard(projects, include_manual=True)
    await update.callback_query.edit_message_text("Выберите проект для списания:", reply_markup=reply_markup)
    return SELECT_PROJECT

async def select_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    tag = query.data.replace("proj_", "")
    role = context.user_data.get("role", "")
    project = next((p for p in get_projects_list(role) if str(p["Номер договора"]) == tag), None)
    if not project:
        logger.warning(f"User {user_id}: Проект '{tag}' не найден")
        await query.edit_message_text(f"Проект '{tag}' не найден.")
        return ConversationHandler.END
    context.user_data["project_tag"] = tag
    logger.info(f"User {user_id}: Выбран проект '{tag}' со статусом '{project['Статус']}'")
    direction = get_project_direction(tag)
    materials = get_materials_by_direction(direction)
    context.user_data["mat_inputs"] = {}
    reply_markup = build_material_keyboard(materials, context.user_data.get("mat_inputs", {}), show_submit=True)
    await query.edit_message_text(f"Выберите материалы для списания на {tag}:", reply_markup=reply_markup)
    return SELECT_MATERIAL

async def enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    material = query.data.replace("mat_", "")
    context.user_data["current_material"] = material
    direction = get_project_direction(context.user_data.get("project_tag", ""))
    materials = get_materials_by_direction(direction)
    unit = next((m["unit"] for m in materials if m["name"] == material), "шт")
    await query.edit_message_text(f"Введите количество для {material} ({unit}):")
    return ENTER_QUANTITY

async def manual_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Введите номер договора вручную:")
    return SELECT_PROJECT

async def manual_project_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    tag = update.message.text.strip()
    role = context.user_data.get("role", "")
    project = next((p for p in get_projects_list(role) if str(p["Номер договора"]) == tag), None)
    if not project:
        logger.warning(f"User {user_id}: Проект '{tag}' не найден при ручном вводе")
        await update.message.reply_text("Проект не найден. Попробуйте снова:")
        return SELECT_PROJECT
    context.user_data["project_tag"] = tag
    logger.info(f"User {user_id}: Вручную выбран проект '{tag}' со статусом '{project['Статус']}'")
    direction = get_project_direction(tag)
    materials = get_materials_by_direction(direction)
    context.user_data["mat_inputs"] = {}
    reply_markup = build_material_keyboard(materials, context.user_data.get("mat_inputs", {}), show_submit=True)
    await update.message.reply_text(f"Выберите материалы для списания на {tag}:", reply_markup=reply_markup)
    return SELECT_MATERIAL

async def manual_material(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Введите название материала:")
    return SELECT_MATERIAL

async def manual_material_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    material = update.message.text.strip()
    context.user_data["current_material"] = material
    await update.message.reply_text(f"Введите количество для {material} (шт):")
    return ENTER_QUANTITY

async def confirm_material(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    try:
        quantity = float(update.message.text.strip().replace(",", "."))
        if quantity <= 0:
            logger.warning(f"User {user_id}: Количество {quantity} не положительное")
            await update.message.reply_text("Количество должно быть положительным.")
            return ENTER_QUANTITY
    except ValueError:
        logger.warning(f"User {user_id}: Неверное число для количества: {update.message.text}")
        await update.message.reply_text("Введите корректное число:")
        return ENTER_QUANTITY
    material = context.user_data.get("current_material", "")
    context.user_data.setdefault("mat_inputs", {})[material] = {"quantity": quantity}
    logger.info(f"User {user_id}: Добавлено {quantity} для {material}")
    direction = get_project_direction(context.user_data.get("project_tag", ""))
    materials = get_materials_by_direction(direction)
    reply_markup = build_material_keyboard(materials, context.user_data["mat_inputs"], show_submit=True)
    await update.message.reply_text("Выберите следующий материал или подтвердите:", reply_markup=reply_markup)
    return SELECT_MATERIAL

async def submit_materials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        logger.debug(f"User {user_id}: Нажата кнопка 'Вернуться в меню' в submit_materials")
        return ConversationHandler.END
    mat_inputs = context.user_data.get("mat_inputs", {})
    project_tag = context.user_data.get("project_tag", "unknown")
    if not mat_inputs:
        logger.warning(f"User {user_id}: Не выбраны материалы для списания")
        await query.edit_message_text("Не выбраны материалы для списания.")
        return ConversationHandler.END
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    login = str(context.user_data.get("login", "unknown"))  # Приводим к строке
    employee_data = next((emp for emp in caches["employees"] if str(emp["Логин"]) == login), None)
    user = employee_data["Ф.И.О"] if employee_data else login  # ФИО или логин
    logger.debug(f"User {user_id}: Login={login}, Employee_data={employee_data}, User={user}")  # Отладка
    direction = context.user_data.get("department", "Строительство")
    records = [
        [date, "Расход", user, "", direction, material, info["quantity"], "", "", "", project_tag]
        for material, info in mat_inputs.items()
    ]
    if record_write_off(records):
        text = f"Материалы списаны для проекта {project_tag} (отдел: {direction}):\n" + "\n".join(
            f"{material}: {info['quantity']}" for material, info in mat_inputs.items()
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.info(f"User {user_id}: Успешно списаны материалы для проекта {project_tag}")
    else:
        await query.edit_message_text(
            "Ошибка при записи списания.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.error(f"User {user_id}: Ошибка списания для проекта {project_tag}")
    return ConversationHandler.END