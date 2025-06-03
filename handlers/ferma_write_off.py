import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import (
    get_projects_list, get_materials_by_category, record_ferma_write_off, caches,
    parse_plate_categories_and_plates
)
from utils import build_project_keyboard

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

FERMA_PROJECT, FERMA_TYPE, FERMA_MATERIAL_CAT, FERMA_MATERIAL, FERMA_CAT, FERMA_PLATE, FERMA_MATERIAL_QUANTITY, FERMA_PLATE_QUANTITY = range(8)

def get_fullname_by_login(login):
    employees = caches.get("employees", [])
    for emp in employees:
        if str(emp.get("Логин", "")) == str(login):
            return emp.get("Ф.И.О", str(login))
    return str(login)

async def start_ferma_write_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    print("!!! КНОПКА СПИСАТЬ МАТЕРИАЛЫ НА ФЕРМЫ НАЖАТА !!!")
    await update.callback_query.answer()
    role = context.user_data.get("role", "")
    projects = get_projects_list(role)
    if not projects:
        await update.callback_query.edit_message_text(
            "Нет доступных проектов для списания на фермы.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        return ConversationHandler.END
    context.user_data["ferma_items"] = {}        # Пластины
    context.user_data["ferma_mat_inputs"] = {}   # Материалы
    reply_markup = build_project_keyboard(projects)
    await update.callback_query.edit_message_text(
        "Выберите проект для списания на фермы:", reply_markup=reply_markup
    )
    return FERMA_PROJECT

async def select_ferma_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    tag = query.data.replace("proj_", "")
    context.user_data["ferma_project_id"] = tag
    project = next((p for p in get_projects_list(context.user_data.get("role", "")) if str(p["ID проекта"]) == tag), None)
    if not project:
        await query.edit_message_text(
            f"Проект '{tag}' не найден.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        return ConversationHandler.END
    keyboard = [
        [InlineKeyboardButton("Материалы", callback_data="type_materials")],
        [InlineKeyboardButton("Пластины", callback_data="type_plates")],
        [InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        f"Выбран проект: {project['Номер договора']}. Выберите тип списания:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return FERMA_TYPE

async def select_ferma_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    context.user_data["ferma_type"] = query.data
    if query.data == "type_materials":
        material_categories = caches.get("material_categories", [])
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"matcat_{cat}")] for cat in material_categories]
        keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
        await query.edit_message_text("Выберите категорию материалов:", reply_markup=InlineKeyboardMarkup(keyboard))
        return FERMA_MATERIAL_CAT
    else:
        categories, category_to_plates = parse_plate_categories_and_plates()
        context.user_data["ferma_plate_categories_list"] = categories
        context.user_data["ferma_category_to_plates"] = category_to_plates
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
        await query.edit_message_text("Выберите категорию пластин:", reply_markup=InlineKeyboardMarkup(keyboard))
        return FERMA_CAT

async def select_ferma_material_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    if not query.data.startswith("matcat_"):
        await query.edit_message_text("Ошибка. Неизвестная категория.")
        return ConversationHandler.END
    cat = query.data.replace("matcat_", "")
    context.user_data["ferma_material_category"] = cat
    materials = get_materials_by_category(cat)
    reply_markup = build_materials_keyboard_ferma(materials, context.user_data.get("ferma_mat_inputs", {}), show_submit=True)
    await query.edit_message_text(f"Выберите материал из категории '{cat}':", reply_markup=reply_markup)
    return FERMA_MATERIAL

def build_materials_keyboard_ferma(materials, selected, show_submit=False):
    keyboard = []
    for m in materials:
        mat_id = str(m.get("ID") or m.get("id"))
        name = m.get("Наименование") or m.get("name")
        unit = m.get("Ед. измерения", m.get("unit", "шт"))
        qty = selected.get(mat_id, {}).get("quantity", "")
        label = f"{name} ({qty})" if qty else f"{name} ({unit})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"mat_{mat_id}")])
    if show_submit:
        keyboard.append([InlineKeyboardButton("Отправить отчёт", callback_data="submit")])
    keyboard.append([InlineKeyboardButton("Вернуться к категориям", callback_data="back_to_cat_materials")])
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def build_plates_keyboard_ferma(plates, selected, show_submit=False):
    keyboard = []
    for plate in plates:
        plate_id = str(plate.get("ID") or plate.get("id", ""))
        plate_name = plate.get("Наименование") or plate.get("name")
        unit = plate.get("Ед. измерения", plate.get("unit", "шт"))
        qty = selected.get(plate_id, {}).get("quantity", "")
        label = f"{plate_name} ({qty})" if qty else f"{plate_name} ({unit})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"plate_{plate_id}")])
    if show_submit:
        keyboard.append([InlineKeyboardButton("Отправить отчёт", callback_data="submit")])
    keyboard.append([InlineKeyboardButton("Назад к категориям", callback_data="back_to_cat_plates")])
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

async def select_ferma_material(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "submit":
        return await submit_ferma(update, context)
    if query.data == "back_to_cat_materials":
        material_categories = caches.get("material_categories", [])
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"matcat_{cat}")] for cat in material_categories]
        keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
        await query.edit_message_text("Выберите категорию материалов:", reply_markup=InlineKeyboardMarkup(keyboard))
        return FERMA_MATERIAL_CAT
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    if query.data.startswith("mat_"):
        mat_id = query.data.replace("mat_", "")
        context.user_data["ferma_current_material_id"] = mat_id
        cat = context.user_data.get("ferma_material_category", "")
        materials = get_materials_by_category(cat)
        material = next((m for m in materials if str(m.get("ID") or m.get("id")) == mat_id), None)
        unit = material["Ед. измерения"] if material else "шт"
        name = material["Наименование"] if material else mat_id
        await query.edit_message_text(f"Введите количество для {name} ({unit}):")
        return FERMA_MATERIAL_QUANTITY

async def enter_ferma_material_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    quantity_text = update.message.text.strip()
    try:
        quantity = float(quantity_text.replace(",", "."))
        if quantity <= 0:
            await update.message.reply_text("Количество должно быть положительным.")
            return FERMA_MATERIAL_QUANTITY
    except ValueError:
        await update.message.reply_text("Введите корректное число:")
        return FERMA_MATERIAL_QUANTITY
    item_id = context.user_data.get("ferma_current_material_id", "")
    context.user_data.setdefault("ferma_mat_inputs", {})[str(item_id)] = {"quantity": quantity}
    cat = context.user_data.get("ferma_material_category", "")
    materials = get_materials_by_category(cat)
    reply_markup = build_materials_keyboard_ferma(materials, context.user_data["ferma_mat_inputs"], show_submit=True)
    await update.message.reply_text("Выберите следующий материал или отправьте:", reply_markup=reply_markup)
    return FERMA_MATERIAL

# ------------------------ Пластины --------------------------

async def select_plate_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cat = query.data.replace("cat_", "")
    context.user_data["ferma_plate_category"] = cat
    category_to_plates = context.user_data.get("ferma_category_to_plates", {})
    plates = category_to_plates.get(cat, [])
    reply_markup = build_plates_keyboard_ferma(plates, context.user_data.get("ferma_items", {}), show_submit=True)
    await query.edit_message_text(f"Выберите пластину категории {cat}:", reply_markup=reply_markup)
    return FERMA_PLATE

async def select_ferma_plate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "submit":
        return await submit_ferma(update, context)
    if query.data == "back_to_cat_plates":
        categories = context.user_data.get("ferma_plate_categories_list", [])
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
        await query.edit_message_text("Выберите категорию пластин:", reply_markup=InlineKeyboardMarkup(keyboard))
        return FERMA_CAT
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    if query.data.startswith("plate_"):
        plate_id = query.data.replace("plate_", "")
        context.user_data["ferma_current_plate_id"] = plate_id
        cat = context.user_data.get("ferma_plate_category", "")
        category_to_plates = context.user_data.get("ferma_category_to_plates", {})
        plates = category_to_plates.get(cat, [])
        plate = next((p for p in plates if str(p.get("ID") or p.get("id")) == plate_id), None)
        unit = plate.get("Ед. измерения", plate.get("unit", "шт")) if plate else "шт"
        name = plate.get("Наименование", plate.get("name", plate_id)) if plate else plate_id
        await query.edit_message_text(f"Введите количество для {name} ({unit}):")
        return FERMA_PLATE_QUANTITY

async def enter_ferma_plate_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    quantity_text = update.message.text.strip()
    try:
        quantity = float(quantity_text.replace(",", "."))
        if quantity <= 0:
            await update.message.reply_text("Количество должно быть положительным.")
            return FERMA_PLATE_QUANTITY
    except ValueError:
        await update.message.reply_text("Введите корректное число:")
        return FERMA_PLATE_QUANTITY
    item_id = context.user_data.get("ferma_current_plate_id", "")
    context.user_data.setdefault("ferma_items", {})[str(item_id)] = {"quantity": quantity}
    cat = context.user_data.get("ferma_plate_category", "")
    category_to_plates = context.user_data.get("ferma_category_to_plates", {})
    plates = category_to_plates.get(cat, [])
    reply_markup = build_plates_keyboard_ferma(plates, context.user_data["ferma_items"], show_submit=True)
    await update.message.reply_text("Выберите следующую пластину или отправьте:", reply_markup=reply_markup)
    return FERMA_PLATE

# --- submit для обоих сценариев (материалы и пластины) ---
async def submit_ferma(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ferma_items = context.user_data.get("ferma_items", {})
    ferma_mat_inputs = context.user_data.get("ferma_mat_inputs", {})
    project_id = context.user_data.get("ferma_project_id", "")
    project = next((p for p in get_projects_list(context.user_data.get("role", "")) if str(p["ID проекта"]) == project_id), {})
    project_num = project.get("Номер договора", project_id)
    direction = "Фермы"
    fullname = get_fullname_by_login(context.user_data.get("login", ""))
    records = []

    # Материалы:
    for item_id, v in ferma_mat_inputs.items():
        cat = None
        for mat_cat in caches.get("material_categories", []):
            mats = get_materials_by_category(mat_cat)
            material = next((m for m in mats if str(m.get("ID") or m.get("id")) == item_id), None)
            if material:
                cat = material
                break
        name = cat.get("Наименование") if cat else item_id
        records.append([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Расход", fullname, "", direction,
            name, v["quantity"], "", "", "", project_num
        ])

    # Пластины:
    if ferma_items:
        category_to_plates = context.user_data.get("ferma_category_to_plates", {})
        id_to_name = {}
        for cat_list in category_to_plates.values():
            for plate in cat_list:
                pid = str(plate.get("ID") or plate.get("id"))
                pname = plate.get("Наименование") or plate.get("name")
                id_to_name[pid] = pname
        for item_id, v in ferma_items.items():
            name = id_to_name.get(str(item_id), str(item_id))
            records.append([
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Расход", fullname, "", direction,
                name, v["quantity"], "", "", "", project_num
            ])
    if not records:
        await query.edit_message_text("Не выбрано ни одного материала для списания.")
        return ConversationHandler.END

    if record_ferma_write_off(records):
        text = f"Материалы списаны для проекта {project_num} (отдел: {direction}):\n"
        for r in records:
            text += f"{r[5]}: {r[6]}\n"
        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
    else:
        await query.message.reply_text(
            "Ошибка при записи списания.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
    return ConversationHandler.END
