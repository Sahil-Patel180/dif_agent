"""
scraper.py — Rapaport trade site automation.
Uses label-click pattern for shape/size/color/clarity/fluorescence/lab
(these are custom components, not <select>). See config.py for selector
templates. Company name + report date require an extra click+PDF-open
per stone — set include_report_date=False to skip that for speed.

WINDOWS NOTE: Streamlit runs your script in a worker thread that doesn't
inherit Python's default ProactorEventLoop (needed on Windows for
Playwright to spawn the browser subprocess). Running Playwright directly
there throws NotImplementedError. Fix: run it inside a fresh thread where
we explicitly set the Proactor event loop policy first — see run().
"""

import re
import sys
import asyncio
import threading
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import sync_playwright
import pandas as pd

from config import (
    LOGIN_URL, SELECTORS, RESULT_COLUMNS, PROFILE_DIR,
    shape_label, size_range_label, color_label, clarity_label,
    fluorescence_label, lab_label, finish_quick_button,
)


def login(page, username: str, password: str):
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")

    # Saved profile already trusted -> Rapaport auto-redirects past login.
    # Nothing to do, no OTP needed.
    if page.query_selector(SELECTORS["username_field"]) is None:
        return

    page.fill(SELECTORS["username_field"], username)
    page.fill(SELECTORS["password_field"], password)
    page.click(SELECTORS["login_button"])
    page.wait_for_load_state("networkidle")

    # If an OTP screen appears (new device), give time for manual entry —
    # only happens on first run per profile. Polls up to 2 minutes for the
    # URL to move off the login page (e.g. to #/dashboard or #/search).
    try:
        page.wait_for_function(
            "() => !location.hash.includes('login')",
            timeout=120000,
        )
    except Exception:
        pass  # already past login, or timed out — apply_filters will fail loudly if not


def goto_search_page(page):
    """Login lands on Dashboard, not the filters page — navigate there
    explicitly and wait for the Shape section to actually render before
    any filter clicks are attempted (fixes 'label not found' timeouts)."""
    page.goto(f"{LOGIN_URL}#/search")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(shape_label("Round"), timeout=30000)


def apply_filters(page, filters: dict):
    """
    filters dict keys expected (matches your sheet's green columns):
      shape: str (e.g. 'Round')
      size_range: str (e.g. '0.50 - 0.69') — preset button text
      carat_min, carat_max: float — only used if size_range not given
      color_min, color_max: str single letters (e.g. 'H')
      clarity_min, clarity_max: str (e.g. 'VVS1')
      fluorescence: str (e.g. 'None')
      lab: str (e.g. 'IGI')
      finish: str one of '3X','EX-','VG+','VG-' — sets Cut+Pol+Sym together
      depth_min, depth_max: float — depth% range
    """

    if filters.get("shape"):
        page.click(shape_label(filters["shape"]))

    if filters.get("size_range"):
        page.click(size_range_label(filters["size_range"]))
    else:
        if filters.get("carat_min") is not None:
            page.fill(SELECTORS["carat_min_input"], str(filters["carat_min"]))
        if filters.get("carat_max") is not None:
            page.fill(SELECTORS["carat_max_input"], str(filters["carat_max"]))

    if filters.get("color_min"):
        page.click(color_label(filters["color_min"]))
    if filters.get("color_max") and filters["color_max"] != filters.get("color_min"):
        page.click(color_label(filters["color_max"]))

    if filters.get("clarity_min"):
        page.click(clarity_label(filters["clarity_min"]))
    if filters.get("clarity_max") and filters["clarity_max"] != filters.get("clarity_min"):
        page.click(clarity_label(filters["clarity_max"]))

    if filters.get("fluorescence"):
        page.click(fluorescence_label(filters["fluorescence"]))

    if filters.get("lab"):
        page.click(lab_label(filters["lab"]))

    if filters.get("finish"):
        page.click(finish_quick_button(filters["finish"]))

    if filters.get("depth_min") is not None:
        page.fill(SELECTORS["depth_percent_from"], str(filters["depth_min"]))
    if filters.get("depth_max") is not None:
        page.fill(SELECTORS["depth_percent_to"], str(filters["depth_max"]))

    page.click(SELECTORS["search_button"])
    page.wait_for_load_state("networkidle")


def get_report_date(page, context) -> str | None:
    """Opens the cert/report link in a new tab and intercepts the PDF's raw
    network response (the report renders in Chrome's built-in PDF viewer,
    which lives in a shadow DOM Playwright can't click into — so instead of
    clicking the download button, we grab the PDF bytes straight off the
    network response that loads it). Extracts the date text (e.g.
    'May 27, 2026') from page 1 via pypdf. Returns None if not found."""
    cert_link = page.query_selector(SELECTORS["cert_link"])
    if not cert_link:
        return None

    pdf_bytes_holder = {}

    def handle_response(response):
        content_type = response.headers.get("content-type", "")
        if "pdf" in content_type.lower() and "pdf" not in pdf_bytes_holder:
            try:
                pdf_bytes_holder["pdf"] = response.body()
            except Exception:
                pass

    with context.expect_page() as new_page_info:
        cert_link.click()
    cert_page = new_page_info.value
    cert_page.on("response", handle_response)
    cert_page.wait_for_load_state("networkidle")
    cert_page.wait_for_timeout(1000)  # give the PDF fetch a moment to fire/complete

    date_text = None
    if "pdf" in pdf_bytes_holder:
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(pdf_bytes_holder["pdf"]))
            text = reader.pages[0].extract_text() or ""
            match = re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}", text)
            date_text = match.group(0) if match else None
        except Exception:
            date_text = None

    cert_page.close()
    return date_text


def scrape_results(page, context, include_report_date: bool = True) -> pd.DataFrame:
    """
    Scrapes the results grid (div-based, not a real <table>). Each row is
    clicked to expand and reveal the Seller/company name; optionally opens
    the cert PDF per stone to pull the report date (slow — one extra page
    load per stone). Set include_report_date=False to skip and go fast.
    """
    rows = page.query_selector_all(SELECTORS["result_rows"])

    records = []
    for row in rows:
        cells = row.query_selector_all(SELECTORS["result_cells"])
        if not cells:
            continue

        def cell_text(i):
            return cells[i].inner_text().strip() if i < len(cells) else None

        record = {col: cell_text(i) for i, col in enumerate(RESULT_COLUMNS)}

        # expand row to reveal company name + cert link
        row.click()
        page.wait_for_timeout(500)

        company_el = page.query_selector(SELECTORS["company_name"])
        record["Company"] = company_el.inner_text().strip() if company_el else None

        if include_report_date:
            record["Report Date"] = get_report_date(page, context)

        records.append(record)

    return pd.DataFrame(records)


def compute_min_max_discount(df: pd.DataFrame, company_name: str) -> dict:
    col = "%Rap (Back Discount)"
    disc = pd.to_numeric(
        df[col].astype(str).str.replace("%", "").str.strip(),
        errors="coerce",
    )
    return {
        "Company": company_name,
        "Min Discount %": disc.min(),
        "Max Discount %": disc.max(),
        "Rows Fetched": len(df),
    }


def run(username: str, password: str, company_name: str, filters: dict,
        headless: bool = True, include_report_date: bool = True):
    """
    Full pipeline: login -> filter -> scrape -> summarize.
    Returns (summary_dict, details_dataframe)

    Runs inside a dedicated thread with the Proactor event loop policy set
    explicitly (Windows fix — see module docstring). Safe no-op on
    macOS/Linux.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_impl, username, password, company_name,
                                  filters, headless, include_report_date)
        return future.result()


def _run_impl(username: str, password: str, company_name: str, filters: dict,
              headless: bool, include_report_date: bool):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",   # use real installed Chrome, not bundled Chromium
            headless=headless,
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            login(page, username, password)
            goto_search_page(page)
            apply_filters(page, filters)
            df = scrape_results(page, context, include_report_date=include_report_date)
        finally:
            context.close()

    summary = compute_min_max_discount(df, company_name) if not df.empty else {
        "Company": company_name, "Min Discount %": None, "Max Discount %": None, "Rows Fetched": 0
    }
    return summary, df