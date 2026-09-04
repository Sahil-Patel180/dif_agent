import os
import io
import streamlit as st
import pandas as pd
import traceback
from openpyxl.styles import Font
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

from srk_scraper import run as run_srk, run_bulk as run_srk_bulk
import undetected_chromedriver as uc
import traceback

load_dotenv()

# TODO verify: add SRK_LOGIN_URL to config.py (login page URL, not search URL)
try:
    from config import SRK_LOGIN_URL
except ImportError:
    SRK_LOGIN_URL = "https://pure.srk.one/login"  # placeholder, verify real path


def build_manual_login_driver():
    """Visible Chrome window — site has captcha, login must be done by hand.
    undetected_chromedriver patches automation signals. On top of that, the site
    also loads assets/js/disable-devtool.min.js which shows a blocking overlay —
    block that request outright via CDP so it never runs.
    """
    opts = uc.ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.page_load_strategy = "eager"  # don't wait for full page load, just DOM ready
    driver = uc.Chrome(options=opts, log_level=0)
    driver.set_page_load_timeout(60)
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": ["*disable-devtool*"]})
    return driver

st.set_page_config(page_title="Rapaport Discount Agent", layout="centered")
st.title("Rapaport Discount % Agent")

st.subheader("Login")
col1, col2 = st.columns(2)
username = col1.text_input("Username", value=os.getenv("RAPAPORT_USERNAME", ""))
password = col2.text_input("Password", value=os.getenv("RAPAPORT_PASSWORD", ""), type="password")
company_name = st.text_input("Run Label (optional, used only for the Excel filename)")
platform = st.radio("Platform", ["Rapaport", "SRK"])

if platform == "Rapaport":
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

            excel_bytes = build_excel(summary_df, df, report_date_from, report_date_to)

            st.download_button(
                "Download Excel Report",
                data=excel_bytes,
                file_name=f"rapaport_report_{(company_name or 'company').replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

elif platform == "SRK":
    st.subheader("Filters")

    shape = st.selectbox("Shape", ["Round", "Oval", "Pear", "Emerald", "L Radiant",
                                    "Princess", "Sq Emerald", "Heart", "Marquise",
                                    "Cushion", "Cu Plasma", "Triangular"])
    c1, c2 = st.columns(2)
    carat_min = c1.number_input("Carat Min", min_value=0.0, step=0.01, value=0.0)
    carat_max = c2.number_input("Carat Max", min_value=0.0, step=0.01, value=0.0)

    clarity = st.selectbox("Clarity", ["FL", "IF", "VVS1", "VVS2", "VS1", "VS2",
                                        "SI1", "SI2", "SI3", "I1", "I2", "I3"])
    colour = st.selectbox("Colour", ["D", "E", "F", "G", "H", "I", "J", "K", "L", "M"])
    shade = st.selectbox("Shade", ["None", "Brown", "Mix Tinge 1", "Mix Tinge 2",
                                    "Pink Tinge", "Green Tinge"])
    cut = st.selectbox("Cut", ["EX", "VG", "G", "F"])
    polish = st.selectbox("Polish", ["EX", "VG", "G", "F"])
    symmetry = st.selectbox("Symmetry", ["EX", "VG", "G", "F"])
    fluorescence = st.selectbox("Fluorescence", ["None", "Faint", "Medium", "Strong", "Very Strong"])
    luster = st.selectbox("Luster", ["Excellent", "Very Good", "Good", "Slight Milky",
                                      "Medium Milky", "Heavy Milky"])
    lab = st.selectbox("Lab", ["GIA", "IGI", "Non-Cert", "HRD", "FM", "IOD"])

    c3, c4 = st.columns(2)
    total_depth_min = c3.number_input("Total Depth Min", min_value=0.0, max_value=100.0, value=0.0, step=0.1)
    total_depth_max = c4.number_input("Total Depth Max", min_value=0.0, max_value=100.0, value=0.0, step=0.1)

    fetch_video = st.checkbox("Fetch video link URL (slower — opens new tab per row)", value=True)

    st.caption("Site has captcha → login done by hand in a real browser window. Headless not possible.")

    col_a, col_b = st.columns(2)

    if col_a.button("1. Open Browser & Login"):
        if "srk_driver" in st.session_state:
            try:
                st.session_state.srk_driver.quit()
            except Exception:
                pass
        st.session_state.srk_driver = build_manual_login_driver()
        st.session_state.srk_driver.get(SRK_LOGIN_URL)
        st.info("Browser window opened. Log in + solve captcha there, then click step 2 below.")

    run_clicked = col_b.button("2. I've Logged In → Run Search")

    if run_clicked:
        if "srk_driver" not in st.session_state:
            st.error("Click 'Open Browser & Login' first.")
        else:
            filters = {
                "shape": shape or None,
                "carat_from": carat_min or None,
                "carat_to": carat_max or None,
                "clarity": clarity or None,
                "colour": colour or None,
                "shade": shade or None,
                "cut": cut or None,
                "polish": polish or None,
                "symmetry": symmetry or None,
                "fluorescence": fluorescence or None,
                "luster": luster or None,
                "lab": lab or None,
                "total_depth_from": total_depth_min or None,
                "total_depth_to": total_depth_max or None,
            }
            with st.spinner("Fetching results..."):
                try:
                    srk_df = run_srk(st.session_state.srk_driver, filters, fetch_video=fetch_video)
                except Exception as e:
                    traceback.print_exc()  # full stack -> terminal, read this not the red box
                    st.error(f"Failed: {e}")
                    st.info("Most likely a selector in srk_scraper.py doesn't match the live page yet "
                             "(login page selectors + search page selectors both unverified — check with browser open).")
                    st.stop()
                finally:
                    try:
                        st.session_state.srk_driver.quit()
                    except Exception:
                        pass
                    del st.session_state.srk_driver

            st.subheader(f"SRK Results ({len(srk_df)} rows)")
            st.dataframe(srk_df)

            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                srk_df.to_excel(writer, index=False, sheet_name="SRK Results")
                ws = writer.sheets["SRK Results"]
                for row in ws.iter_rows():
                    for cell in row:
                        cell.font = Font(name="Arial", bold=(cell.row == 1))
                for col_cells in ws.columns:
                    width = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells) + 2
                    ws.column_dimensions[col_cells[0].column_letter].width = min(width, 40)

            st.download_button(
                "Download Excel Report",
                data=excel_buffer.getvalue(),
                file_name=f"srk_report_{(company_name or 'company').replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    st.divider()
    st.subheader("Bulk Search (multiple input sets)")
    st.caption(
        "Upload agent_srk_bulkinput.xlsx. Each row = one input set, run sequentially: "
        "enter filters -> search -> full scroll-scan results -> back to input page -> next row. "
        "Cols read: SHAPE, CARAT From, CARAT To, CLARITY, COLOUR, SHADE, CUT, POLISH, "
        "SYMMETRY, FLUORESCENCE, LUSTER, LAB, TOTAL DEPTH From, TOTAL DEPTH To."
    )
    bulk_file = st.file_uploader("Bulk input file", type=["xlsx"], key="bulk_file")

    col_c, col_d = st.columns(2)
    if col_c.button("1. Open Browser & Login (bulk)"):
        if "srk_driver" in st.session_state:
            try:
                st.session_state.srk_driver.quit()
            except Exception:
                pass
        st.session_state.srk_driver = build_manual_login_driver()
        st.session_state.srk_driver.get(SRK_LOGIN_URL)
        st.info("Browser window opened. Log in + solve captcha there, then click step 2 below.")

    run_bulk_clicked = col_d.button("2. I've Logged In → Run Bulk")

    if run_bulk_clicked:
        if "srk_driver" not in st.session_state:
            st.error("Click 'Open Browser & Login (bulk)' first.")
        elif bulk_file is None:
            st.error("Upload agent_srk_bulkinput.xlsx first.")
        else:
            bulk_df = pd.read_excel(bulk_file)
            progress = st.progress(0.0, text="Starting...")
            status = st.empty()

            def _progress_cb(i, total, filters):
                progress.progress(i / total, text=f"Row {i}/{total}")
                status.write(f"Row {i}/{total}: {filters}")

            with st.spinner("Running bulk search..."):
                try:
                    inputs_df, all_df = run_srk_bulk(
                        st.session_state.srk_driver, bulk_df, progress_cb=_progress_cb
                    )
                except Exception as e:
                    traceback.print_exc()
                    st.error(f"Bulk run failed: {e}")
                    st.stop()
                finally:
                    try:
                        st.session_state.srk_driver.quit()
                    except Exception:
                        pass
                    if "srk_driver" in st.session_state:
                        del st.session_state.srk_driver

            st.subheader(f"Bulk Results ({len(all_df)} rows across {len(inputs_df)} input sets)")
            st.dataframe(all_df)

            bulk_buffer = io.BytesIO()
            with pd.ExcelWriter(bulk_buffer, engine="openpyxl") as writer:
                inputs_df.to_excel(writer, index=False, sheet_name="INPUTS")
                all_df.to_excel(writer, index=False, sheet_name="ALL")
                for sheet_name in ("INPUTS", "ALL"):
                    ws = writer.sheets[sheet_name]
                    for row in ws.iter_rows():
                        for cell in row:
                            cell.font = Font(name="Arial", bold=(cell.row == 1))
                    for col_cells in ws.columns:
                        width = max(
                            len(str(c.value)) if c.value is not None else 0 for c in col_cells
                        ) + 2
                        ws.column_dimensions[col_cells[0].column_letter].width = min(width, 40)

            st.download_button(
                "Download Bulk Excel Report",
                data=bulk_buffer.getvalue(),
                file_name=f"srk_bulk_report_{(company_name or 'company').replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )