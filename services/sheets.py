import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import MONTH_NAMES, SPREADSHEET_ID

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_TRANSACTIONS_SHEET = "транзакции 2026"
_SUMMARY_SHEET = "суммы по месяцам"


def _get_service():
    raw = os.environ["GOOGLE_CREDENTIALS_JSON"]
    # support both raw JSON and base64-encoded JSON
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        import base64
        raw = raw.strip().replace(" ", "").replace("\n", "").replace("\r", "")
        raw += "=" * (-len(raw) % 4)
        info = json.loads(base64.b64decode(raw).decode())
    creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _col_letter(n: int) -> str:
    """1-based column index → letter(s): 1→A, 26→Z, 27→AA"""
    result = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


def _month_col_header(month_num: int) -> str:
    return f"{MONTH_NAMES[month_num]} 2026, RSD"


def _ensure_month_column(service, month_num: int) -> None:
    """Add a month column to the summary sheet if it doesn't exist yet."""
    header = _month_col_header(month_num)

    # Read current headers
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_SUMMARY_SHEET}'!1:1",
    ).execute()
    headers = result.get("values", [[]])[0]

    if header in headers:
        return  # already exists

    # Find "Всего RSD" column (always last) — insert before it
    if "Всего RSD" in headers:
        insert_col = headers.index("Всего RSD") + 1  # 1-based
    else:
        insert_col = len(headers) + 1

    # Read all data to know how many category rows exist
    data = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_SUMMARY_SHEET}'!A:A",
    ).execute().get("values", [])
    total_rows = len(data)  # includes header + categories + ИТОГО

    # Get sheet id for batchUpdate
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheet_id = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == _SUMMARY_SHEET
    )

    # Insert blank column at insert_col position
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": insert_col - 1,
                    "endIndex": insert_col,
                },
                "inheritFromBefore": False,
            }
        }]},
    ).execute()

    col = _col_letter(insert_col)
    mm = str(month_num).zfill(2)

    # Write header
    values = [[header]]
    # SUMPRODUCT formula for each category row (rows 2 to total_rows-1)
    # Use INDIRECT() so references don't drift when rows are inserted in the transactions sheet
    for row in range(2, total_rows):  # skip header and ИТОГО
        formula = (
            f"=SUMPRODUCT("
            f"(RIGHT(INDIRECT(\"'{_TRANSACTIONS_SHEET}'!A2:A10000\"),2)=\"{mm}\")*"
            f"(INDIRECT(\"'{_TRANSACTIONS_SHEET}'!D2:D10000\")=$A{row})*"
            f"INDIRECT(\"'{_TRANSACTIONS_SHEET}'!C2:C10000\"))"
        )
        values.append([formula])
    # ИТОГО row — SUM of the column
    values.append([f"=SUM({col}2:{col}{total_rows - 1})"])

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_SUMMARY_SHEET}'!{col}1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()

    # Update "Всего RSD" column formulas to include the new month
    # It's now shifted one column to the right
    total_col = _col_letter(insert_col + 1)
    total_values = []
    for row in range(2, total_rows + 1):
        # sum all columns between B and the column before "Всего RSD"
        total_values.append([f"=SUM(B{row}:{_col_letter(insert_col)}{row})"])
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_SUMMARY_SHEET}'!{total_col}2",
        valueInputOption="USER_ENTERED",
        body={"values": total_values},
    ).execute()


def repair_summary_formulas() -> None:
    """Fix drifted SUMPRODUCT formulas in the summary sheet caused by row insertions.
    Rewrites all month column formulas to use INDIRECT() so they stay static."""
    service = _get_service()

    # Read headers to find all month columns
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_SUMMARY_SHEET}'!1:1",
    ).execute()
    headers = result.get("values", [[]])[0]

    # Read column A to find category rows and ИТОГО
    col_a = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_SUMMARY_SHEET}'!A:A",
    ).execute().get("values", [])
    total_rows = len(col_a)

    for col_idx, header in enumerate(headers, start=1):
        # Match month headers like "май 2026, RSD"
        import re as _re
        m = _re.match(r"(\S+) 2026, RSD", header)
        if not m:
            continue
        month_name = m.group(1)
        month_num = next((k for k, v in MONTH_NAMES.items() if v == month_name), None)
        if month_num is None:
            continue
        mm = str(month_num).zfill(2)
        col = _col_letter(col_idx)

        values = []
        for row in range(2, total_rows):  # skip header, skip ИТОГО
            formula = (
                f"=SUMPRODUCT("
                f"(RIGHT(INDIRECT(\"'{_TRANSACTIONS_SHEET}'!A2:A10000\"),2)=\"{mm}\")*"
                f"(INDIRECT(\"'{_TRANSACTIONS_SHEET}'!D2:D10000\")=$A{row})*"
                f"INDIRECT(\"'{_TRANSACTIONS_SHEET}'!C2:C10000\"))"
            )
            values.append([formula])
        # ИТОГО row
        values.append([f"=SUM({col}2:{col}{total_rows - 1})"])

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{_SUMMARY_SHEET}'!{col}2",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()


def get_month_total(month_num: int) -> int | None:
    """Return total RSD for the given month from summary sheet, or None if not found."""
    service = _get_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_SUMMARY_SHEET}'!1:1",
    ).execute()
    headers = result.get("values", [[]])[0]
    header = _month_col_header(month_num)
    if header not in headers:
        return None
    col_idx = headers.index(header) + 1  # 1-based
    col = _col_letter(col_idx)

    # Find ИТОГО row
    col_a = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_SUMMARY_SHEET}'!A:A",
    ).execute().get("values", [])
    itogo_row = next((i + 1 for i, r in enumerate(col_a) if r and "ИТОГО" in r[0].upper()), None)
    if not itogo_row:
        return None

    val = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_SUMMARY_SHEET}'!{col}{itogo_row}",
    ).execute().get("values", [[None]])[0][0]
    try:
        return int(float(str(val).replace(",", ".")))
    except (ValueError, TypeError):
        return None


def get_merchant_categories() -> dict[str, str]:
    """Return {merchant: last_used_category} from transaction history."""
    service = _get_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_TRANSACTIONS_SHEET}'!B:D",
    ).execute()
    rows = result.get("values", [])
    mapping = {}
    for row in rows[1:]:  # skip header
        if len(row) >= 3:
            merchant, _, category = row[0], row[1], row[2]
            if merchant and category:
                mapping[merchant.strip().lower()] = category
    return mapping


def append_transaction(date: str, merchant: str, amount: int, category: str, comment: str = "") -> None:
    service = _get_service()

    # Get sheet id to insert row after header (row 2)
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheet_id = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == _TRANSACTIONS_SHEET
    )

    # Insert blank row at position 2 (after header)
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"insertDimension": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 1, "endIndex": 2},
            "inheritFromBefore": False,
        }}]},
    ).execute()

    # Write data — date as plain text (apostrophe prefix prevents Google Sheets date parsing)
    row = [f"'{date}", merchant, amount, category, comment]
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{_TRANSACTIONS_SHEET}'!A2:E2",
        valueInputOption="USER_ENTERED",
        body={"values": [row]},
    ).execute()

    # Ensure summary sheet has a column for this month
    month_num = int(date.split(".")[1])
    _ensure_month_column(service, month_num)
