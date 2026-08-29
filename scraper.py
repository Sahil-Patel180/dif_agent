"""
scraper.py — Rapaport trade site automation.

IMPORTANT: Rapaport is a login-walled site. The exact HTML selectors below
(login fields, filter dropdowns, result table) are PLACEHOLDERS.
You must open https://trade.rapaport.com/ in Chrome, log in manually,
open DevTools (F12) -> Inspect element on each field, and replace the
selector strings marked "# TODO: verify selector" with the real ones.

How to find a selector fast:
  1. Right-click the field on the page -> Inspect
  2. In DevTools, right-click the highlighted HTML -> Copy -> Copy selector
  3. Paste that value in place of the placeholder string below

Run once with headless=False (see run() call in app.py) so you can watch
the browser and confirm each step works before trusting the output.
"""

from playwright.sync_api import sync_playwright
import pandas as pd


LOGIN_URL = "https://trade.rapaport.com/"


def login(page, username: str, password: str):
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")

    # TODO: verify selector — username field
    page.fill("#username", username)
    # TODO: verify selector — password field
    page.fill("#password", password)
    # TODO: verify selector — submit/login button
    page.click("button[type='submit']")

    page.wait_for_load_state("networkidle")


def apply_filters(page, filters: dict):
    """
    filters dict keys expected (matches your sheet's green columns):
    shape, carat_min, carat_max, color_min, color_max,
    clarity_min, clarity_max, cut, polish, symmetry, fluorescence
    """

    # TODO: verify selector — navigate to search/diamond-list page if not default
    # page.click("text=Search")

    # Example pattern — adjust per actual field type (select vs input vs multiselect)
    if filters.get("shape"):
        # TODO: verify selector
        page.select_option("#shapeSelect", filters["shape"])

    if filters.get("carat_min") is not None:
        # TODO: verify selector
        page.fill("#caratMin", str(filters["carat_min"]))
    if filters.get("carat_max") is not None:
        # TODO: verify selector
        page.fill("#caratMax", str(filters["carat_max"]))

    if filters.get("color_min"):
        # TODO: verify selector
        page.select_option("#colorMin", filters["color_min"])
    if filters.get("color_max"):
        # TODO: verify selector
        page.select_option("#colorMax", filters["color_max"])

    if filters.get("clarity_min"):
        # TODO: verify selector
        page.select_option("#claritySelectMin", filters["clarity_min"])
    if filters.get("clarity_max"):
        # TODO: verify selector
        page.select_option("#claritySelectMax", filters["clarity_max"])

    if filters.get("cut"):
        # TODO: verify selector
        page.select_option("#cutSelect", filters["cut"])
    if filters.get("polish"):
        # TODO: verify selector
        page.select_option("#polishSelect", filters["polish"])
    if filters.get("symmetry"):
        # TODO: verify selector
        page.select_option("#symmetrySelect", filters["symmetry"])
    if filters.get("fluorescence"):
        # TODO: verify selector
        page.select_option("#fluorescenceSelect", filters["fluorescence"])

    # TODO: verify selector — the "Search" / "Apply filters" button
    page.click("button#searchBtn")
    page.wait_for_load_state("networkidle")


def scrape_results(page) -> pd.DataFrame:
    """
    Scrapes the result grid. Adjust the table row/column selectors to match
    Rapaport's actual result table structure (likely an HTML <table> or
    div-based grid). Column list below mirrors your uploaded sheet.
    """

    # TODO: verify selector — result table rows
    rows = page.query_selector_all("table#resultsTable tbody tr")

    records = []
    for row in rows:
        cells = row.query_selector_all("td")
        if not cells:
            continue

        def cell_text(i):
            return cells[i].inner_text().strip() if i < len(cells) else None

        # TODO: map each index below to the real column order on the page
        record = {
            "Packet No.": cell_text(1),
            "Shape": cell_text(2),
            "Cts": cell_text(3),
            "Col": cell_text(4),
            "Cla": cell_text(5),
            "Cut": cell_text(6),
            "Pol": cell_text(7),
            "Sym": cell_text(8),
            "FL": cell_text(9),
            "Lus": cell_text(10),
            "Rap Price": cell_text(11),
            "Quotation Price": cell_text(12),
            "Back (Discount %)": cell_text(13),
            "Lab": cell_text(14),
            "Depth %": cell_text(15),
            "Table": cell_text(16),
            "Dia/LW": cell_text(17),
            "Meas": cell_text(18),
            # add any further report columns here as needed
        }
        records.append(record)

    return pd.DataFrame(records)


def compute_min_max_discount(df: pd.DataFrame, company_name: str) -> dict:
    disc = pd.to_numeric(
        df["Back (Discount %)"].astype(str).str.replace("%", "").str.strip(),
        errors="coerce",
    )
    return {
        "Company": company_name,
        "Min Discount %": disc.min(),
        "Max Discount %": disc.max(),
        "Rows Fetched": len(df),
    }


def run(username: str, password: str, company_name: str, filters: dict, headless: bool = True):
    """
    Full pipeline: login -> filter -> scrape -> summarize.
    Returns (summary_dict, details_dataframe)
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            login(page, username, password)
            apply_filters(page, filters)
            df = scrape_results(page)
        finally:
            browser.close()

    summary = compute_min_max_discount(df, company_name) if not df.empty else {
        "Company": company_name, "Min Discount %": None, "Max Discount %": None, "Rows Fetched": 0
    }
    return summary, df