import json
import os
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import MONTH_NAMES, SPREADSHEET_ID

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_HEADERS = ["Дата", "Магазин / получатель", "Сумма, RSD", "Категория", "Комментарий"]


def _get_service():
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _sheet_name(date_str: str) -> str:
    month_num = int(date_str.split(".")[1])
    year = datetime.now().year
    return f"{MONTH_NAMES[month_num]} {year}"


def _get_sheet_names(service) -> list[str]:
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    return [s["properties"]["title"] for s in meta["sheets"]]


def _create_sheet(service, name: str) -> None:
    body = {"requests": [{"addSheet": {"properties": {"title": name}}}]}
    service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()
    # write headers
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{name}'!A1:E1",
        valueInputOption="RAW",
        body={"values": [_HEADERS]},
    ).execute()


def append_transaction(date: str, merchant: str, amount: int, category: str, comment: str = "") -> None:
    service = _get_service()
    sheet_name = _sheet_name(date)

    existing = _get_sheet_names(service)
    if sheet_name not in existing:
        _create_sheet(service, sheet_name)

    row = [date, merchant, amount, category, comment]
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_name}'!A:E",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
