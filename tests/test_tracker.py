from datetime import date, datetime, time

import pytest

from tracker import edits, summary
from tracker.models import Credit, Entry, duration_hours
from tracker.sheets import CREDIT_HEADERS, HEADERS, AttendanceSheet, DuplicateEntryError


class FakeWorksheet:
    def __init__(self, headers=HEADERS):
        self.rows = [headers]

    def row_values(self, n):
        return self.rows[n - 1] if len(self.rows) >= n else []

    def update(self, range_name, values):
        self.rows[: len(values)] = [[str(c) for c in r] for r in values]

    def batch_clear(self, ranges):
        first, last = ranges[0].split(":")
        a, b = int(first[1:]), int(last[1:])
        del self.rows[a - 1 : b]

    def get_all_values(self):
        return self.rows

    def append_row(self, row, **kwargs):
        self.rows.append([str(c) for c in row])


def make_sheet():
    return AttendanceSheet(FakeWorksheet(), FakeWorksheet(CREDIT_HEADERS))


def test_duration():
    assert duration_hours(time(16, 0), time(17, 30)) == 1.5
    assert duration_hours(time(16, 0), time(16, 20)) == 0.33


def test_validate_rejects_end_before_start():
    with pytest.raises(ValueError):
        Entry(date(2026, 1, 1), time(18, 0), time(17, 0)).validate()
    with pytest.raises(ValueError):
        Entry(date(2026, 1, 1), time(18, 0), time(18, 0)).validate()


def test_to_row():
    row = Entry(date(2026, 1, 5), time(16, 0), time(18, 0), " Math ").to_row(
        "2026-01-05 19:00:00"
    )
    assert row == ["2026-01-05", "16:00", "18:00", 2.0, "Math", "2026-01-05 19:00:00"]


def test_add_and_read():
    sheet = make_sheet()
    sheet.add(Entry(date(2026, 1, 5), time(16, 0), time(18, 0), "Math"))
    df = sheet.read()
    assert len(df) == 1
    assert df.loc[0, "Duration (hrs)"] == 2.0


def test_add_rejects_duplicate():
    sheet = make_sheet()
    e = Entry(date(2026, 1, 5), time(16, 0), time(18, 0))
    sheet.add(e)
    with pytest.raises(DuplicateEntryError):
        sheet.add(Entry(date(2026, 1, 5), time(16, 0), time(17, 0)))


def test_add_rejects_invalid():
    with pytest.raises(ValueError):
        make_sheet().add(Entry(date(2026, 1, 5), time(18, 0), time(16, 0)))


def test_summaries():
    sheet = make_sheet()
    sheet.add(Entry(date(2026, 1, 5), time(16, 0), time(18, 0), "Math"))
    sheet.add(Entry(date(2026, 1, 12), time(16, 0), time(17, 0), "Math"))
    sheet.add(Entry(date(2026, 2, 2), time(16, 0), time(17, 30)))
    df = sheet.read()

    assert summary.totals(df) == {"sessions": 3, "hours": 4.5, "avg_hours": 1.5}

    combined = summary.by_month_subject(df)
    assert list(
        zip(combined["Month"], combined["Subject"], combined["Sessions"], combined["Hours"])
    ) == [("2026-01", "Math", 2, 3.0), ("2026-02", "(none)", 1, 1.5)]


def test_empty_summaries():
    df = make_sheet().read()
    assert summary.totals(df)["sessions"] == 0
    assert summary.by_month_subject(df).empty


def test_credits_add_and_balance():
    sheet = make_sheet()
    sheet.add_credit(Credit(date(2026, 1, 1), 10, "package"))
    sheet.add_credit(Credit(date(2026, 2, 1), 5.5))
    sheet.add(Entry(date(2026, 1, 5), time(16, 0), time(18, 0)))
    credits = sheet.read_credits()
    assert list(credits["Hours"]) == [10.0, 5.5]
    assert summary.credit_balance(sheet.read(), credits) == {
        "purchased": 15.5, "used": 2.0, "remaining": 13.5,
    }


def test_credit_rejects_non_positive():
    with pytest.raises(ValueError):
        make_sheet().add_credit(Credit(date(2026, 1, 1), 0))


def test_balance_empty_and_overdrawn():
    sheet = make_sheet()
    assert summary.credit_balance(sheet.read(), sheet.read_credits())["remaining"] == 0
    sheet.add(Entry(date(2026, 1, 5), time(16, 0), time(18, 0)))
    assert summary.credit_balance(sheet.read(), sheet.read_credits())["remaining"] == -2.0


def _two_entry_sheet():
    sheet = make_sheet()
    sheet.add(Entry(date(2026, 1, 5), time(16, 0), time(18, 0), "Math"))
    sheet.add(Entry(date(2026, 1, 5), time(19, 0), time(20, 0)))
    sheet.add(Entry(date(2026, 1, 8), time(16, 0), time(17, 0), "Science"))
    return sheet


def test_entries_on_day():
    df = _two_entry_sheet().read()
    day = summary.entries_on_day(df, date(2026, 1, 5))
    assert list(day["Start"]) == ["16:00", "19:00"]
    assert summary.entries_on_day(df, date(2026, 3, 1)).empty


def test_edit_and_delete_entries_round_trip():
    sheet = _two_entry_sheet()
    df = sheet.read()
    edited = edits.attendance_editor_frame(df)
    edited.loc[0, "End"] = time(18, 30)
    edited.loc[1, "Delete"] = True
    edited.loc[2, "Subject"] = "Science"
    sheet.replace_entries(edits.entries_from_editor(df, edited))
    out = sheet.read()
    assert list(out["End"]) == ["18:30", "17:00"]
    assert list(out["Duration (hrs)"]) == [2.5, 1.0]
    assert list(out["Subject"]) == ["Math", "Science"]
    assert out.loc[0, "Logged at"] == df.loc[0, "Logged at"]
    assert len(sheet.ws.rows) == 3


def test_edit_entries_rejects_bad_input():
    sheet = _two_entry_sheet()
    df = sheet.read()
    edited = edits.attendance_editor_frame(df)
    edited.loc[0, "End"] = time(15, 0)
    with pytest.raises(ValueError):
        edits.entries_from_editor(df, edited)
    edited = edits.attendance_editor_frame(df)
    edited.loc[0, "Start"] = None
    with pytest.raises(ValueError):
        edits.entries_from_editor(df, edited)
    edited = edits.attendance_editor_frame(df)
    edited.loc[1, "Start"] = time(16, 0)
    with pytest.raises(DuplicateEntryError):
        sheet.replace_entries(edits.entries_from_editor(df, edited))


def test_edit_and_delete_credits():
    sheet = make_sheet()
    sheet.add_credit(Credit(date(2026, 1, 1), 10, "a"))
    sheet.add_credit(Credit(date(2026, 2, 1), 5, "b"))
    df = sheet.read_credits()
    edited = edits.credits_editor_frame(df)
    edited.loc[0, "Hours"] = 8.0
    edited.loc[1, "Delete"] = True
    sheet.replace_credits(edits.credits_from_editor(df, edited))
    out = sheet.read_credits()
    assert list(out["Hours"]) == [8.0] and list(out["Note"]) == ["a"]
    edited = edits.credits_editor_frame(out)
    edited.loc[0, "Hours"] = 0
    with pytest.raises(ValueError):
        edits.credits_from_editor(out, edited)
