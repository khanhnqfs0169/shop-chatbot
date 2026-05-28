import os, json, openpyxl
from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

class SheetLogger:
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    SHEET_HEADERS = ["Thoi gian", "Sender ID", "Ten khach", "Cau hoi", "Bot tra loi", "Chuyen nhan vien?"]

    def __init__(self):
        self.spreadsheet_id = os.getenv("GOOGLE_SHEET_ID", "")
        self.credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        self.local_log_file = "conversations_log.xlsx"
        self._sheet = None
        self._local_wb = None
        self._local_ws = None
        if GSPREAD_AVAILABLE and self.spreadsheet_id:
            self._init_google_sheet()
        else:
            self._init_local_excel()

    def _init_google_sheet(self):
        try:
            creds = Credentials.from_service_account_file(self.credentials_file, scopes=self.SCOPES)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(self.spreadsheet_id)
            try:
                self._sheet = spreadsheet.worksheet("Hoi thoai")
            except gspread.exceptions.WorksheetNotFound:
                self._sheet = spreadsheet.add_worksheet("Hoi thoai", rows=5000, cols=10)
                self._sheet.append_row(self.SHEET_HEADERS)
            print("Ket noi Google Sheet thanh cong.")
        except Exception as e:
            print(f"Khong ket noi duoc Google Sheet: {e} -> ghi local.")
            self._sheet = None
            self._init_local_excel()

    def _init_local_excel(self):
        try:
            self._local_wb = openpyxl.load_workbook(self.local_log_file)
            self._local_ws = self._local_wb["Hoi thoai"]
        except FileNotFoundError:
            self._local_wb = openpyxl.Workbook()
            self._local_ws = self._local_wb.active
            self._local_ws.title = "Hoi thoai"
            self._local_ws.append(self.SHEET_HEADERS)
            self._local_wb.save(self.local_log_file)

    def log(self, sender_id, question, answer, sender_name="", escalated=False):
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        row = [timestamp, sender_id, sender_name, question, answer, "Co" if escalated else "Khong"]
        if self._sheet:
            try:
                self._sheet.append_row(row)
                return
            except Exception as e:
                print(f"Loi ghi Google Sheet: {e}")
        if self._local_ws:
            self._local_ws.append(row)
            self._local_wb.save(self.local_log_file)

    def get_today_logs(self):
        today = datetime.now().strftime("%d/%m/%Y")
        rows = []
        if self._sheet:
            try:
                all_rows = self._sheet.get_all_records()
                rows = [r for r in all_rows if r.get("Thoi gian", "").startswith(today)]
            except Exception:
                pass
        elif self._local_ws:
            headers = [cell.value for cell in self._local_ws[1]]
            for row in self._local_ws.iter_rows(min_row=2, values_only=True):
                if row[0] and str(row[0]).startswith(today):
                    rows.append(dict(zip(headers, row)))
        return rows

logger = SheetLogger()
