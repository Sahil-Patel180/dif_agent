"""
scraper.py — Rapaport trade site automation.
Selectors + column order now live in config.py — edit there, not here.
"""

from playwright.sync_api import sync_playwright
import pandas as pd

from config import LOGIN_URL, SELECTORS, RESULT_COLUMNS


def login(page, username: str, password: str):
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")

    page.fill(SELECTORS["username_field"], username)
    page.fill(SELECTORS["password_field"], password)
    page.click(SELECTORS["login_button"])

    page.wait_for_load_state("networkidle")


def apply_filters(page, filters: dict):
    """
    filters dict keys expected (matches your sheet's green columns):
    shape, carat_min, carat_max, color_min, color_max,
    clarity_min, clarity_max, cut, polish, symmetry, fluorescence
    """

    if filters.get("shape"):
        page.select_option(SELECTORS["shape_select"], filters["shape"])

    if filters.get("carat_min") is not None:
        page.fill(SELECTORS["carat_min_input"], str(filters["carat_min"]))
    if filters.get("carat_max") is not None:
        page.fill(SELECTORS["carat_max_input"], str(filters["carat_max"]))

    if filters.get("color_min"):
        page.select_option(SELECTORS["color_min_select"], filters["color_min"])
    if filters.get("color_max"):
        page.select_option(SELECTORS["color_max_select"], filters["color_max"])

    if filters.get("clarity_min"):
        page.select_option(SELECTORS["clarity_min_select"], filters["clarity_min"])
    if filters.get("clarity_max"):
        page.select_option(SELECTORS["clarity_max_select"], filters["clarity_max"])

    if filters.get("cut"):
        page.select_option(SELECTORS["cut_select"], filters["cut"])
    if filters.get("polish"):
        page.select_option(SELECTORS["polish_select"], filters["polish"])
    if filters.get("symmetry"):
        page.select_option(SELECTORS["symmetry_select"], filters["symmetry"])
    if filters.get("fluorescence"):
        page.select_option(SELECTORS["fluorescence_select"], filters["fluorescence"])

    page.click(SELECTORS["search_button"])
    page.wait_for_load_state("networkidle")


def scrape_results(page) -> pd.DataFrame:
    """
    Scrapes result grid using RESULT_COLUMNS order from config.py.
    Fix that list once you count Rapaport's real table columns.
    """
    rows = page.query_selector_all(SELECTORS["result_rows"])

    records = []
    for row in rows:
        cells = row.query_selector_all("td")
        if not cells:
            continue

        def cell_text(i):
            return cells[i].inner_text().strip() if i < len(cells) else None

        record = {col: cell_text(i) for i, col in enumerate(RESULT_COLUMNS)}
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