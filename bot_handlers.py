# bot_handlers.py
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from handlers import start, write_off, expense, project, status_change, ferma_write_off, delivery, instrument, new_instrument, web_write_off, purchase
from handlers.report_issue import start_report_issue, save_issue, back_to_menu  # Добавлен импорт для report_issue
import logging

logger = logging.getLogger(__name__)

def register_handlers(application: Application):
    auth_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start.start)],
        states={
            start.LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, start.login)],
            start.PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, start.password)],
        },
        fallbacks=[CallbackQueryHandler(start.reset_login, pattern="reset_login")],
        per_message=False
    )
    application.add_handler(auth_conv)
    application.add_handler(CallbackQueryHandler(start.reset_login, pattern="reset_login"))

    write_off_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(write_off.start_write_off, pattern="write_off")],
        states={
            write_off.SELECT_PROJECT: [
                CallbackQueryHandler(write_off.select_project),
                CallbackQueryHandler(write_off.manual_project, pattern="manual"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, write_off.manual_project_tag)
            ],
            write_off.SELECT_CATEGORY: [
                CallbackQueryHandler(write_off.select_category),
            ],
            write_off.SELECT_MATERIAL: [
                CallbackQueryHandler(write_off.select_material),
                CallbackQueryHandler(write_off.manual_material, pattern="manual_material"),
                CallbackQueryHandler(write_off.submit_materials, pattern="submit"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, write_off.manual_material_entry),
                MessageHandler(filters.TEXT & ~filters.COMMAND, write_off.enter_quantity)
            ],
            write_off.ENTER_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, write_off.enter_quantity)
            ],
        },
        fallbacks=[CallbackQueryHandler(start.back_to_menu, pattern="main_menu")],
        per_message=False
    )
    application.add_handler(write_off_conv)

    expense_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(expense.start_add_expense, pattern="add_expense")],
        states={
            expense.SELECT_PROJECT: [CallbackQueryHandler(expense.select_project)],  # pattern убран!
            expense.ENTER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense.enter_details)],
            expense.SUBMIT_EXPENSE: [CallbackQueryHandler(expense.submit_expense, pattern="submit")]
        },
        fallbacks=[CallbackQueryHandler(start.back_to_menu, pattern="main_menu")],
        per_message=False
    )
    application.add_handler(expense_conv)

    project_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(project.project_entry, pattern="create_project")],
        states={
            project.PROJECT_CUSTOMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, project.project_customer)],
            project.PROJECT_TAG: [MessageHandler(filters.TEXT & ~filters.COMMAND, project.project_tag)],
            project.PROJECT_DIRECTION: [CallbackQueryHandler(project.project_direction, pattern=r"^(?!main_menu$).*$")]
        },
        fallbacks=[CallbackQueryHandler(start.back_to_menu, pattern="main_menu")],
        per_message=False
    )
    application.add_handler(project_conv)

    status_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(status_change.start_status_change, pattern="change_status")],
        states={
            status_change.STATUS_TAG: [CallbackQueryHandler(status_change.status_tag)],  # pattern убран!
            status_change.STATUS_CHANGE: [CallbackQueryHandler(status_change.status_change, pattern=r"^(?!main_menu$).*$")]
        },
        fallbacks=[CallbackQueryHandler(start.back_to_menu, pattern="main_menu")],
        per_message=False
    )
    application.add_handler(status_conv)

    ferma_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ferma_write_off.start_ferma_write_off, pattern="ferma_write_off")],
        states={
            ferma_write_off.FERMA_PROJECT: [
                CallbackQueryHandler(ferma_write_off.select_ferma_project)
            ],
            ferma_write_off.FERMA_TYPE: [
                CallbackQueryHandler(ferma_write_off.select_ferma_type)
            ],
            ferma_write_off.FERMA_MATERIAL_CAT: [
                CallbackQueryHandler(ferma_write_off.select_ferma_material_category)
            ],
            ferma_write_off.FERMA_MATERIAL: [
                CallbackQueryHandler(ferma_write_off.select_ferma_material),
                CallbackQueryHandler(ferma_write_off.submit_ferma, pattern="submit"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ferma_write_off.enter_ferma_material_quantity)
            ],
            ferma_write_off.FERMA_CAT: [
                CallbackQueryHandler(ferma_write_off.select_plate_category)
            ],
            ferma_write_off.FERMA_PLATE: [
                CallbackQueryHandler(ferma_write_off.select_ferma_plate),
                CallbackQueryHandler(ferma_write_off.submit_ferma, pattern="submit"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ferma_write_off.enter_ferma_plate_quantity)
            ],
            # ДОБАВЬ вот этот блок!
            ferma_write_off.FERMA_PLATE_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ferma_write_off.enter_ferma_plate_quantity)
            ],
        },
        fallbacks=[CallbackQueryHandler(start.back_to_menu, pattern="main_menu")],
        per_message=False
    )
    application.add_handler(ferma_conv)

    delivery_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delivery.start_delivery, pattern="delivery")],
        states={
            delivery.SELECT_PROJECT: [CallbackQueryHandler(delivery.select_project)],  # pattern убран!
            delivery.SELECT_DEPARTMENT: [CallbackQueryHandler(delivery.select_department, pattern=r"^(Строительство|Производство|Накладные)$")],
            delivery.ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery.enter_amount)],
            delivery.ENTER_NOTE: [
                CallbackQueryHandler(delivery.enter_note, pattern=r"^(skip_note|add_note)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, delivery.process_note)
            ],
            delivery.SUBMIT_DELIVERY: [CallbackQueryHandler(delivery.submit_delivery, pattern="submit")]
        },
        fallbacks=[CallbackQueryHandler(start.back_to_menu, pattern="main_menu")],
        per_message=False
    )
    application.add_handler(delivery_conv)

    instrument_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(instrument.start_instrument, pattern="instrument")],
        states={
            instrument.SELECT_PROJECT: [CallbackQueryHandler(instrument.select_project)],  # pattern убран!
            instrument.TRANSACTION_TYPE: [CallbackQueryHandler(instrument.transaction_type, pattern=r"^(Приход|Расход)$")],
            instrument.RECIPIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, instrument.recipient)],
            instrument.SELECT_INSTRUMENT: [
                CallbackQueryHandler(instrument.select_instrument),  # pattern убран!
                CallbackQueryHandler(instrument.submit_instrument, pattern="submit")
            ],
            instrument.ENTER_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, instrument.enter_quantity)],
            instrument.SUBMIT: [CallbackQueryHandler(instrument.submit_instrument, pattern="submit")]
        },
        fallbacks=[CallbackQueryHandler(start.back_to_menu, pattern="main_menu")],
        per_message=False
    )
    application.add_handler(instrument_conv)

    new_instrument_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_instrument.start_new_instrument, pattern="new_instrument")],
        states={
            new_instrument.ENTER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_instrument.enter_details)],
        },
        fallbacks=[CallbackQueryHandler(start.back_to_menu, pattern="main_menu")],
        per_message=False
    )
    application.add_handler(new_instrument_conv)

    application.add_handler(CallbackQueryHandler(web_write_off.start_web_write_off, pattern="web_write_off"))
    application.add_handler(CallbackQueryHandler(purchase.start_purchase, pattern="purchase"))
    application.add_handler(CallbackQueryHandler(web_write_off.start_web_write_off, pattern="volumes"))
    application.add_handler(CallbackQueryHandler(start.refresh_cache, pattern="refresh_cache"))
    application.add_handler(CallbackQueryHandler(start.back_to_menu, pattern="main_menu"))

    # Добавлен обработчик для "Сообщить о проблеме"
    report_issue_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_report_issue, pattern="^report_issue$")],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_issue)],
        },
        fallbacks=[CallbackQueryHandler(back_to_menu, pattern="^main_menu$")],
        per_message=False
    )
    application.add_handler(report_issue_conv)
