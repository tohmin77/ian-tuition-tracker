from datetime import date, datetime, time

import altair as alt
import streamlit as st
import streamlit.components.v1 as components

from tracker import edits, summary
from tracker.models import Credit, Entry, duration_hours
from tracker.sheets import AttendanceSheet, DuplicateEntryError

DEFAULT_SESSION_MINUTES = 120
SUBJECTS = ["Science", "Mathematics"]
SUBJECT_COLORS = {"Science": "#2a9d8f", "Mathematics": "#e76f51", "(none)": "#adb5bd"}

st.set_page_config(page_title="Ian's Tuition Tracker", page_icon="static/icon-512.png")
st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { display: none; }
    .block-container { padding: 0.75rem 0.75rem 1rem; }
    div[data-testid="stVerticalBlock"] { gap: 0.5rem; }
    div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.5rem; }
    div[data-testid="stColumn"] { min-width: 0 !important; }
    div[data-testid="stCaptionContainer"] { margin-bottom: -0.4rem; }
    div[data-baseweb="input"] input,
    div[data-baseweb="select"] *,
    div[data-baseweb="popover"] li,
    div[data-baseweb="popover"] li * {
        font-size: 16px !important;
    }
    .st-key-save_attendance button,
    .st-key-save_att_edits button,
    .st-key-save_credit_edits button {
        background-color: #b7e4c7;
        border-color: #95d5b2;
        color: #1b4332;
    }
    .st-key-confirm_add_credits button,
    .st-key-add_credits button {
        background-color: #bde0fe;
        border-color: #a2d2ff;
        color: #1d3557;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_sheet() -> AttendanceSheet:
    credentials = (
        dict(st.secrets["gcp_service_account"])
        if "gcp_service_account" in st.secrets
        else st.secrets["service_account_file"]
    )
    sheet = AttendanceSheet.connect(credentials, st.secrets["sheet_id"])
    sheet.ensure_header()
    return sheet


def set_time(key: str, t: time) -> None:
    st.session_state[f"{key}_h"] = t.hour % 12 or 12
    st.session_state[f"{key}_m"] = t.minute
    st.session_state[f"{key}_p"] = "PM" if t.hour >= 12 else "AM"


def time_picker(label: str, key: str, on_change=None) -> time:
    st.caption(label)
    h_col, m_col, p_col = st.columns(3)
    hour = h_col.selectbox(
        "Hour", range(1, 13), key=f"{key}_h",
        label_visibility="collapsed", on_change=on_change,
    )
    minute = m_col.selectbox(
        "Minute", range(0, 60, 5), format_func=lambda m: f"{m:02d}",
        key=f"{key}_m", label_visibility="collapsed", on_change=on_change,
    )
    period = p_col.selectbox(
        "AM/PM", ["AM", "PM"], key=f"{key}_p",
        label_visibility="collapsed", on_change=on_change,
    )
    return time(hour % 12 + (12 if period == "PM" else 0), minute)


def toggle_subject(name: str) -> None:
    st.session_state["subject"] = None if st.session_state.get("subject") == name else name


def default_end_from_start() -> None:
    h = st.session_state["start_h"] % 12 + (12 if st.session_state["start_p"] == "PM" else 0)
    minutes = min(h * 60 + st.session_state["start_m"] + DEFAULT_SESSION_MINUTES, 23 * 60 + 55)
    set_time("end", time(minutes // 60, minutes % 60))


try:
    sheet = get_sheet()
except (FileNotFoundError, KeyError, st.errors.StreamlitSecretNotFoundError):
    st.error(
        "Google Sheets is not configured. Copy `.streamlit/secrets.toml.example` to "
        "`.streamlit/secrets.toml`, fill it in, and place the service account key "
        "file as described in the README."
    )
    st.stop()
except Exception as exc:
    st.error(f"Could not connect to Google Sheets: {exc}")
    st.stop()

if "start_h" not in st.session_state:
    set_time("start", time(14, 30))
    default_end_from_start()
st.session_state.setdefault("edit_ver", 0)
if flash := st.session_state.pop("flash", None):
    st.toast(flash)


components.html(
    """
    <script>
    const head = window.parent.document.head;
    head.querySelectorAll('link[rel="apple-touch-icon"]').forEach(l => l.remove());
    const link = window.parent.document.createElement('link');
    link.rel = 'apple-touch-icon';
    link.href = '/app/static/apple-touch-icon.png';
    head.appendChild(link);
    </script>
    """,
    height=0,
)


def fmt_time(text: str) -> str:
    return datetime.strptime(text, "%H:%M").strftime("%-I:%M %p")


def run_edit_save(save, items_fn, message: str) -> None:
    try:
        save(items_fn())
    except (ValueError, DuplicateEntryError) as exc:
        st.warning(str(exc))
    except Exception as exc:
        st.error(f"Could not save to Google Sheets: {exc}")
    else:
        st.session_state["flash"] = message
        st.session_state["edit_ver"] += 1
        st.rerun()


def attendance_editor(df) -> None:
    frame = edits.attendance_editor_frame(df)
    subjects = SUBJECTS + sorted(set(frame["Subject"].dropna()) - set(SUBJECTS))
    edited = st.data_editor(
        frame,
        key=f"att_editor_{st.session_state['edit_ver']}",
        hide_index=True,
        width="stretch",
        column_config={
            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
            "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", required=True),
            "Start": st.column_config.TimeColumn("Start", format="h:mm a", required=True),
            "End": st.column_config.TimeColumn("End", format="h:mm a", required=True),
            "Subject": st.column_config.SelectboxColumn("Subject", options=subjects),
        },
    )
    if st.button("Save attendance changes", key="save_att_edits", width="stretch"):
        run_edit_save(
            sheet.replace_entries,
            lambda: edits.entries_from_editor(df, edited),
            "Attendance updated.",
        )


def credits_editor(credits_df) -> None:
    frame = edits.credits_editor_frame(credits_df)
    edited = st.data_editor(
        frame,
        key=f"credit_editor_{st.session_state['edit_ver']}",
        hide_index=True,
        width="stretch",
        column_config={
            "Delete": st.column_config.CheckboxColumn("🗑", width="small"),
            "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", required=True),
            "Hours": st.column_config.NumberColumn("Hours", min_value=0.5, step=0.5, required=True),
            "Note": st.column_config.TextColumn("Note"),
        },
    )
    if st.button("Save credit changes", key="save_credit_edits", width="stretch"):
        run_edit_save(
            sheet.replace_credits,
            lambda: edits.credits_from_editor(credits_df, edited),
            "Credits updated.",
        )


@st.dialog("Add time credits")
def add_credits_dialog() -> None:
    credit_day = st.date_input("Date purchased", value=date.today())
    hours = st.number_input("Hours purchased", min_value=0.5, value=10.0, step=0.5)
    note = st.text_input("Note (optional)", placeholder="e.g. 10-hour package")
    if st.button("Add credits", key="confirm_add_credits"):
        try:
            sheet.add_credit(Credit(credit_day, hours, note))
        except ValueError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(f"Could not save to Google Sheets: {exc}")
        else:
            st.rerun()


log_tab, summary_tab = st.tabs(["➕ Log", "📊 Summary"])

with log_tab:
    remaining_slot = st.empty()
    day = st.date_input("Date", value=date.today())
    same_day_slot = st.empty()
    start = time_picker("Start time", "start", on_change=default_end_from_start)
    end = time_picker("End time", "end")
    st.caption("Subject")
    subject_cols = st.columns(len(SUBJECTS))
    for col, name in zip(subject_cols, SUBJECTS):
        col.button(
            name,
            key=f"subject_{name}",
            type="primary" if st.session_state.get("subject") == name else "secondary",
            on_click=toggle_subject,
            args=(name,),
            width="stretch",
        )
    subject = st.session_state.get("subject")
    if end > start:
        st.write(f"Duration: **{duration_hours(start, end)} hrs**")
    else:
        st.write("Duration: end time must be after start time")

    if st.button("Save attendance", key="save_attendance", width="stretch"):
        try:
            sheet.add(Entry(day, start, end, subject or ""))
            st.success("Saved to Google Sheet.")
        except (ValueError, DuplicateEntryError) as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(f"Could not save to Google Sheets: {exc}")

try:
    df = sheet.read()
    credits_df = sheet.read_credits()
except Exception as exc:
    st.error(f"Could not read from Google Sheets: {exc}")
    st.stop()

same_day = summary.entries_on_day(df, day)
if len(same_day) >= 2:
    details = "; ".join(
        f"{fmt_time(r.Start)}–{fmt_time(r.End)}" + (f" {r.Subject}" if r.Subject else "")
        for r in same_day.itertuples()
    )
    same_day_slot.warning(
        f"⚠️ {len(same_day)} entries recorded on {day:%d %b %Y}: {details}"
    )

balance = summary.credit_balance(df, credits_df)
remaining_slot.markdown(
    f"**📚 Teacher Zhou's Center** · **{balance['remaining']} hrs** left"
)

with summary_tab:
    c1, c2, c3 = st.columns(3)
    c1.metric("Purchased", balance["purchased"])
    c2.metric("Used", balance["used"])
    c3.metric("Remaining", balance["remaining"])
    if balance["remaining"] < 0:
        st.warning(f"Attendance exceeds purchased credits by {-balance['remaining']} hrs.")
    if st.button("➕ Add time credits", key="add_credits", width="stretch"):
        add_credits_dialog()
    if not credits_df.empty:
        with st.expander("Credit purchases (edit)"):
            st.caption("Tick 🗑 to delete a row, then save.")
            credits_editor(credits_df)

    if df.empty:
        st.info("No attendance recorded yet.")
    else:
        t = summary.totals(df)
        m1, m2, m3 = st.columns(3)
        m1.metric("Sessions", t["sessions"])
        m2.metric("Hours", t["hours"])
        m3.metric("Avg / session", t["avg_hours"])

        st.subheader("Attendance log")
        st.caption("Edit a cell or tick 🗑 to delete a row, then save.")
        attendance_editor(df)

        monthly = summary.by_month_subject(df)
        st.subheader("Hours by month and subject")
        chart = (
            alt.Chart(monthly)
            .mark_bar()
            .encode(
                x=alt.X("Month:N", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Hours:Q", title="Hours"),
                color=alt.Color(
                    "Subject:N",
                    scale=alt.Scale(
                        domain=list(SUBJECT_COLORS), range=list(SUBJECT_COLORS.values())
                    ),
                    legend=alt.Legend(orient="bottom", title=None),
                ),
                tooltip=["Month", "Subject", "Sessions", "Hours"],
            )
            .properties(height=260)
        )
        st.altair_chart(chart, width="stretch")
        st.dataframe(monthly, hide_index=True, width="stretch")
