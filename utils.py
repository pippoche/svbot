from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def build_project_keyboard(projects, include_manual=False):
    keyboard = [
        [InlineKeyboardButton(
            f"{p['Номер договора']} ({p['Ф.И.О заказчика']})",
            callback_data=f"proj_{p['ID проекта']}")
        ]
        for p in projects if p.get('ID проекта')
    ]
    if include_manual:
        keyboard.append([InlineKeyboardButton("Ввести номер договора вручную", callback_data="manual")])
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def build_material_keyboard(materials, mat_inputs=None, show_submit=False):
    mat_inputs = mat_inputs or {}
    keyboard = []
    keyboard.append([InlineKeyboardButton("Ввести материал вручную", callback_data="manual_material")])
    for mat in materials:
        # Поддерживаем оба варианта — если структура вдруг разная
        mat_id = str(mat.get("ID") or mat.get("id"))
        mat_name = mat.get("Наименование", mat.get("name"))
        unit = mat.get("Ед. измерения", mat.get("unit", "шт"))
        qty = mat_inputs.get(mat_id, {}).get('quantity', '')
        label = f"{mat_name} ({qty})" if qty else f"{mat_name} ({unit})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"mat_{mat_id}")])
    if show_submit and mat_inputs:
        keyboard.append([InlineKeyboardButton("Отправить отчёт", callback_data="submit")])
    keyboard.append([build_cancel_button()])
    return InlineKeyboardMarkup(keyboard)

def build_instrument_keyboard(instruments, selected_instruments, show_submit=True):
    keyboard = []
    for instr in instruments:
        instr_id = str(instr.get('ID инструмента') or instr.get('id'))
        name = instr.get("Инструмент") or instr.get("name")
        qty = selected_instruments.get(instr_id, 0)
        button_text = f"{name} ({qty})" if qty else f"{name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"inst_{instr_id}")])
    if show_submit and selected_instruments:
        keyboard.append([InlineKeyboardButton("Отправить отчёт", callback_data="submit")])
    keyboard.append([InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def build_cancel_button():
    return InlineKeyboardButton("Вернуться в меню", callback_data="main_menu")

def get_cancel_keyboard():
    return InlineKeyboardMarkup([[build_cancel_button()]])
