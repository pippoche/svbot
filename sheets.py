# sheets.py
import datetime
import logging
import threading
import time
from config import client, SPREADSHEET_ID

logger = logging.getLogger(__name__)

__all__ = [
    "load_caches", "record_write_off", "get_project_direction", "update_project_report_link",
    "get_projects_list", "update_project_status", "create_project_record", "get_materials_by_direction",
    "get_employee_data", "get_role_permissions", "can_write_off_at_status", "record_expense",
    "record_instrument_transaction", "add_new_instrument", "record_delivery", "record_ferma_write_off",
    "get_plates_by_type", "get_plate_stock", "get_web_form_url", "get_instruments"
]

HEADERS = ["ID проекта", "Ф.И.О заказчика", "Номер договора", "Тип сделки", "Статус", "Дата создания", "Примечание", "Ссылка на отчёт"]
EMPLOYEE_HEADERS = ["ID", "Ф.И.О", "Логин", "Пароль", "Роль", "Отдел", "Доступ"]
MATERIAL_HEADERS = ["ID", "Наименование", "Ед. измерения", "Тип сделки"]
URL_HEADERS = ["Действие", "URL"]
DATA_HEADERS = ["№ строки", "Дата", "Тип операции", "Кто", "Тип оплаты", "Направление", "что списано/приобретенено", "кол-во", "Ед. измерения", "Цена", "Общая цена", "Номер договора", "Примечание"]
INSTRUMENT_HEADERS = ["ID инструмента", "Инструмент", "Ед. измерения", "Кол-во на складе"]
WHERE_INSTRUMENT_HEADERS = ["№ строки", "Дата", "Тип операции", "Кто", "Номер договора", "Кому выдан инструмент", "Инструмент", "кол-во"]

caches = {
    "projects": None,
    "employees": None,
    "permissions": None,
    "materials": None,
    "plates": None,
    "plate_types": None,
    "urls": None,
    "instruments": None,
    "where_instruments": None,
    "last_updated": None
}

def find_header_row(all_values, required_headers):
    for i, row in enumerate(all_values):
        if all(any(h.lower() in cell.lower() for cell in row) for h in required_headers):
            return i + 1
    return None

def find_last_row(worksheet, column="A"):
    values = worksheet.col_values(1)
    return len(values) if values else 1

def load_caches(force=False):
    global caches
    now = datetime.datetime.now()
    if caches["last_updated"] and not force and (now - caches["last_updated"]).total_seconds() < 3600:
        logger.info("Используется кэшированная версия данных.")
        return
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet_names = [sheet.title for sheet in spreadsheet.worksheets()]
        logger.info(f"Доступные листы в таблице: {sheet_names}")

        projects_sheet = spreadsheet.worksheet("Проекты")
        projects_all_values = projects_sheet.get_all_values()
        projects_header_row = find_header_row(projects_all_values, ["ID проекта", "Номер договора"])
        if projects_header_row is None:
            logger.error("Заголовки таблицы проектов не найдены в листе 'Проекты'.")
            caches["projects"] = []
        else:
            logger.info(f"Заголовки листа 'Проекты' найдены на строке {projects_header_row}: {projects_all_values[projects_header_row - 1]}")
            projects_data = projects_sheet.get_all_records(expected_headers=HEADERS, head=projects_header_row)
            caches["projects"] = sorted(projects_data, key=lambda x: x.get("Дата создания", ""), reverse=True)
            logger.info(f"Проекты загружены, записей: {len(caches['projects'])}")

        employees_sheet = spreadsheet.worksheet("Сотрудники")
        employees_all_values = employees_sheet.get_all_values()
        employees_header_row = find_header_row(employees_all_values, ["ID", "Ф.И.О"])
        if employees_header_row is None:
            logger.error("Заголовки таблицы сотрудников не найдены в листе 'Сотрудники'.")
            caches["employees"] = []
        else:
            logger.info(f"Заголовки листа 'Сотрудники' найдены на строке {employees_header_row}: {employees_all_values[employees_header_row - 1]}")
            employees_data = employees_sheet.get_all_records(expected_headers=EMPLOYEE_HEADERS, head=employees_header_row)
            caches["employees"] = employees_data
            logger.info(f"Сотрудники загружены, записей: {len(caches['employees'])}")

        perms_data = spreadsheet.worksheet("Действия и разрешения").get_all_values()
        caches["permissions"] = perms_data
        logger.info(f"Действия и разрешения загружены, строк: {len(caches['permissions'])}")

        materials_sheet = spreadsheet.worksheet("Материалы")
        materials_all_values = materials_sheet.get_all_values()
        materials_header_row = find_header_row(materials_all_values, ["ID", "Наименование"])
        if materials_header_row is None:
            logger.error("Заголовки таблицы материалов не найдены в листе 'Материалы'.")
            caches["materials"] = []
        else:
            logger.info(f"Заголовки листа 'Материалы' найдены на строке {materials_header_row}: {materials_all_values[materials_header_row - 1]}")
            materials_data = materials_sheet.get_all_records(expected_headers=MATERIAL_HEADERS, head=materials_header_row)
            caches["materials"] = materials_data
            logger.info(f"Материалы загружены, записей: {len(caches['materials'])}")

        plates_data = spreadsheet.worksheet("Пластины МЗП").get_all_values()
        caches["plate_types"] = [row[1] for row in plates_data[1:6] if row and row[1] and row[1] != "Тип пластин"]
        caches["plates"] = plates_data[6:]
        logger.info(f"Типы пластин: {len(caches['plate_types'])}, пластины: {len(caches['plates'])}")

        urls_sheet = spreadsheet.worksheet("URL действия")
        urls_all_values = urls_sheet.get_all_values()
        urls_header_row = find_header_row(urls_all_values, ["Действие", "URL"])
        if urls_header_row is None:
            logger.error("Заголовки таблицы URL не найдены в листе 'URL действия'. Используем пустой словарь.")
            caches["urls"] = {}
        else:
            logger.info(f"Заголовки листа 'URL действия' найдены на строке {urls_header_row}: {urls_all_values[urls_header_row - 1]}")
            urls_data = urls_sheet.get_all_records(expected_headers=URL_HEADERS, head=urls_header_row)
            caches["urls"] = {row["Действие"]: row["URL"] for row in urls_data if row.get("URL", "")}
            logger.info(f"URL действия загружены, записей: {len(caches['urls'])}")

        instruments_sheet = spreadsheet.worksheet("Инструмент")
        instruments_all_values = instruments_sheet.get_all_values()
        instruments_header_row = find_header_row(instruments_all_values, ["ID инструмента", "Инструмент"])
        if instruments_header_row is None:
            logger.error("Заголовки таблицы инструментов не найдены в листе 'Инструмент'.")
            caches["instruments"] = []
        else:
            logger.info(f"Заголовки листа 'Инструмент' найдены на строке {instruments_header_row}: {instruments_all_values[instruments_header_row - 1]}")
            instruments_data = instruments_sheet.get_all_records(expected_headers=INSTRUMENT_HEADERS, head=instruments_header_row)
            caches["instruments"] = instruments_data
            logger.info(f"Инструменты загружены, записей: {len(caches['instruments'])}")

        where_instruments_sheet = spreadsheet.worksheet("Где инструмент")
        where_instruments_all_values = where_instruments_sheet.get_all_values()
        where_instruments_header_row = find_header_row(where_instruments_all_values, ["№ строки", "Дата"])
        if where_instruments_header_row is None:
            logger.error("Заголовки таблицы 'Где инструмент' не найдены.")
            caches["where_instruments"] = []
        else:
            logger.info(f"Заголовки листа 'Где инструмент' найдены на строке {where_instruments_header_row}: {where_instruments_all_values[where_instruments_header_row - 1]}")
            where_instruments_data = where_instruments_sheet.get_all_records(expected_headers=WHERE_INSTRUMENT_HEADERS, head=where_instruments_header_row)
            caches["where_instruments"] = where_instruments_data
            logger.info(f"Где инструмент загружено, записей: {len(caches['where_instruments'])}")

        caches["last_updated"] = now
        logger.info("Данные из Google Sheets загружены в кэш.")
    except Exception as e:
        logger.error(f"Ошибка при загрузке кэшей: {str(e)}", exc_info=True)
        raise

def schedule_cache_update():
    while True:
        now = datetime.datetime.now()
        next_update = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now > next_update:
            next_update += datetime.timedelta(days=1)
        time.sleep((next_update - now).total_seconds())
        load_caches(force=True)
        time.sleep(43200)

threading.Thread(target=schedule_cache_update, daemon=True).start()

def record_write_off(data_list):
    try:
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("Данные")
        last_row = find_last_row(worksheet)
        start_row = last_row + 1
        for i, data in enumerate(data_list):
            row_num = start_row + i
            row = [row_num] + data[:11]  # Ограничиваем до 12 элементов (A:L)
            if len(row) < 12:
                row.extend([""] * (12 - len(row)))
            worksheet.update(f"A{row_num}:L{row_num}", [row])
        logger.info(f"Записано списание: {len(data_list)} строк в диапазоне A:L")
        return True
    except Exception as e:
        logger.error(f"Ошибка записи списания: {e}")
        return False

def record_expense(data_list):
    try:
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("Данные")
        last_row = find_last_row(worksheet)
        start_row = last_row + 1
        for i, data in enumerate(data_list):
            row_num = start_row + i
            row = [row_num] + data[:11]  # До "Номер договора"
            if len(row) < 12:
                row.extend([""] * (12 - len(row)))
            worksheet.update(f"A{row_num}:L{row_num}", [row])
        logger.info(f"Записан расход: {len(data_list)} строк в диапазоне A:L")
        return True
    except Exception as e:
        logger.error(f"Ошибка записи расхода: {e}")
        return False

def record_instrument_transaction(data_list):
    try:
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("Где инструмент")
        last_row = find_last_row(worksheet)
        start_row = last_row + 1
        for i, data in enumerate(data_list):
            row_num = start_row + i
            # Добавляем номер строки как первый элемент
            row = [row_num] + data  # Теперь row имеет 8 элементов (A:H)
            if len(row) < 8:
                row.extend([""] * (8 - len(row)))
            elif len(row) > 8:
                row = row[:8]  # Обрезаем до 8, если больше
            worksheet.update(f"A{row_num}:H{row_num}", [row])
        logger.info(f"Записана транзакция инструмента: {len(data_list)} строк в диапазоне A:H")
        caches["where_instruments"].extend([dict(zip(WHERE_INSTRUMENT_HEADERS, row)) for row in data_list])
        return True
    except Exception as e:
        logger.error(f"Ошибка записи инструмента: {e}")
        return False

def add_new_instrument(name, unit, quantity=0):
    try:
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("Инструмент")
        last_row = find_last_row(worksheet)
        last_id = max([int(row["ID инструмента"] or 0) for row in caches["instruments"]], default=0)
        new_id = last_id + 1
        new_row = [new_id, name, unit, quantity]
        worksheet.update(f"A{last_row + 1}:D{last_row + 1}", [new_row])
        caches["instruments"].append({"ID инструмента": new_id, "Инструмент": name, "Ед. измерения": unit, "Кол-во на складе": quantity})
        logger.info(f"Добавлен инструмент: {name}, {quantity} {unit}")
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления инструмента: {e}")
        return False

def record_delivery(data_list):
    try:
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("Данные")
        last_row = find_last_row(worksheet)
        start_row = last_row + 1
        for i, data in enumerate(data_list):
            row_num = start_row + i
            row = [row_num] + data  # Полный список из 13 элементов (A:M)
            if len(row) < 13:
                row.extend([""] * (13 - len(row)))
            elif len(row) > 13:
                row = row[:13]  # Обрезаем до 13, если больше
            worksheet.update(f"A{row_num}:M{row_num}", [row])
        logger.info(f"Записана доставка: {len(data_list)} строк в диапазоне A:M")
        return True
    except Exception as e:
        logger.error(f"Ошибка записи доставки: {e}")
        return False

def record_ferma_write_off(data_list):
    try:
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("Данные")
        last_row = find_last_row(worksheet)
        start_row = last_row + 1
        for i, data in enumerate(data_list):
            row_num = start_row + i
            row = [row_num] + data[:11]
            if len(row) < 12:
                row.extend([""] * (12 - len(row)))
            worksheet.update(f"A{row_num}:L{row_num}", [row])
        logger.info(f"Записано списание на фермы: {len(data_list)} строк в диапазоне A:L")
        return True
    except Exception as e:
        logger.error(f"Ошибка записи списания на фермы: {e}")
        return False

def get_plates_by_type(plate_type):
    try:
        plates = []
        for row in caches["plates"]:
            if len(row) >= 5 and row[2] == plate_type and row[1]:
                stock = float(row[4] or 0)
                plates.append({
                    "name": row[1],
                    "unit": row[3],
                    "stock": stock
                })
        return plates
    except Exception as e:
        logger.error(f"Ошибка получения пластин по типу {plate_type}: {e}")
        return []

def get_plate_stock(plate_name):
    try:
        for row in caches["plates"]:
            if len(row) > 1 and row[1] == plate_name:
                return float(row[4] or 0)
        return None
    except Exception as e:
        logger.error(f"Ошибка получения остатка пластины {plate_name}: {e}")
        return None

def get_project_direction(tag):
    try:
        for record in caches["projects"] or []:
            if str(record["Номер договора"]).strip().lower() == str(tag).strip().lower():
                return record.get("Тип сделки", "")
        return None
    except Exception as e:
        logger.error(f"Ошибка получения направления проекта: {e}")
        return None

def update_project_report_link(tag, url):
    try:
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("Проекты")
        cell = worksheet.find(str(tag))
        if cell:
            worksheet.update_cell(cell.row, HEADERS.index("Ссылка на отчёт") + 1, url)
            for proj in caches["projects"]:
                if proj["Номер договора"] == tag:
                    proj["Ссылка на отчёт"] = url
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка обновления ссылки отчета: {e}")
        return False


def get_projects_list(role=None):
    try:
        projects = caches["projects"] or []
        logger.info(f"Всего проектов в кэше: {len(projects)}")
        if not role:
            logger.info("Роль не указана, возвращаем все проекты")
            return projects
        role_lower = role.lower()
        perms = next((row for row in caches["permissions"] if row and row[0].lower() == role_lower), None)
        if not perms or len(perms) < 2:
            logger.warning(f"Разрешения для роли {role} не найдены.")
            return []

        # Получаем разрешённые статусы (столбец B)
        visible_statuses_raw = perms[1] if perms[1] else ""
        visible_statuses = visible_statuses_raw.split()  # Разбиваем по пробелам
        # Собираем статусы вручную, учитывая составные ("В работе", "Продукция готова")
        statuses = []
        i = 0
        while i < len(visible_statuses):
            if i + 1 < len(visible_statuses) and visible_statuses[i] in ["В", "Продукция"]:
                statuses.append(f"{visible_statuses[i]} {visible_statuses[i+1]}")
                i += 2
            else:
                statuses.append(visible_statuses[i])
                i += 1
        logger.info(f"Видимые статусы для роли '{role}': {statuses}")

        # Фильтруем проекты
        filtered_projects = []
        for p in projects:
            project_status = p.get("Статус", "").lower().replace(" ", "")
            for status in statuses:
                if project_status == status.lower().replace(" ", ""):
                    filtered_projects.append(p)
                    logger.debug(f"Проект '{p.get('Номер договора')}' со статусом '{p.get('Статус')}' добавлен для роли '{role}'")
                    break
            else:
                logger.debug(f"Проект '{p.get('Номер договора')}' со статусом '{p.get('Статус')}' исключён для роли '{role}'")
        logger.info(f"Для роли '{role}' найдено {len(filtered_projects)} проектов.")
        return filtered_projects
    except Exception as e:
        logger.error(f"Ошибка получения списка проектов: {e}")
        return []

def update_project_status(tag, new_status):
    try:
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("Проекты")
        cell = worksheet.find(str(tag))
        if cell:
            worksheet.update_cell(cell.row, HEADERS.index("Статус") + 1, new_status)
            for proj in caches["projects"]:
                if proj["Номер договора"] == tag:
                    proj["Статус"] = new_status
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка обновления статуса: {e}")
        return False

def create_project_record(customer_name, tag, direction):
    try:
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet("Проекты")
        new_id = max([float(row["ID проекта"]) for row in caches["projects"] if row["ID проекта"]], default=0) + 1
        status = "В работе"
        date_created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [new_id, customer_name, tag, direction, status, date_created, "", ""]
        worksheet.append_row(new_row)
        caches["projects"].append(dict(zip(HEADERS, new_row)))
        return True
    except Exception as e:
        logger.error(f"Ошибка создания проекта: {e}")
        return False

def get_materials_by_direction(direction):
    try:
        materials = []
        for row in caches["materials"]:
            if not direction:
                materials.append({"name": row["Наименование"], "unit": row["Ед. измерения"], "Тип сделки": row["Тип сделки"]})
            else:
                types = row["Тип сделки"].lower().split()
                if "все" in types or direction.rstrip("ы").lower() in types:
                    materials.append({"name": row["Наименование"], "unit": row["Ед. измерения"], "Тип сделки": row["Тип сделки"]})
        return materials
    except Exception as e:
        logger.error(f"Ошибка получения материалов для {direction}: {e}")
        return []

def get_instruments():
    try:
        instruments = []
        for row in caches["instruments"]:
            if row.get("Инструмент") and row["Инструмент"].strip():  # Фильтруем пустые строки
                try:
                    stock = float(row["Кол-во на складе"] or 0)
                except (ValueError, TypeError):
                    stock = 0
                instruments.append({
                    "id": row["ID инструмента"],
                    "name": row["Инструмент"],
                    "unit": row["Ед. измерения"],
                    "stock": stock
                })
        logger.info(f"Инструменты загружены, записей: {len(instruments)}")
        return instruments
    except Exception as e:
        logger.error(f"Ошибка получения инструментов: {e}")
        return []

def get_employee_data(login, password):
    try:
        for emp in caches["employees"]:
            if str(emp["Логин"]).strip() == str(login).strip() and str(emp["Пароль"]).strip() == str(password).strip():
                if str(emp["Доступ"]).lower() in ["true", "1", "yes"]:
                    return emp["Роль"], emp["Отдел"]
                return None, None
        return None, None
    except Exception as e:
        logger.error(f"Ошибка проверки учетных данных: {e}")
        return None, None

def get_role_permissions(role):
    try:
        perms_row = next((row for row in caches["permissions"] if row and row[0].lower() == role.lower()), None)
        if not perms_row or len(perms_row) < 3:
            logger.warning(f"Роль '{role}' не найдена в таблице.")
            return {}

        actions_str = perms_row[2].strip().replace("  ", " ")
        possible_actions = [
            "Смена статуса проекта", "Создать проект", "Списать материалы",
            "Списание материалов (веб-форма)", "Списать материалы на фермы",
            "Добавить расход", "Доставка", "Инструмент", "Новый инструмент",
            "Закупка материалов", "Внести объемы материалов", "Обновление КЭШ-а"
        ]

        permissions_dict = {action: action in actions_str for action in possible_actions}
        logger.info(f"Права для роли '{role}': {permissions_dict}")
        return permissions_dict
    except Exception as e:
        logger.error(f"Ошибка получения прав роли '{role}': {e}")
        return {}

def can_write_off_at_status(role, status, action="Списать материалы"):
    try:
        perms_row = next((row for row in caches["permissions"] if row and row[0].lower() == role.lower()), None)
        if not perms_row or len(perms_row) < 3:
            return False
        statuses = perms_row[1].split() if perms_row[1] else []
        status_lower = status.lower().replace(" ", "")
        allowed_status = any(status_lower == s.lower().replace(" ", "") for s in statuses)
        allowed_action = action in perms_row[2]
        return allowed_status and allowed_action
    except Exception as e:
        logger.error(f"Ошибка проверки статуса для списания: {e}")
        return False

def get_web_form_url(action):
    try:
        return caches["urls"].get(action, "")
    except Exception as e:
        logger.error(f"Ошибка получения URL для {action}: {e}")
        return ""

if __name__ == "__main__":
    load_caches()