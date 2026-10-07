from dataclasses import dataclass
from datetime import date, datetime, time

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M"
LOGGED_FMT = "%Y-%m-%d %H:%M:%S"


def now_stamp() -> str:
    return datetime.now().strftime(LOGGED_FMT)


def duration_hours(start: time, end: time) -> float:
    delta = (
        datetime.combine(date.min, end) - datetime.combine(date.min, start)
    ).total_seconds()
    return round(delta / 3600, 2)


@dataclass(frozen=True)
class Entry:
    day: date
    start: time
    end: time
    subject: str = ""

    @property
    def hours(self) -> float:
        return duration_hours(self.start, self.end)

    def validate(self) -> None:
        if self.end <= self.start:
            raise ValueError("End time must be after start time.")

    def key(self) -> tuple[str, str]:
        return self.day.strftime(DATE_FMT), self.start.strftime(TIME_FMT)

    def to_row(self, logged_at: str) -> list:
        return [
            self.day.strftime(DATE_FMT),
            self.start.strftime(TIME_FMT),
            self.end.strftime(TIME_FMT),
            self.hours,
            self.subject.strip(),
            logged_at,
        ]


@dataclass(frozen=True)
class Credit:
    day: date
    hours: float
    note: str = ""

    def validate(self) -> None:
        if self.hours <= 0:
            raise ValueError("Credit hours must be greater than zero.")

    def to_row(self, logged_at: str) -> list:
        return [
            self.day.strftime(DATE_FMT),
            round(self.hours, 2),
            self.note.strip(),
            logged_at,
        ]
