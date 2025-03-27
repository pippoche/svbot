# config.py
from decouple import config
import gspread
from google.oauth2.service_account import Credentials

BOT_TOKEN = config("BOT_TOKEN", default="7572773238:AAHRqTdV3uutzW1t1ugt8fZ8Bo3X-agsslA")
SPREADSHEET_ID = config("SPREADSHEET_ID", default="1qqvqutnkSradMpgji3Yhq3sxpnKg4109i9_bCpr-1VE")
SERVICE_ACCOUNT_FILE = config("SERVICE_ACCOUNT_FILE", default="service_account.json")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
client = gspread.authorize(creds)

ALLOWED_STATUSES = [
    "В работе", "Продукция готова", "Приостановлен", "Проект готов", "Строительство"
]  # Убраны дубли, единый регистр