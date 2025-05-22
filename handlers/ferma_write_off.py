# handlers/ferma_write_off.py
import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from sheets import get_projects_list, get_project_direction, get_materials_by_direction, get_plates_by_type, record_ferma_write_off, caches
from utils import build_project_keyboard, build_material_keyboard, decode_callback_data

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

FERMA_PROJECT, FERMA_TYPE, FERMA_MATERIAL, FERMA_PLATE_TYPE, FERMA_QUANTITY, FERMA_SUBMIT = range(6)

async def start_ferma_write_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    role = context.user_data.get("role", "")
    user_id = update.effective_user.id
    logger.info(f"User {user_id}: Начало списания на фермы, роль={role}")
    context.user_data["ferma_items"] = {}  # Очищаем перед началом нового списания
    projects = get_projects_list(role)
    logger.info(f"User {user_id}: Найдено {len(projects)} проектов для списания на фермы")
    if not projects:
        await update.callback_query.edit_message_text(
            "Нет доступных проектов для списания на фермы.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        return ConversationHandler.END
    reply_markup = build_project_keyboard(projects)
    await update.callback_query.edit_message_text(
        "Выберите проект для списания на фермы:", reply_markup=reply_markup
    )
    return FERMA_PROJECT

async def select_ferma_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    raw = decode_callback_data(query.data)
    tag = raw.replace("proj_", "")
    context.user_data["ferma_project_tag"] = tag
    project = next((p for p in get_projects_list(context.user_data.get("role", "")) if str(p["Номер договора"]) == tag), None)
    if not project:
        logger.warning(f"User {user_id}: Проект '{tag}' не найден")
        await query.edit_message_text(
            f"Проект '{tag}' не найден.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        return ConversationHandler.END
    logger.info(f"User {user_id}: Выбран проект '{tag}' со статусом '{project['Статус']}'")
    keyboard = [
        [InlineKeyboardButton("Материалы", callback_data="type_materials")],
        [InlineKeyboardButton("Пластины", callback_data="type_plates")],
        [InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        f"Выбран проект: {tag}. Выберите тип списания:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return FERMA_TYPE

async def select_ferma_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    context.user_data["ferma_type"] = query.data
    logger.info(f"User {user_id}: Выбран тип списания: {query.data}")
    if query.data == "type_materials":
        direction = get_project_direction(context.user_data["ferma_project_tag"])
        materials = [m for m in get_materials_by_direction(direction) if "Фермы" in m.get("Тип сделки", "").split()]
        if not materials:
            logger.warning(f"User {user_id}: Материалы для ферм не найдены")
            await query.edit_message_text("Материалы для ферм не найдены.")
            return ConversationHandler.END
        reply_markup = build_material_keyboard(materials, context.user_data["ferma_items"], show_submit=True)
        await query.edit_message_text("Выберите материал:", reply_markup=reply_markup)
        return FERMA_MATERIAL
    else:
        from sheets import caches
        all_plates = []
        for plate_type in caches["plate_types"]:
            all_plates.extend(get_plates_by_type(plate_type))
        if not all_plates:
            logger.warning(f"User {user_id}: Пластины не найдены")
            await query.edit_message_text("Пластины не найдены.")
            return ConversationHandler.END
        keyboard = []
        for p in all_plates:
            name = p['name']
            if name in context.user_data["ferma_items"]:
                quantity = context.user_data["ferma_items"][name]["quantity"]
                button_text = f"{name} (выбрано: {quantity})"
            else:
                button_text = name
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"plate_{name}")])
        keyboard.append([InlineKeyboardButton("Отправить отчёт", callback_data="submit")])
        keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
        await query.edit_message_text("Выберите пластину:", reply_markup=InlineKeyboardMarkup(keyboard))
        return FERMA_PLATE_TYPE

async def select_ferma_material(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Тоже для base64, НЕ для "submit"
    if query.data == "submit":
        return await submit_ferma(update, context)

    raw = decode_callback_data(query.data)
    material = raw.replace("mat_", "")
    context.user_data["ferma_current_item"] = material
    direction = get_project_direction(context.user_data.get("ferma_project_tag", ""))
    materials = [m for m in get_materials_by_direction(direction) if "Фермы" in m.get("Тип сделки", "").split()]
    unit = next((m['unit'] for m in materials if m['name'] == material), "шт")
    await query.edit_message_text(f"Введите количество для {material} ({unit}):")
    return FERMA_QUANTITY


async def select_plate_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    elif query.data == "submit":
        return await submit_ferma(update, context)
    plate = query.data.replace("plate_", "")
    context.user_data["ferma_current_item"] = plate
    from sheets import caches
    all_plates = []
    for plate_type in caches["plate_types"]:
        all_plates.extend(get_plates_by_type(plate_type))
    unit = next((p['unit'] for p in all_plates if p['name'] == plate), "шт")
    await query.edit_message_text(f"Введите количество для {plate} ({unit}):")
    return FERMA_QUANTITY

async def enter_ferma_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    quantity_text = update.message.text.strip()
    logger.info(f"User {user_id}: Введено количество: {quantity_text}")
    try:
        quantity = float(quantity_text.replace(",", "."))
        if quantity <= 0:
            logger.warning(f"User {user_id}: Количество {quantity} не положительное")
            await update.message.reply_text("Количество должно быть положительным.")
            return FERMA_QUANTITY
    except ValueError:
        logger.warning(f"User {user_id}: Неверное число для количества: {quantity_text}")
        await update.message.reply_text("Введите корректное число:")
        return FERMA_QUANTITY
    item = context.user_data.get("ferma_current_item", "")
    context.user_data.setdefault("ferma_items", {})[item] = {"quantity": quantity}
    logger.info(f"User {user_id}: Добавлено {quantity} для {item}")
    if context.user_data["ferma_type"] == "type_materials":
        direction = get_project_direction(context.user_data["ferma_project_tag"])
        materials = [m for m in get_materials_by_direction(direction) if "Фермы" in m.get("Тип сделки", "").split()]
        reply_markup = build_material_keyboard(materials, context.user_data["ferma_items"], show_submit=True)
        await update.message.reply_text("Выберите следующий материал или отправьте:", reply_markup=reply_markup)
        return FERMA_MATERIAL
    else:
        from sheets import caches
        all_plates = []
        for plate_type in caches["plate_types"]:
            all_plates.extend(get_plates_by_type(plate_type))
        keyboard = []
        for p in all_plates:
            name = p['name']
            if name in context.user_data["ferma_items"]:
                quantity = context.user_data["ferma_items"][name]["quantity"]
                button_text = f"{name} (выбрано: {quantity})"
            else:
                button_text = name
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"plate_{name}")])
        keyboard.append([InlineKeyboardButton("Отправить отчёт", callback_data="submit")])
        keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
        await update.message.reply_text("Выберите следующую пластину или отправьте:", reply_markup=InlineKeyboardMarkup(keyboard))
        return FERMA_PLATE_TYPE

async def submit_ferma(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "main_menu":
        from handlers.start import back_to_menu
        await back_to_menu(update, context)
        return ConversationHandler.END
    mat_inputs = context.user_data.get("ferma_items", {})
    project_tag = context.user_data.get("ferma_project_tag", "unknown")
    if not mat_inputs:
        logger.warning(f"User {user_id}: Не выбраны материалы для списания")
        await query.edit_message_text(
            "Не выбраны материалы для списания.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        return ConversationHandler.END
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    login = str(context.user_data.get("login", "unknown"))  # Приводим к строке
    employee_data = next((emp for emp in caches["employees"] if str(emp["Логин"]) == login), None)
    user = employee_data["Ф.И.О"] if employee_data else login  # ФИО или логин
    logger.debug(f"User {user_id}: Login={login}, Employee_data={employee_data}, User={user}")  # Отладка
    direction = context.user_data.get("department", "Производство")
    records = [[date, "Расход", user, "", direction, k, v["quantity"], "", "", "", project_tag] for k, v in mat_inputs.items()]
    if record_ferma_write_off(records):
        text = f"Материалы списаны для проекта {project_tag} (отдел: {direction}):\n" + "\n".join([f"{k}: {v['quantity']}" for k, v in mat_inputs.items()])
        await query.message.reply_text(  # Оставляем reply_text, как в твоей исходной версии
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.info(f"User {user_id}: Успешно списаны элементы для проекта {project_tag}")
    else:
        await query.message.reply_text(
            "Ошибка при записи списания.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")]])
        )
        logger.error(f"User {user_id}: Ошибка списания для проекта {project_tag}")
    return ConversationHandler.END