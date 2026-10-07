import gspread
import pandas as pd

from .models import Credit, Entry, now_stamp

HEADERS = ["Date", "Start", "End", "Duration (hrs)", "Subject", "Logged at"]
CREDIT_HEADERS = ["Date", "Hours", "Note", "Logged at"]
CREDITS_TAB = "Credits"


class DuplicateEntryError(Exception):
    pass


class AttendanceSheet:
    def __init__(self, worksheet, credits_worksheet):
        self.ws = worksheet
        self.credits_ws = credits_worksheet

    @classmethod
    def connect(cls, credentials: str | dict, sheet_id: str) -> "AttendanceSheet":
        if isinstance(credentials, dict):
            client = gspread.service_account_from_dict(credentials)
        else:
            client = gspread.service_account(filename=credentials)
        book = client.open_by_key(sheet_id)
        try:
            credits_ws = book.worksheet(CREDITS_TAB)
        except gspread.WorksheetNotFound:
            credits_ws = book.add_worksheet(CREDITS_TAB, rows=200, cols=len(CREDIT_HEADERS))
        return cls(book.sheet1, credits_ws)

    def ensure_header(self) -> None:
        if self.ws.row_values(1) != HEADERS:
            self.ws.update(range_name="A1:F1", values=[HEADERS])
        if self.credits_ws.row_values(1) != CREDIT_HEADERS:
            self.credits_ws.update(range_name="A1:D1", values=[CREDIT_HEADERS])

    def read(self) -> pd.DataFrame:
        rows = self.ws.get_all_values()[1:]
        df = pd.DataFrame([r[:6] + [""] * (6 - len(r)) for r in rows], columns=HEADERS)
        df = df[df["Date"].str.strip() != ""]
        df["Duration (hrs)"] = pd.to_numeric(df["Duration (hrs)"], errors="coerce").fillna(0.0)
        return df.reset_index(drop=True)

    def add(self, entry: Entry) -> None:
        entry.validate()
        existing = self.read()
        if ((existing["Date"] == entry.key()[0]) & (existing["Start"] == entry.key()[1])).any():
            raise DuplicateEntryError("An entry for this date and start time already exists.")
        self.ws.append_row(
            entry.to_row(now_stamp()),
            value_input_option="RAW",
            table_range="A1",
        )

    def read_credits(self) -> pd.DataFrame:
        rows = self.credits_ws.get_all_values()[1:]
        n = len(CREDIT_HEADERS)
        df = pd.DataFrame([r[:n] + [""] * (n - len(r)) for r in rows], columns=CREDIT_HEADERS)
        df = df[df["Date"].str.strip() != ""]
        df["Hours"] = pd.to_numeric(df["Hours"], errors="coerce").fillna(0.0)
        return df.reset_index(drop=True)

    def add_credit(self, credit: Credit) -> None:
        credit.validate()
        self.credits_ws.append_row(
            credit.to_row(now_stamp()),
            value_input_option="RAW",
            table_range="A1",
        )

    def replace_entries(self, items: list[tuple[Entry, str]]) -> None:
        seen = set()
        for entry, _ in items:
            entry.validate()
            if entry.key() in seen:
                raise DuplicateEntryError(
                    f"Two entries share the same date and start time: {entry.key()[0]} {entry.key()[1]}."
                )
            seen.add(entry.key())
        _replace_rows(self.ws, HEADERS, [e.to_row(ts) for e, ts in items])

    def replace_credits(self, items: list[tuple[Credit, str]]) -> None:
        for credit, _ in items:
            credit.validate()
        _replace_rows(self.credits_ws, CREDIT_HEADERS, [c.to_row(ts) for c, ts in items])


def _replace_rows(ws, headers: list[str], rows: list[list]) -> None:
    old_count = len(ws.get_all_values())
    ws.update(range_name="A1", values=[headers] + rows)
    if old_count > len(rows) + 1:
        ws.batch_clear([f"A{len(rows) + 2}:Z{old_count}"])
