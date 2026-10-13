import io
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from PIL import Image

st.set_page_config(page_title="Vehicle Data Capture", page_icon="🚚", layout="centered")

MODEL = st.secrets.get("GEMINI_MODEL", "gemini-2.5-flash")  # free-tier model; change in secrets if needed
HEADERS = [
    "Submitted At", "Photo Date/Time", "Location", "VIN", "Hours",
    "Odometer km", "Plate", "Status", "Notes", "Submitted By",
]

PROMPT = """You are reading photos of a commercial truck (BharatBenz). Photos are labelled.
Return ONLY JSON with these keys:
{
 "vin": "17-character VIN from the VIN plate photo. Engraved font uses a slashed zero: that is the digit 0. VIN never contains letters I, O, Q.",
 "hours": "number from the HRS screen photo (engine hours, digits only, no 'h')",
 "odometer_km": "TOTAL odometer in km from the cluster photo. This is the value inside the green box, NOT the 'trip' value. Number only, may include one decimal.",
 "plate": "registration / temporary plate text from the front photo, or ''",
 "photo_datetime": "date and time from the green overlay text on any photo, or ''",
 "location": "place name from the green overlay text, or ''",
 "notes": "mention anything blurry, glare, or uncertain; else ''"
}
If a value is unreadable use "" and explain in notes. Never guess digits."""


# ---------- helpers ----------
def check_password():
    pw = st.secrets.get("APP_PASSWORD")
    if not pw:
        return True
    if st.session_state.get("auth"):
        return True
    entered = st.text_input("Password", type="password")
    if entered:
        if entered == pw:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    return False


def prep(file):
    img = Image.open(file).convert("RGB")
    img.thumbnail((1600, 1600))
    return img


@st.cache_resource
def get_ws():
    gc = gspread.service_account_from_dict(json.loads(st.secrets["GCP_JSON"]))
    ws = gc.open_by_key(st.secrets["SHEET_ID"]).sheet1
    if not ws.get_all_values():
        ws.append_row(HEADERS)
    return ws


def load_df():
    values = get_ws().get_all_values()
    if len(values) < 2:
        return pd.DataFrame(columns=HEADERS)
    return pd.DataFrame(values[1:], columns=values[0])


def extract(images):
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    contents = [PROMPT]
    for label, img in images:
        contents.append(f"Photo label: {label}")
        contents.append(img)
    resp = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    return json.loads(resp.text)


def to_float(x):
    try:
        return float(re.sub(r"[^0-9.]", "", str(x)))
    except ValueError:
        return None


def validate(vin, hours, odo):
    problems = []
    vin = vin.strip().upper()
    if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", vin):
        problems.append("VIN must be 17 chars, no I/O/Q")
    if to_float(hours) is None:
        problems.append("Hours missing")
    o = to_float(odo)
    if o is None:
        problems.append("Odometer missing")
    else:
        try:
            df = load_df()
            prev = df[df["VIN"] == vin]["Odometer km"].map(to_float).dropna()
            if len(prev) and o < prev.max():
                problems.append(f"Odometer lower than previous entry ({prev.max()})")
        except Exception:
            pass
    return problems


# ---------- UI ----------
st.title("🚚 Vehicle Data Capture")
if not check_password():
    st.stop()

tab_add, tab_db = st.tabs(["Add new set", "Database"])

with tab_add:
    st.caption("Upload the 4 photos, tap **Read photos**, check the values, then **Save**.")
    nonce = st.session_state.setdefault("nonce", 0)
    f_vin = st.file_uploader("1. VIN plate photo", type=["jpg", "jpeg", "png"], key=f"vin{nonce}")
    f_odo = st.file_uploader("2. Odometer (km) photo", type=["jpg", "jpeg", "png"], key=f"odo{nonce}")
    f_hrs = st.file_uploader("3. Hours (HRS) photo", type=["jpg", "jpeg", "png"], key=f"hrs{nonce}")
    f_front = st.file_uploader("4. Front of truck photo", type=["jpg", "jpeg", "png"], key=f"front{nonce}")
    who = st.text_input("Your name (optional)", key=f"who{nonce}")

    if st.button("Read photos", type="primary", disabled=not (f_vin and f_odo and f_hrs and f_front)):
        with st.spinner("Reading photos..."):
            try:
                st.session_state["ext"] = extract([
                    ("VIN plate", prep(f_vin)),
                    ("Odometer cluster", prep(f_odo)),
                    ("HRS screen", prep(f_hrs)),
                    ("Front of truck", prep(f_front)),
                ])
            except Exception as e:
                st.error(f"Could not read photos: {e}")

    ext = st.session_state.get("ext")
    if ext:
        st.subheader("Check / correct values")
        vin = st.text_input("VIN", str(ext.get("vin", "")).upper(), key=f"v{nonce}")
        c1, c2 = st.columns(2)
        hours = c1.text_input("Hours", str(ext.get("hours", "")), key=f"h{nonce}")
        odo = c2.text_input("Odometer km", str(ext.get("odometer_km", "")), key=f"o{nonce}")
        plate = st.text_input("Plate", str(ext.get("plate", "")), key=f"p{nonce}")
        ptime = st.text_input("Photo date/time", str(ext.get("photo_datetime", "")), key=f"t{nonce}")
        loc = st.text_input("Location", str(ext.get("location", "")), key=f"l{nonce}")
        notes = ext.get("notes", "")
        if notes:
            st.info(f"AI note: {notes}")

        problems = validate(vin, hours, odo)
        for p in problems:
            st.warning(p)

        if st.button("Save to database"):
            status = "Needs review" if problems else "OK"
            now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
            get_ws().append_row(
                [now, ptime, loc, vin.strip().upper(), hours, odo, plate, status,
                 "; ".join(problems) or notes, who],
                value_input_option="USER_ENTERED",
            )
            st.success(f"Saved ({status}). You can add the next set.")
            st.session_state["nonce"] += 1
            st.session_state.pop("ext", None)
            st.rerun()

with tab_db:
    if st.button("Refresh"):
        st.rerun()
    df = load_df()
    st.dataframe(df, use_container_width=True)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    st.download_button(
        "Download Excel", buf.getvalue(), "vehicle_database.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
