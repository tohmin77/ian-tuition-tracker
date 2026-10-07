from datetime import date

import pandas as pd

from .models import DATE_FMT


def totals(df: pd.DataFrame) -> dict:
    sessions = len(df)
    hours = round(float(df["Duration (hrs)"].sum()), 2)
    avg = round(hours / sessions, 2) if sessions else 0.0
    return {"sessions": sessions, "hours": hours, "avg_hours": avg}


def by_month_subject(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Month", "Subject", "Sessions", "Hours"])
    month = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m")
    subject = df["Subject"].str.strip().replace("", "(none)")
    out = (
        df.assign(Month=month, Subject=subject)
        .dropna(subset=["Month"])
        .groupby(["Month", "Subject"])["Duration (hrs)"]
        .agg(Sessions="count", Hours="sum")
        .reset_index()
        .sort_values(["Month", "Subject"])
    )
    out["Hours"] = out["Hours"].round(2)
    return out.reset_index(drop=True)


def credit_balance(attendance: pd.DataFrame, credits: pd.DataFrame) -> dict:
    purchased = round(float(credits["Hours"].sum()), 2)
    used = round(float(attendance["Duration (hrs)"].sum()), 2)
    return {"purchased": purchased, "used": used, "remaining": round(purchased - used, 2)}


def entries_on_day(df: pd.DataFrame, day: date) -> pd.DataFrame:
    return df[df["Date"] == day.strftime(DATE_FMT)].sort_values("Start")
