import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from scraper import run
from excel_export import build_excel
from config import (
    SHAPE_OPTIONS, GRADE_OPTIONS, COLOR_OPTIONS,
    CLARITY_OPTIONS, FLUORESCENCE_OPTIONS, LAB_OPTIONS,
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
c1, c2 = st.columns(2)
shape = c1.selectbox("Shape", SHAPE_OPTIONS)
finish = c2.selectbox("Finish (Cut+Pol+Sym together)", GRADE_OPTIONS)

size_range = st.selectbox(
    "Carat Range (preset)",
    ["", "0.30 - 0.39", "0.40 - 0.49", "0.50 - 0.69", "0.70 - 0.89",
     "0.90 - 0.99", "1.00 - 1.49", "1.50 - 1.99", "2.00 - 2.99",
     "3.00 - 3.99", "4.00 - 4.99", "5.00 - 5.99", "6.00 - 9.99", "10.00 - 10.99"],
)

c3, c4 = st.columns(2)
color_min = c3.selectbox("Color Min", COLOR_OPTIONS)
color_max = c4.selectbox("Color Max", COLOR_OPTIONS)

c5, c6 = st.columns(2)
clarity_min = c5.selectbox("Clarity Min", CLARITY_OPTIONS)
clarity_max = c6.selectbox("Clarity Max", CLARITY_OPTIONS)

fluorescence = st.selectbox("Fluorescence", FLUORESCENCE_OPTIONS)
lab = st.selectbox("Grading Report / Lab", LAB_OPTIONS)

c7, c8 = st.columns(2)
depth_min = c7.number_input("Depth% Min", min_value=0.0, max_value=100.0, value=62.0, step=0.1)
depth_max = c8.number_input("Depth% Max", min_value=0.0, max_value=100.0, value=65.0, step=0.1)

include_report_date = st.checkbox(
    "Fetch report date per stone (opens each cert PDF — slower)", value=False
)
headless = st.checkbox("Run headless (uncheck first time to watch & debug selectors)", value=False)

if st.button("Run Search"):
    if not username or not password:
        st.error("Enter username and password.")
    else:
        filters = {
            "shape": shape or None,
            "size_range": size_range or None,
            "color_min": color_min or None,
            "color_max": color_max or None,
            "clarity_min": clarity_min or None,
            "clarity_max": clarity_max or None,
            "fluorescence": fluorescence or None,
            "lab": lab or None,
            "finish": finish or None,
            "depth_min": depth_min,
            "depth_max": depth_max,
        }
        with st.spinner("Logging in and fetching results..."):
            try:
                summary_df, df = run(
                    username, password, company_name or "Unknown", filters,
                    headless=headless, include_report_date=include_report_date,
                )
            except Exception as e:
                st.error(f"Failed: {e}")
                st.info("Most likely a selector in config.py doesn't match the live page yet. "
                         "Uncheck 'Run headless' and re-run to watch the browser and fix selectors.")
                st.stop()

        st.subheader("Summary (per company)")
        st.dataframe(summary_df)

        st.subheader(f"Report Data ({len(df)} rows)")
        st.dataframe(df)

        excel_bytes = build_excel(summary_df, df)

        st.download_button(
            "Download Excel Report",
            data=excel_bytes,
            file_name=f"rapaport_report_{(company_name or 'company').replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )