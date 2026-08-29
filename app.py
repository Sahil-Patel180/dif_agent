import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from scraper import run
from excel_export import build_excel
from config import (
    SHAPE_OPTIONS, GRADE_OPTIONS, COLOR_OPTIONS,
    CLARITY_OPTIONS, FLUORESCENCE_OPTIONS,
)

load_dotenv()

st.set_page_config(page_title="Rapaport Discount Agent", layout="centered")
st.title("Rapaport Discount % Agent")

st.subheader("Login")
col1, col2 = st.columns(2)
username = col1.text_input("Username", value=os.getenv("RAPAPORT_USERNAME", ""))
password = col2.text_input("Password", value=os.getenv("RAPAPORT_PASSWORD", ""), type="password")
company_name = st.text_input("Company Name (label for this run)")

st.subheader("Filters")
c1, c2, c3, c4 = st.columns(4)
shape = c1.selectbox("Shape", SHAPE_OPTIONS)
cut = c2.selectbox("Cut", GRADE_OPTIONS)
polish = c3.selectbox("Polish", GRADE_OPTIONS)
symmetry = c4.selectbox("Symmetry", GRADE_OPTIONS)

c5, c6 = st.columns(2)
carat_min = c5.number_input("Carat Min", min_value=0.0, step=0.01, value=0.30)
carat_max = c6.number_input("Carat Max", min_value=0.0, step=0.01, value=2.00)

c7, c8 = st.columns(2)
color_min = c7.selectbox("Color Min", COLOR_OPTIONS)
color_max = c8.selectbox("Color Max", COLOR_OPTIONS)

c9, c10 = st.columns(2)
clarity_min = c9.selectbox("Clarity Min", CLARITY_OPTIONS)
clarity_max = c10.selectbox("Clarity Max", CLARITY_OPTIONS)

fluorescence = st.selectbox("Fluorescence (FL col)", FLUORESCENCE_OPTIONS)

headless = st.checkbox("Run headless (uncheck first time to watch & debug selectors)", value=False)

if st.button("Run Search"):
    if not username or not password:
        st.error("Enter username and password.")
    else:
        filters = {
            "shape": shape or None,
            "carat_min": carat_min,
            "carat_max": carat_max,
            "color_min": color_min or None,
            "color_max": color_max or None,
            "clarity_min": clarity_min or None,
            "clarity_max": clarity_max or None,
            "cut": cut or None,
            "polish": polish or None,
            "symmetry": symmetry or None,
            "fluorescence": fluorescence or None,
        }
        with st.spinner("Logging in and fetching results..."):
            try:
                summary, df = run(username, password, company_name or "Unknown", filters, headless=headless)
            except Exception as e:
                st.error(f"Failed: {e}")
                st.info("Most likely a selector in config.py doesn't match the live page yet. "
                         "Uncheck 'Run headless' and re-run to watch the browser and fix selectors.")
                st.stop()

        st.subheader("Summary")
        st.table(pd.DataFrame([summary]))

        st.subheader("Report Data")
        st.dataframe(df)

        excel_bytes = build_excel(summary, df)

        st.download_button(
            "Download Excel Report",
            data=excel_bytes,
            file_name=f"rapaport_report_{(company_name or 'company').replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )