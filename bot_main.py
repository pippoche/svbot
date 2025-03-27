#bot_main.py
import logging
import os
import json
from telegram.ext import Application
from config import BOT_TOKEN
from sheets import load_caches, caches
from bot_handlers import register_handlers
import asyncio

CACHE_FILE = 'cach.json'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def load_cache_from_file():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                loaded_cache = json.load(f)
                caches.update(loaded_cache)
            logger.info("Кэш успешно загружен из файла.")
            return True
        except json.JSONDecodeError:
            logger.warning("Файл кэша повреждён, будет загружен из Google Sheets.")
            return False
    logger.info("Файл кэша отсутствует, загрузка из Google Sheets.")
    return False

def save_cache_to_file():
    import datetime
    def convert_datetime(obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return obj
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(caches, f, ensure_ascii=False, indent=4, default=convert_datetime)
        logger.info("Кэш успешно сохранён в файл.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении кэша: {e}")

async def shutdown(application):
    if application:
        save_cache_to_file()
        await application.stop()
        await application.updater.stop()
        logger.info("Бот завершил работу.")

async def main():
    application = None
    try:
        load_cache_from_file()
        load_caches(force=True)
        save_cache_to_file()

        application = Application.builder().token(BOT_TOKEN).build()
        register_handlers(application)
        logger.info("Бот запущен.")
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            poll_interval=1.0,
            timeout=10,
            drop_pending_updates=True
        )

        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            logger.info("Получен сигнал завершения, останавливаем бота.")
            stop_event.set()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise
    finally:
        await shutdown(application)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")