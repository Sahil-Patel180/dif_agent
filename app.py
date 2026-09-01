import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from scraper import run
from excel_export import build_excel
from config import (
    SHAPE_OPTIONS, GRADE_OPTIONS, COLOR_OPTIONS,
    CLARITY_OPTIONS, FLUORESCENCE_OPTIONS, LAB_OPTIONS, SHOW_ONLY_OPTIONS,
)

from datetime import date
from dateutil.relativedelta import relativedelta
from excel_export import build_excel, select_and_rename, SUMMARY_COLUMNS, DETAILS_COLUMNS

load_dotenv()

st.set_page_config(page_title="Rapaport Discount Agent", layout="centered")
st.title("Rapaport Discount % Agent")

st.subheader("Login")
col1, col2 = st.columns(2)
username = col1.text_input("Username", value=os.getenv("RAPAPORT_USERNAME", ""))
password = col2.text_input("Password", value=os.getenv("RAPAPORT_PASSWORD", ""), type="password")
company_name = st.text_input("Run Label (optional, used only for the Excel filename)")

st.subheader("Filters")

# 1. Shape
shape = st.selectbox("Shape", SHAPE_OPTIONS)

# 2. Size (carat)
c1, c2 = st.columns(2)
carat_min = c1.number_input("Carat Min", min_value=0.0, step=0.01, value=0.50)
carat_max = c2.number_input("Carat Max", min_value=0.0, step=0.01, value=0.69)

# 3. Color
c3, c4 = st.columns(2)
color_min = c3.selectbox("Color Min", COLOR_OPTIONS)
color_max = c4.selectbox("Color Max", COLOR_OPTIONS)

# 4. Clarity
c5, c6 = st.columns(2)
clarity_min = c5.selectbox("Clarity Min", CLARITY_OPTIONS)
clarity_max = c6.selectbox("Clarity Max", CLARITY_OPTIONS)

# 5. Finish
finish = st.selectbox("Finish (Cut+Pol+Sym together)", GRADE_OPTIONS)

# 6. Fluorescence
fluorescence = st.selectbox("Fluorescence", FLUORESCENCE_OPTIONS)

# 7. Grading Report
lab = st.selectbox("Grading Report / Lab", LAB_OPTIONS)

# 7b. Report Date range — default: today -> 3 months back (per image spec)
st.caption("Report Date range")
rd1, rd2 = st.columns(2)
report_date_from = rd1.date_input("From Date", value=date.today() - relativedelta(months=3))
report_date_to = rd2.date_input("To Date", value=date.today())

# 8. Show Only
show_only = st.selectbox("Show Only", SHOW_ONLY_OPTIONS)

# 9. Depth% (optional — under Measurements)
use_depth = st.checkbox("Filter by Depth%", value=False)
if use_depth:
    c7, c8 = st.columns(2)
    depth_min = c7.number_input("Depth% Min", min_value=0.0, max_value=100.0, value=62.0, step=0.1)
    depth_max = c8.number_input("Depth% Max", min_value=0.0, max_value=100.0, value=65.0, step=0.1)
else:
    depth_min = depth_max = None

include_report_date = True
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
            "finish": finish or None,
            "fluorescence": fluorescence or None,
            "lab": lab or None,
            "report_date_from": report_date_from.strftime("%m/%d/%Y") if report_date_from else None,
            "report_date_to": report_date_to.strftime("%m/%d/%Y") if report_date_to else None,
            "show_only": show_only or None,
            "depth_min": depth_min,
            "depth_max": depth_max,
        }
        with st.spinner("Logging in and fetching results..."):
            try:
                summary_df, df = run(
                    username, password, company_name or "Unknown", filters,
                    headless=headless, include_report_date=True,
                )
            except Exception as e:
                st.error(f"Failed: {e}")
                st.info("Most likely a selector in config.py doesn't match the live page yet. "
                         "Uncheck 'Run headless' and re-run to watch the browser and fix selectors.")
                st.stop()

        st.subheader("Summary (per company)")
        st.dataframe(select_and_rename(summary_df, SUMMARY_COLUMNS))

        st.subheader(f"Report Data ({len(df)} rows)")
        st.dataframe(select_and_rename(df, DETAILS_COLUMNS))

        excel_bytes = build_excel(summary_df, df)

        st.download_button(
            "Download Excel Report",
            data=excel_bytes,
            file_name=f"rapaport_report_{(company_name or 'company').replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )