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

## Deploy to Streamlit Community Cloud (use from a phone)
1. Push this repo to GitHub (never commit the key file; `credentials/` is git-ignored).
2. At https://share.streamlit.io create an app from the repo with main file `app.py`.
3. In the app's **Settings → Secrets**, paste:
   ```
   sheet_id = "<your sheet id>"

   [gcp_service_account]
   type = "service_account"
   ... (the fields from your JSON key)
   ```
4. In **Settings → Sharing**, restrict viewing to specific people so only you can open it.
