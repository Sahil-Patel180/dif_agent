import os
import io
import streamlit as st
import pandas as pd
import traceback
import config
import srk_scraper
from openpyxl.styles import Font
from dotenv import load_dotenv

from scraper import run
from excel_export import build_excel, select_and_rename, DETAILS_COLUMNS
from config import (
    SHAPE_OPTIONS, GRADE_OPTIONS, COLOR_OPTIONS,
    CLARITY_OPTIONS, FLUORESCENCE_OPTIONS, LAB_OPTIONS, SHOW_ONLY_OPTIONS,
    CARAT_RANGES, DEPTH_RANGES, find_range,
    SRK_COLOUR_SCALE, SRK_CLARITY_SCALE, SRK_RANGE_ALL, expand_scale_range,
)

from datetime import date

from srk_scraper import run as run_srk, run_bulk as run_srk_bulk
from checkpoint import file_hash, clear_checkpoint
import undetected_chromedriver as uc
import traceback

load_dotenv()

# confirmed manually 09-Sep-2026: https://pure.srk.one/ auto-redirects to
# https://pure.srk.one/login, so this is the right target, not a guess anymore.
try:
    from config import SRK_LOGIN_URL
except ImportError:
    SRK_LOGIN_URL = "https://pure.srk.one/login"

# Set this to YOUR installed Chrome's major version (chrome://version, first
# number before the first dot). Chrome auto-updates itself in the background —
# every time it bumps past what undetected_chromedriver last matched, you get
# a driver/browser mismatch again (same as the SessionNotCreatedException
# from before) and it can present as a silent white screen instead of a
# clean error, depending on what stage it fails at. Recheck this after every
# Chrome update.
SRK_CHROME_VERSION_MAIN = None  # e.g. 152 — fill in, None = let uc guess (risky)


def build_manual_login_driver():
    """Visible Chrome window — site has captcha, login must be done by hand.
    undetected_chromedriver patches automation signals. On top of that, the site
    also loads assets/js/disable-devtool.min.js which shows a blocking overlay —
    block that request outright via CDP so it never runs.
    """
    opts = uc.ChromeOptions()
    opts.add_argument(f"--user-data-dir={config.SRK_PROFILE_DIR}")
    opts.add_argument("--start-maximized")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    # opts.page_load_strategy = "eager"  # don't wait for full page load, just DOM ready
    # enables driver.get_log("browser") below — without this capability set,
    # get_log() silently returns [] even when the page threw real JS errors
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    uc_kwargs = {"options": opts, "log_level": 0}
    if SRK_CHROME_VERSION_MAIN:
        uc_kwargs["version_main"] = SRK_CHROME_VERSION_MAIN

    driver = uc.Chrome(**uc_kwargs)
    driver.maximize_window()
    driver.set_page_load_timeout(60)
    driver.execute_cdp_cmd("Network.enable", {})
    # Confirmed 09-Sep-2026 via console diagnostics + screenshot: page DOES
    # bootstrap fine underneath — the disable-devtool script throws a
    # full-screen block overlay on top of the working app, which just LOOKS
    # like a white screen. Blocking the exact confirmed URL is the fix.
    driver.execute_cdp_cmd(
        "Network.setBlockedURLs",
        {"urls": ["*://pure.srk.one/assets/js/disable-devtool.min.js"]},
    )
    return driver


def _diagnose_blank_page(driver, label=""):
    """Prints to the TERMINAL running `streamlit run app.py` — NOT the
    Streamlit browser tab. Check the terminal window, not the page, for
    this output."""
    try:
        print(f"[srk][diag]{' ' + label if label else ''} url:", driver.current_url)
        print(f"[srk][diag] readyState:", driver.execute_script("return document.readyState"))
        print(f"[srk][diag] body length:", len(driver.execute_script("return document.body.innerHTML")))
        for entry in driver.get_log("browser"):
            print(f"[srk][diag][console] {entry.get('level')}: {entry.get('message')}")
    except Exception as e:
        print(f"[srk][diag] diagnostic itself failed: {type(e).__name__}: {e}")

st.set_page_config(page_title="Rapaport Discount Agent", layout="centered")
st.title("Rapaport Discount % Agent")

platform = st.radio("Platform", ["Rapaport", "SRK"])
company_name = st.text_input("Run Label (optional, used only for the Excel filename)")

if platform == "Rapaport":
    st.subheader("Login")
    col1, col2 = st.columns(2)
    username = col1.text_input("Username", value=os.getenv("RAPAPORT_USERNAME", ""))
    password = col2.text_input("Password", value=os.getenv("RAPAPORT_PASSWORD", ""), type="password")

    st.subheader("Filters")

    # 1. Shape
    shape = st.selectbox("Shape", SHAPE_OPTIONS, index=SHAPE_OPTIONS.index("Round"))

    # 2. Size (carat) — default 1.00-1.00. Editing From auto-settles To to
    # the matching bucket in CARAT_RANGES (config.py). Editing To leaves
    # From untouched — no snap-back on that side.
    def _settle_carat_from():
        val = st.session_state["carat_from"]
        match = find_range(val, CARAT_RANGES)
        if match:
            st.session_state["carat_from"], st.session_state["carat_to"] = match

    if "carat_from" not in st.session_state:
        st.session_state["carat_from"], st.session_state["carat_to"] = CARAT_RANGES[0]

    cc1, cc2 = st.columns(2)
    cc1.number_input("Carat From", step=0.01, key="carat_from", on_change=_settle_carat_from)
    cc2.number_input("Carat To", step=0.01, key="carat_to")

    # 3. Color
    c3, c4 = st.columns(2)
    color_min = c3.selectbox("Color Min", COLOR_OPTIONS, index=COLOR_OPTIONS.index("D"))
    color_max = c4.selectbox("Color Max", COLOR_OPTIONS, index=COLOR_OPTIONS.index("M"))

    # 4. Clarity
    c5, c6 = st.columns(2)
    clarity_min = c5.selectbox("Clarity Min", CLARITY_OPTIONS, index=CLARITY_OPTIONS.index("FL"))
    clarity_max = c6.selectbox("Clarity Max", CLARITY_OPTIONS, index=CLARITY_OPTIONS.index("VVS2"))

    # 4b. No BGM — always forced on in apply_filters(), not user-toggleable
    st.caption("No BGM: always applied")

    # 5. Finish
    finish = st.selectbox("Finish (Cut+Pol+Sym together)", GRADE_OPTIONS, index=GRADE_OPTIONS.index("3X"))

    # 6. Fluorescence
    fluorescence = st.selectbox("Fluorescence", FLUORESCENCE_OPTIONS, index=FLUORESCENCE_OPTIONS.index("None"))

    # 7. Grading Report
    lab = st.selectbox("Grading Report / Lab", LAB_OPTIONS, index=LAB_OPTIONS.index("GIA"))

    # 7b. Report Date range — OPTIONAL, same pattern as Depth% below.
    # Unchecked means the filter is not sent at all (None), so the site
    # returns every report date instead of silently clamping to 2024-today.
    use_report_date = st.checkbox("Filter by Report Date range", value=False)
    report_date_from = report_date_to = None
    if use_report_date:
        st.caption("Report Date range")
        rd1, rd2 = st.columns(2)
        report_date_from = rd1.date_input("From Date", value=date(2024, 1, 1))
        report_date_to = rd2.date_input("To Date", value=date.today())

    # 8. Show Only — OPTIONAL. Unchecked = no Show Only chip applied.
    use_show_only = st.checkbox("Filter by Show Only", value=False)
    show_only = None
    if use_show_only:
        show_only = st.selectbox("Show Only", SHOW_ONLY_OPTIONS, index=0)

    # 9. Depth% — optional. When on: give either From or To, other
    # auto-settles to the matching bucket in DEPTH_RANGES (config.py)
    def _settle_depth(edited: str):
        val = st.session_state[f"depth_{edited}"]
        match = find_range(val, DEPTH_RANGES)
        if match:
            st.session_state["depth_from"], st.session_state["depth_to"] = match

    use_depth = st.checkbox("Filter by Depth%", value=False)
    if use_depth:
        if "depth_from" not in st.session_state:
            st.session_state["depth_from"], st.session_state["depth_to"] = DEPTH_RANGES[0]
        dd1, dd2 = st.columns(2)
        dd1.number_input("Depth% From", step=0.1, key="depth_from", on_change=_settle_depth, args=("from",))
        dd2.number_input("Depth% To", step=0.1, key="depth_to", on_change=_settle_depth, args=("to",))

    include_report_date = True
    headless = st.checkbox("Run headless (uncheck first time to watch & debug selectors)", value=False)
    resume = st.checkbox(
        "Resume previous run if it crashed/stopped midway (same filters)",
        value=True,
        help="If a checkpoint exists for this exact filter combo, already-scraped rows are skipped, not re-fetched.",
    )

    if st.button("Run Search"):
        if not username or not password:
            st.error("Enter username and password.")
        else:
            filters = {
                "shape": shape,
                "carat_min": st.session_state["carat_from"],
                "carat_max": st.session_state["carat_to"],
                "color_min": color_min,
                "color_max": color_max,
                "clarity_min": clarity_min,
                "clarity_max": clarity_max,
                "finish": finish,
                "fluorescence": fluorescence,
                "lab": lab,
                "report_date_from": report_date_from.strftime("%m/%d/%Y") if report_date_from else None,
                "report_date_to": report_date_to.strftime("%m/%d/%Y") if report_date_to else None,
                "show_only": show_only,
                "depth_min": st.session_state["depth_from"] if use_depth else None,
                "depth_max": st.session_state["depth_to"] if use_depth else None,
            }
            with st.spinner("Logging in and fetching results..."):
                try:
                    df, checkpoint_csv_path, checkpoint_progress_path = run(
                        username, password, company_name or "Unknown", filters,
                        headless=headless, include_report_date=True, resume=resume,
                    )
                except Exception as e:
                    st.error(f"Failed: {e}")
                    st.info("Most likely a selector in config.py doesn't match the live page yet. "
                             "Uncheck 'Run headless' and re-run to watch the browser and fix selectors.")
                    st.stop()

            st.subheader(f"Report Data ({len(df)} rows)")
            st.dataframe(select_and_rename(df, DETAILS_COLUMNS))

            excel_bytes = build_excel(df)

            st.download_button(
                "Download Excel Report",
                data=excel_bytes,
                file_name=f"rapaport_report_{(company_name or 'company').replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            if st.button("Clear checkpoint (search done, start fresh next time)"):
                clear_checkpoint(checkpoint_csv_path, checkpoint_progress_path)
                st.success("Checkpoint cleared.")

elif platform == "SRK":
    st.subheader("Bulk Search (multiple input sets)")
    st.caption(
        "Upload agent_srk_bulkinput.xlsx. Each row = one input set, run sequentially: "
        "enter filters -> search -> full scroll-scan results -> back to input page -> next row. "
        "Cols read: SHAPE, CARAT From, CARAT To, CLARITY, COLOUR, SHADE, CUT, POLISH, "
        "SYMMETRY, FLUORESCENCE, LUSTER, LAB, TOTAL DEPTH From, TOTAL DEPTH To."
    )
    bulk_file = st.file_uploader("Bulk input file", type=["xlsx"], key="bulk_file")
    resume = st.checkbox(
        "Resume previous run if it crashed/stopped midway (same file)",
        value=True,
        help="If a checkpoint exists for this exact file, already-scraped rows are skipped, not re-fetched.",
    )

    col_c, col_d = st.columns(2)
    if col_c.button("1. Open Browser & Login (bulk)"):
        if "srk_driver" in st.session_state:
            try:
                st.session_state.srk_driver.quit()
            except Exception:
                pass
        st.session_state.srk_driver = build_manual_login_driver()
        st.session_state.srk_driver.get(SRK_LOGIN_URL)
        _diagnose_blank_page(st.session_state.srk_driver, label="(bulk open)")
        st.info("Browser window opened. Log in + solve captcha there, then click step 2 below. "
                "If the window is white, check the TERMINAL (not this page) for [srk][diag] lines.")

    run_bulk_clicked = col_d.button("2. I've Logged In → Run Bulk")

    if run_bulk_clicked:
        if "srk_driver" not in st.session_state:
            st.error("Click 'Open Browser & Login (bulk)' first.")
        elif bulk_file is None:
            st.error("Upload agent_srk_bulkinput.xlsx first.")
        else:
            raw_bytes = bulk_file.getvalue()
            run_id = file_hash(raw_bytes)
            bulk_df = pd.read_excel(io.BytesIO(raw_bytes))
            bulk_input_df = bulk_df.copy()
            bulk_input_df.insert(
                0,
                "Input Row",
                range(1, len(bulk_input_df) + 1)
            )

            try:
                st.session_state.srk_driver.minimize_window()
                st.session_state.srk_driver.maximize_window()
            except Exception:
                pass  # OS-level focus trick — window may already be gone/closed manually

            progress = st.progress(0.0, text="Starting...")
            status = st.empty()

            def _progress_cb(i, total, filters):
                progress.progress(i / total, text=f"Row {i}/{total}")
                status.write(f"Row {i}/{total}: {filters}")

            with st.spinner("Running bulk search..."):
                try:
                    inputs_df, all_df, checkpoint_csv_path, checkpoint_progress_path = run_srk_bulk(
                        st.session_state.srk_driver, bulk_df, progress_cb=_progress_cb,
                        run_id=run_id, resume=resume,
                    )
                except Exception as e:
                    traceback.print_exc()
                    st.error(f"Bulk run failed: {e}")
                    st.stop()
                finally:
                    try:
                        srk_scraper.logout(st.session_state.srk_driver)
                    except Exception:
                        pass
                    try:
                        st.session_state.srk_driver.quit()
                    except Exception:
                        pass
                    if "srk_driver" in st.session_state:
                        del st.session_state.srk_driver

            st.subheader(f"Bulk Results ({len(all_df)} rows across {len(inputs_df)} input sets)")
            st.dataframe(all_df)

            found_input_rows = set()

            if not all_df.empty and "Input Row" in all_df.columns:
                found_input_rows = set(
                    pd.to_numeric(
                        all_df["Input Row"],
                        errors="coerce"
                    )
                    .dropna()
                    .astype(int)
                    .tolist()
                )

            not_found_df = bulk_input_df[
                ~bulk_input_df["Input Row"].isin(found_input_rows)
            ].copy()

            # Show input parameters that produced no results
            st.subheader(
                f"Inputs With No Results ({len(not_found_df)})"
            )
            st.dataframe(not_found_df)

            bulk_buffer = io.BytesIO()

            with pd.ExcelWriter(
                bulk_buffer,
                engine="openpyxl"
            ) as writer:

                inputs_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="INPUTS"
                )

                all_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="ALL"
                )

                not_found_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="NOT FOUND"
                )

                for sheet_name in (
                    "INPUTS",
                    "ALL",
                    "NOT FOUND",
                ):
                    ws = writer.sheets[sheet_name]

                    # Bold header
                    for cell in ws[1]:
                        cell.font = Font(
                            name="Arial",
                            bold=True
                        )

                    # Auto-size columns
                    for col_cells in ws.columns:
                        width = max(
                            len(str(c.value))
                            if c.value is not None
                            else 0
                            for c in col_cells
                        ) + 2

                        ws.column_dimensions[
                            col_cells[0].column_letter
                        ].width = min(width, 40)

            st.download_button(
                "Download Bulk Excel Report",
                data=bulk_buffer.getvalue(),
                file_name=f"srk_bulk_report_{(company_name or 'company').replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            if st.button("Clear checkpoint (all rows done, start fresh next time)"):
                clear_checkpoint(checkpoint_csv_path, checkpoint_progress_path)
                st.success("Checkpoint cleared.")
    st.divider()
    st.subheader("Filters")
    shape = st.selectbox("Shape", ["Round", "Oval", "Pear", "Emerald", "L Radiant",
                                    "Princess", "Sq Emerald", "Heart", "Marquise",
                                    "Cushion", "Cu Plasma", "Triangular"])
    c1, c2 = st.columns(2)
    carat_min = c1.number_input("Carat Min", min_value=0.0, step=0.01, value=0.0)
    carat_max = c2.number_input("Carat Max", min_value=0.0, step=0.01, value=0.0)

    # Clarity / Colour as From-To ranges (Rapaport-style). SRK has no range
    # control of its own — expand_scale_range() turns the pair into the list
    # of chips to click, and apply_filters() already accepts a list per
    # filter key and clicks each chip. "All" on either side = not applied.
    cl1, cl2 = st.columns(2)
    clarity_from = cl1.selectbox("Clarity From", [SRK_RANGE_ALL] + SRK_CLARITY_SCALE, index=0)
    clarity_to = cl2.selectbox("Clarity To", [SRK_RANGE_ALL] + SRK_CLARITY_SCALE, index=0)
    clarity_preview = expand_scale_range(SRK_CLARITY_SCALE, clarity_from, clarity_to)

    co1, co2 = st.columns(2)
    colour_from = co1.selectbox("Colour From", [SRK_RANGE_ALL] + SRK_COLOUR_SCALE, index=0)
    colour_to = co2.selectbox("Colour To", [SRK_RANGE_ALL] + SRK_COLOUR_SCALE, index=0)
    colour_preview = expand_scale_range(SRK_COLOUR_SCALE, colour_from, colour_to)

    st.caption(
        f"Will select on site — Clarity: {', '.join(clarity_preview) or 'All'} | "
        f"Colour: {', '.join(colour_preview) or 'All'}"
    )
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

    fetch_video = st.checkbox("Fetch video link URL (slower — opens new tab per row)", value=False)

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
        _diagnose_blank_page(st.session_state.srk_driver, label="(single open)")
        st.info("Browser window opened. Log in + solve captcha there, then click step 2 below. "
                "If the window is white, check the TERMINAL (not this page) for [srk][diag] lines.")

    run_clicked = col_b.button("2. I've Logged In → Run Search")

    if run_clicked:
        if "srk_driver" not in st.session_state:
            st.error("Click 'Open Browser & Login' first.")
        else:
            filters = {
                "shape": shape or None,
                "carat_from": carat_min or None,
                "carat_to": carat_max or None,
                # From/To pair sent straight through — srk_scraper's
                # resolve_range_filters() expands it into the chips to click.
                "clarity_from": clarity_from,
                "clarity_to": clarity_to,
                "colour_from": colour_from,
                "colour_to": colour_to,
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

            # Bring the Chrome window back to the front before driving it.
            # The bulk path already does this; the single path didn't, so
            # after clicking "I've Logged In -> Run Search" in the Streamlit
            # tab the browser stayed buried behind it and every click landed
            # on a background window.
            try:
                st.session_state.srk_driver.switch_to.window(
                    st.session_state.srk_driver.current_window_handle
                )
                st.session_state.srk_driver.minimize_window()
                st.session_state.srk_driver.maximize_window()
            except Exception:
                pass  # OS-level focus trick — window may already be gone/closed manually

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
                        srk_scraper.logout(st.session_state.srk_driver)
                    except Exception:
                        pass
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