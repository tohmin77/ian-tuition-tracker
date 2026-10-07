from datetime import date, datetime, time

import pandas as pd

from .models import DATE_FMT, TIME_FMT, Credit, Entry


def _parse(text: str, fmt: str):
    try:
        return datetime.strptime(text.strip(), fmt)
    except ValueError:
        return None


def _date(text: str) -> date | None:
    parsed = _parse(text, DATE_FMT)
    return parsed.date() if parsed else None


def _time(text: str) -> time | None:
    parsed = _parse(text, TIME_FMT)
    return parsed.time() if parsed else None


def attendance_editor_frame(df: pd.DataFrame) -> pd.DataFrame:
    ordered = df.sort_values(["Date", "Start"], ascending=False)
    return pd.DataFrame(
        {
            "Delete": False,
            "Date": [_date(v) for v in ordered["Date"]],
            "Start": [_time(v) for v in ordered["Start"]],
            "End": [_time(v) for v in ordered["End"]],
            "Subject": [v.strip() or None for v in ordered["Subject"]],
        },
        index=ordered.index,
    )


def credits_editor_frame(df: pd.DataFrame) -> pd.DataFrame:
    ordered = df.sort_values("Date", ascending=False, kind="stable")
    return pd.DataFrame(
        {
            "Delete": False,
            "Date": [_date(v) for v in ordered["Date"]],
            "Hours": ordered["Hours"].astype(float),
            "Note": [v.strip() for v in ordered["Note"]],
        },
        index=ordered.index,
    )


def _missing(value) -> bool:
    return value is None or pd.isna(value)


def _label(original: pd.DataFrame, idx) -> str:
    return f"Row dated {original.loc[idx, 'Date'] or '(blank)'}"


def entries_from_editor(
    original: pd.DataFrame, edited: pd.DataFrame
) -> list[tuple[Entry, str]]:
    items = []
    for idx in original.index:
        row = edited.loc[idx]
        if row["Delete"]:
            continue
        if _missing(row["Date"]) or _missing(row["Start"]) or _missing(row["End"]):
            raise ValueError(f"{_label(original, idx)}: date, start and end are required.")
        entry = Entry(row["Date"], row["Start"], row["End"], "" if _missing(row["Subject"]) else row["Subject"])
        try:
            entry.validate()
        except ValueError as exc:
            raise ValueError(f"{_label(original, idx)}: {exc}") from exc
        items.append((entry, original.loc[idx, "Logged at"]))
    return items


def credits_from_editor(
    original: pd.DataFrame, edited: pd.DataFrame
) -> list[tuple[Credit, str]]:
    items = []
    for idx in original.index:
        row = edited.loc[idx]
        if row["Delete"]:
            continue
        if _missing(row["Date"]) or _missing(row["Hours"]):
            raise ValueError(f"{_label(original, idx)}: date and hours are required.")
        credit = Credit(row["Date"], float(row["Hours"]), "" if _missing(row["Note"]) else row["Note"])
        try:
            credit.validate()
        except ValueError as exc:
            raise ValueError(f"{_label(original, idx)}: {exc}") from exc
        items.append((credit, original.loc[idx, "Logged at"]))
    return items
