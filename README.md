# Vehicle Data Capture (free pilot)

Upload 4 photos (VIN plate, odometer, HRS screen, front) -> AI reads VIN, Hours, Odometer, Plate -> you confirm -> saved to Google Sheet -> download as Excel anytime.

Cost: Rs 0. Stack: Streamlit Community Cloud + Gemini API free tier + Google Sheets, all code on GitHub.

## Setup (about 30 minutes, one time)

### 1. Gemini free API key
- Go to https://aistudio.google.com/apikey and sign in with Google.
- Click **Create API key**. Copy it.

### 2. Google Sheet (the database)
- Create a new blank Google Sheet. Name it "Vehicle Database".
- Copy the Sheet ID from the URL: `docs.google.com/spreadsheets/d/<SHEET_ID>/edit`

### 3. Service account (lets the app write to the Sheet)
- Go to https://console.cloud.google.com, create a project (free).
- Enable **Google Sheets API** (APIs & Services > Library).
- APIs & Services > Credentials > Create credentials > **Service account**. Finish.
- Open the service account > Keys > Add key > Create new key > **JSON**. A file downloads.
- In that file find `client_email`. Open your Google Sheet > Share > paste that email > **Editor**.

### 4. GitHub
- Create a GitHub account and a new repository (public or private).
- Upload `app.py`, `requirements.txt`, `README.md`. Do NOT upload keys.

### 5. Deploy free
- Go to https://share.streamlit.io, sign in with GitHub.
- New app > pick your repo > main file `app.py` > **Advanced settings > Secrets**, paste:

```toml
GEMINI_API_KEY = "paste-your-gemini-key"
SHEET_ID = "paste-your-sheet-id"
APP_PASSWORD = "choose-a-team-password"   # optional, remove line for no password

[gcp_service_account]
# Paste every field from the downloaded JSON file here, in TOML format:
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

- Click Deploy. You get a link like `https://your-app.streamlit.app`. Share it with your team; works on phones.

## Using it
1. Open link, upload the 4 photos in the labelled slots.
2. Tap **Read photos**. Check VIN / Hours / Odometer (edit if wrong).
3. Tap **Save to database**. Next set: just repeat.
4. **Database** tab shows all rows and has **Download Excel**.

## Built-in checks
- VIN must be 17 characters, no I/O/Q.
- Odometer cannot be lower than the previous entry for the same VIN.
- Anything failing a check is saved as "Needs review".

## Free-tier limits to know
- The Streamlit app sleeps after inactivity; first click may take ~30 seconds to wake it.
- Gemini free tier has daily request limits and Google may use free-tier inputs to improve its products. Fine for a pilot; do not use for confidential data. Limits and model names change, so if you get a model error set `GEMINI_MODEL` in secrets to a current free Flash model.
- Photos are not stored (only the extracted data). Keep the originals in WhatsApp/Drive.

## Excel auto-refresh (optional)
Open the Google Sheet in Excel (Desktop) via Data > Get Data > From Web using the Sheet's CSV export link, or simply use the Download Excel button.

## Fully offline alternative
If you cannot use any cloud AI, swap the `extract()` function for EasyOCR or PaddleOCR (open source on GitHub). Expect lower accuracy on dashboard LCD digits and the engraved VIN.
