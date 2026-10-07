# Ian's Tuition Attendance Tracker

Streamlit app that records attendance at Teacher Zhou's Center into a Google Sheet and shows a summary.

## One-time Google setup
1. In Google Cloud Console, create a project and enable the **Google Sheets API** and **Google Drive API**.
2. Create a **service account**, then add a JSON key and download it to `credentials/service_account.json`.
3. In Google Drive, create a blank Google Sheet (e.g. "Ian Tuition Attendance") and share it (Editor) with the service account's email (`client_email` in the JSON).
4. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set `sheet_id` (the long ID in the Sheet's URL between `/d/` and `/edit`).

The app writes to the first tab and creates the header row automatically.

## Run
```
source .venv/bin/activate
streamlit run app.py
```

## Test
```
pytest
```
