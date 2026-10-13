import json
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st

from core import DEFAULTS, build_excel, crop_percent, load_image, to_b64

st.set_page_config(page_title="Vehicle Photo Capture", page_icon="🚚", layout="centered")

TEXT_HEADS = ["ID", "Submitted At", "Vehicle Ref", "VIN (typed)", "Hours (typed)", "Odometer km (typed)"]
IMG_HEADS = ["ID", "VIN", "HRS", "ODO", "FRONT"]
LABELS = {"VIN": "VIN plate", "ODO": "Odometer (km)", "HRS": "Hours (HRS)"}


def check_password():
    pw = st.secrets.get("APP_PASSWORD")
    if not pw or st.session_state.get("auth"):
        return True
    entered = st.text_input("Password", type="password")
    if entered == pw:
        st.session_state["auth"] = True
        st.rerun()
    elif entered:
        st.error("Wrong password")
    return False


@st.cache_resource
def get_sheets():
    gc = gspread.service_account_from_dict(json.loads(st.secrets["GCP_JSON"]))
    sh = gc.open_by_key(st.secrets["SHEET_ID"])
    data = sh.sheet1
    if data.row_values(1) != TEXT_HEADS:
        data.clear()
        data.append_row(TEXT_HEADS)
    try:
        imgs = sh.worksheet("Images")
    except gspread.WorksheetNotFound:
        imgs = sh.add_worksheet("Images", rows=1000, cols=len(IMG_HEADS))
    if imgs.row_values(1) != IMG_HEADS:
        imgs.clear()
        imgs.append_row(IMG_HEADS)
    return data, imgs


def load_rows():
    data, imgs = get_sheets()
    d = data.get_all_values()[1:]
    i = {r[0]: r for r in imgs.get_all_values()[1:] if r}
    rows = []
    for r in d:
        r = r + [""] * (6 - len(r))
        im = i.get(r[0], [""] * 5) + [""] * 5
        rows.append({
            "submitted": r[1], "ref": r[2], "vin": r[3], "hours": r[4], "odo": r[5],
            "images": {"VIN": im[1], "HRS": im[2], "ODO": im[3], "FRONT": im[4]},
        })
    return rows


st.title("🚚 Vehicle Photo Capture")
if not check_password():
    st.stop()

tab_add, tab_db = st.tabs(["Add new set", "Database"])

with tab_add:
    st.caption("Upload the 4 photos. Adjust each crop box if needed. Tap Save. No AI is used.")
    n = st.session_state.setdefault("nonce", 0)
    types = ["jpg", "jpeg", "png"]
    uploads = {
        "VIN": st.file_uploader("1. VIN plate photo", type=types, key=f"vin{n}"),
        "ODO": st.file_uploader("2. Odometer (km) photo", type=types, key=f"odo{n}"),
        "HRS": st.file_uploader("3. Hours (HRS) photo", type=types, key=f"hrs{n}"),
        "FRONT": st.file_uploader("4. Front of truck photo", type=types, key=f"front{n}"),
    }

    crops = {}
    for k in ("VIN", "ODO", "HRS"):
        if uploads[k]:
            img = load_image(uploads[k])
            dxr, dyr, drot = DEFAULTS[k]
            with st.expander(f"Crop: {LABELS[k]}", expanded=True):
                xr = st.slider("Left to right (%)", 0, 100, dxr, key=f"x{k}{n}")
                yr = st.slider("Top to bottom (%)", 0, 100, dyr, key=f"y{k}{n}")
                rot = st.selectbox("Rotate", [0, 90, 180, 270], index=[0, 90, 180, 270].index(drot),
                                   key=f"r{k}{n}")
                crops[k] = crop_percent(img, xr, yr, rot)
                st.image(crops[k], caption="This crop will be saved in Excel")

    with st.expander("Optional: type values and a vehicle reference"):
        ref = st.text_input("Vehicle ref / plate", key=f"ref{n}")
        t_vin = st.text_input("VIN", key=f"tv{n}")
        t_hrs = st.text_input("Hours", key=f"th{n}")
        t_odo = st.text_input("Odometer km", key=f"to{n}")

    ready = all(uploads.values())
    if st.button("Save to database", type="primary", disabled=not ready):
        with st.spinner("Saving..."):
            now = datetime.now(ZoneInfo("Asia/Kolkata"))
            rid = now.strftime("%Y%m%d%H%M%S%f")[:17]
            data, imgs = get_sheets()
            front = load_image(uploads["FRONT"])
            data.append_row([rid, now.strftime("%Y-%m-%d %H:%M:%S"), ref, t_vin.upper(), t_hrs, t_odo],
                            value_input_option="RAW")
            imgs.append_row([rid, to_b64(crops["VIN"]), to_b64(crops["HRS"]),
                             to_b64(crops["ODO"]), to_b64(front, max_w=400)],
                            value_input_option="RAW")
        st.success("Saved. You can add the next set.")
        st.session_state["nonce"] += 1
        st.rerun()

with tab_db:
    if st.button("Refresh"):
        st.rerun()
    rows = load_rows()
    st.write(f"{len(rows)} records")
    if rows:
        df = pd.DataFrame([{k: r[k] for k in ("submitted", "ref", "vin", "hours", "odo")} for r in rows])
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "Download Excel (with photos in cells)", build_excel(rows), "vehicle_database.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
