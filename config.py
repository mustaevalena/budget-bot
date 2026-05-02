import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
# GOOGLE_CREDENTIALS_JSON читается напрямую в sheets.py через os.environ

CATEGORIES = [
    "гипермаркет+аптека",
    "рестораны, кофе, обеды",
    "школа/ситтер",
    "наличные на ситтера",
    "наличные на гипермаркет",
    "квартира",
    "хобби/спорт",
    "интернет и телефон",
    "штрафы, налоги, комиссии",
    "развлечения/праздники",
    "одежда+обувь",
    "такси",
    "красота",
    "врачи",
    "общественный транспорт",
    "дом",
    "машина",
]

MONTH_NAMES = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}

# ConversationHandler states
CONFIRMING = 1
CHOOSING_CATEGORY = 2
EDITING_FIELD = 3
