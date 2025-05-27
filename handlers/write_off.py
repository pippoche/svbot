import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import (
    get_projects_list, get_project_direction, get_materials_by_category, record_write_off, caches
)
from utils import build_project_keyboard, build_material_keyboard

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SELECT_PROJECT, SELECT_CATEGORY, SELECT_MATERIAL, ENTER_QUANTITY, SUBMIT = range(1, 6)

def get_fullname_by_login(login):
    employees = caches.get("employees", [])
    for emp in employees:
        if str(emp.get("Логин", "")) == str(login):
            return emp.get("Ф.И.О", str(login))
    return str(login)

async def start_write_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    role = context.user_data.get("role", "")
    user_id = update.effective_user.id
    logger.info(f"User {user_id}: Начало списания материалов, роль={role}")
    projects = get_projects_list(role)
    if not projects:
        await update.callback_query.message.reply_text("Нет доступных проектов для списания.")
        logger.warning(f"User {user_id}: Проекты не найдены")
        return ConversationHandler.END
    reply_markup = build_project_keyboard(projects, include_manual=True)
    # Сброс только при старте!
    context.user_data["mat_inputs"] = {}
    await update.callback_query.edit_message_text("Выберите проект для списания:", reply_markup=reply_markup)
    return SELECT_PROJECT

async def select_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "manual":
        await query.edit_message_text("Введите номер договора вручную:")
        return SELECT_PROJECT
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    tag = query.data.replace("proj_", "")
    role = context.user_data.get("role", "")
    project = next((p for p in get_projects_list(role) if str(p["ID проекта"]) == tag), None)
    if not project:
        logger.warning(f"Проект '{tag}' не найден")
        await query.edit_message_text(f"Проект '{tag}' не найден.")
        return ConversationHandler.END
    context.user_data["project_id"] = tag
    logger.info(f"Выбран проект '{project['Номер договора']}' (ID: {tag}) со статусом '{project['Статус']}'")
    material_categories = caches.get("material_categories", [])
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in material_categories]
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    await query.edit_message_text("Выберите категорию материалов:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_CATEGORY

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    if not query.data.startswith("cat_"):
        await query.edit_message_text("Ошибка. Неизвестная категория.")
        return ConversationHandler.END
    cat = query.data.replace("cat_", "")
    context.user_data["material_category"] = cat
    # НЕ сбрасываем mat_inputs!
    if "mat_inputs" not in context.user_data:
        context.user_data["mat_inputs"] = {}
    materials = get_materials_by_category(cat)
    if not materials:
        await query.edit_message_text("Нет материалов в выбранной категории.")
        return ConversationHandler.END
    reply_markup = build_material_keyboard(materials, context.user_data.get("mat_inputs", {}), show_submit=True)
    keyboard = list(reply_markup.inline_keyboard) if reply_markup else []
    keyboard.append([InlineKeyboardButton("Вернуться к категориям", callback_data="back_to_categories")])
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    await query.edit_message_text(f"Выберите материалы из категории '{cat}':", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_MATERIAL

async def select_material(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "submit":
        return await submit_materials(update, context)
    if query.data == "manual_material":
        await query.edit_message_text("Введите название материала вручную:")
        return SELECT_MATERIAL
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    if query.data == "back_to_categories":
        material_categories = caches.get("material_categories", [])
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in material_categories]
        keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
        await query.edit_message_text("Выберите категорию материалов:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_CATEGORY
    if query.data.startswith("mat_"):
        mat_id = query.data.replace("mat_", "")
        context.user_data["current_material_id"] = mat_id
        cat = context.user_data.get("material_category", "")
        materials = get_materials_by_category(cat)
        material = next((m for m in materials if str(m.get("ID") or m.get("id")) == mat_id), None)
        unit = material["Ед. измерения"] if material else "шт"
        name = material["Наименование"] if material else mat_id
        await query.edit_message_text(f"Введите количество для {name} ({unit}):")
        return ENTER_QUANTITY

async def enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        quantity = float(update.message.text.strip().replace(",", "."))
        if quantity <= 0:
            await update.message.reply_text("Количество должно быть положительным.")
            return ENTER_QUANTITY
    except ValueError:
        await update.message.reply_text("Введите корректное число:")
        return ENTER_QUANTITY
    mat_id = context.user_data.get("current_material_id", "")
    context.user_data.setdefault("mat_inputs", {})[mat_id] = {"quantity": quantity}
    cat = context.user_data.get("material_category", "")
    materials = get_materials_by_category(cat)
    reply_markup = build_material_keyboard(materials, context.user_data["mat_inputs"], show_submit=True)
    keyboard = list(reply_markup.inline_keyboard) if reply_markup else []
    keyboard.append([InlineKeyboardButton("Вернуться к категориям", callback_data="back_to_categories")])
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    await update.message.reply_text("Выберите следующий материал или подтвердите:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_MATERIAL

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
        logger.warning(f"Проект '{tag}' не найден при ручном вводе")
        await update.message.reply_text("Проект не найден. Попробуйте снова:")
        return SELECT_PROJECT
    project_id = project["ID проекта"]
    context.user_data["project_id"] = project_id
    logger.info(f"Вручную выбран проект '{tag}' (ID: {project_id}) со статусом '{project['Статус']}'")
    material_categories = caches.get("material_categories", [])
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in material_categories]
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    await update.message.reply_text("Выберите категорию материалов:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_CATEGORY

async def manual_material(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Введите название материала вручную:")
    return SELECT_MATERIAL

async def manual_material_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    material = update.message.text.strip()
    context.user_data["current_material_id"] = material
    await update.message.reply_text(f"Введите количество для {material} (шт):")
    return ENTER_QUANTITY

async def submit_materials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    mat_inputs = context.user_data.get("mat_inputs", {})
    project_id = context.user_data.get("project_id", "unknown")
    project = next((p for p in get_projects_list(context.user_data.get("role", "")) if str(p["ID проекта"]) == project_id), {})
    project_num = project.get("Номер договора", project_id)
    department = context.user_data.get("department", "Строительство")
    # Собираем материалы всех категорий!
    all_materials = {}
    material_categories = caches.get("material_categories", [])
    for cat in material_categories:
        for m in get_materials_by_category(cat):
            all_materials[str(m.get("ID") or m.get("id"))] = m.get("Наименование", m.get("name"))
    id_to_name = all_materials
    if not mat_inputs:
        await query.edit_message_text("Не выбраны материалы для списания.")
        return ConversationHandler.END
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    login = str(context.user_data.get("login", "unknown"))
    fullname = get_fullname_by_login(login)
    records = [
        [date, "Расход", fullname, "", department, id_to_name.get(str(mat_id), str(mat_id)), info["quantity"], "", "", "", project_num]
        for mat_id, info in mat_inputs.items()
    ]
    if record_write_off(records):
        text = f"Материалы списаны для проекта {project_num} (отдел: {department}):\n" + "\n".join(
            f"{id_to_name.get(str(mat_id), str(mat_id))}: {info['quantity']}" for mat_id, info in mat_inputs.items()
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]]))
    else:
        await query.edit_message_text(
            "Ошибка при записи списания.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]]))
    return ConversationHandler.END
