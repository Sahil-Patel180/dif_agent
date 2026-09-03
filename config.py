"""
config.py — central place for selectors + dropdown option lists.

Rapaport's search page uses custom label/button components tied to hidden
inputs — NOT plain <select> for shape/color/clarity/fluorescence/lab/show-only.
Those are clicked via the label's `for` attribute. Size (carat) and depth%
are real text <input> fields.
"""

import os

LOGIN_URL = "https://trade.rapaport.com/"

# Persistent Chrome profile dir — reused across runs so "remember this
# device 30 days" sticks and OTP isn't re-triggered every time. First run
# must be headless=False so you can complete OTP manually once; the
# device-trust cookie then lives in this folder for later runs.
PROFILE_DIR = os.getenv(
    "RAPAPORT_PROFILE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile"),
)

SELECTORS = {
    "username_field": "#emailUserName",
    "password_field": "#password",
    "login_button": "#btn-login",

    "carat_from_input": "input[id='filter.size.sizeFrom']",
    "carat_to_input": "input[id='filter.size.sizeTo']",

    "report_date_from_input": "input[id='filter.labDateFrom']",
    "report_date_to_input": "input[id='filter.labDateTo']",

    "depth_percent_from": "input[id='filter.depth.depthPercentFrom']",
    "depth_percent_to": "input[id='filter.depth.depthPercentTo']",
    # Depth% lives under the collapsed "Measurements" section — must expand
    # it first or the inputs above aren't interactable yet.
    "measurements_expand_button": "button[class*='collapsible-container__Button']:has-text('MEASUREMENTS')",

    "search_button": "button[type='submit'][form='classicSearchForm']",
    "result_rows": "div[class*='searchResultTable-tableRow']",
    "result_cells": ":scope > div[class*='table-col']",  # direct children only — avoids grabbing nested duplicate divs that also match 'table-col'
    "result_scroll_container": "div[class*='table-ScrollableTable'], div[id='searchResultTable-tableBody']",

    # Report Date / Key to Symbols / Report Comment all live in the
    # expanded row detail panel — click the row, then read these. No PDF
    # open needed (that was the old, much slower approach — plain DOM text
    # reads). Template takes the visible label text and finds its sibling
    # value div.
    "expanded_detail_value": (
        "xpath=//div[contains(@class,'ExpandedDetailItemTitle') and "
        "normalize-space(text())='{label}']/following-sibling::div[1]"
    ),
}


def shape_label(shape_name: str) -> str:
    """e.g. shape_label('Round') -> label[for='filter.shape.shapes.Round']"""
    return f"label[for='filter.shape.shapes.{shape_name}']"


def color_label(letter: str) -> str:
    """e.g. color_label('D') -> label[for='filter.color.D']"""
    return f"label[for='filter.color.{letter}']"


def clarity_label(clarity: str) -> str:
    """e.g. clarity_label('VVS1') -> label[for='undefined.VVS1']
    NOTE: site bug — real 'for' value is 'undefined.<Clarity>', confirmed
    from live DOM, not 'filter.clarity.<Clarity>'."""
    return f"label[for='undefined.{clarity}']"


def fluorescence_label(level: str) -> str:
    """e.g. fluorescence_label('None') -> label[for='filter.fluorescence.None']"""
    return f"label[for='filter.fluorescence.{level}']"


def lab_label(lab_code: str) -> str:
    """e.g. lab_label('IGI') -> label[for='filter.labs.IGI']"""
    return f"label[for='filter.labs.{lab_code}']"


def finish_quick_button(label: str) -> str:
    """e.g. finish_quick_button('3X') -> sets Cut+Polish+Symmetry all at once
    to the same grade in a single click. label in {'3X','EX-','VG+','VG-'}"""
    return f"div[class*='finish__GroupWrapper'] button:has-text('{label}')"


# 'Show Only' toggle buttons — only Primary Suppliers confirmed so far.
# Add more here as their 'for' values get confirmed via DevTools.
SHOW_ONLY_FOR_MAP = {
    "Primary Suppliers": "filter.showOnly.primarySupplierBadge",
}


def show_only_label(option_name: str) -> str:
    suffix = SHOW_ONLY_FOR_MAP.get(option_name)
    if not suffix:
        raise ValueError(f"Unknown Show Only option '{option_name}' — selector not confirmed yet")
    return f"label[for='{suffix}']"


# visual column order in the results grid (from live screenshot header row)
RESULT_COLUMNS = [
    "Seller", "Status", "Rating", "Location", "Shape", "Size", "Color",
    "Shade", "Clarity", "Cut", "Polish", "Symmetry", "Fluorescence", "Lab",
    "%Rap (Back Discount)", "$/Ct", "Total", "Info & Media", "Depth", "Table",
    "Measurements", "Diamond ID", "Diamond Type", "Ratio", "Vendor Stock #",
    "Key to Symbols",
]

# Extra fields only available in the expanded row detail panel (need a
# row click to read) — Report Date, Report Comment. Key to Symbols turned
# out to already be a normal grid column (see RESULT_COLUMNS above), no
# click needed for that one.
EXPANDED_DETAIL_FIELDS = ["Report Date", "Report Comment"]

SHAPE_OPTIONS = ["", "Round", "Pear", "Oval", "Marquise", "Heart", "Radiant",
                  "Princess", "Emerald", "Asscher", "Sq. Emerald"]
GRADE_OPTIONS = ["", "3X", "EX-", "VG+", "VG-"]  # quick Finish presets (Cut+Pol+Sym together)
COLOR_OPTIONS = ["", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]
CLARITY_OPTIONS = ["", "FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2", "I1"]
FLUORESCENCE_OPTIONS = ["", "None", "Very Slight", "Faint / Slight", "Medium", "Strong", "Very Strong"]
LAB_OPTIONS = ["", "GIA", "GIA DOR", "HRD", "IGI", "AGS", "CGL", "DBIOD", "GCAL", "GHI", "GII"]
SHOW_ONLY_OPTIONS = ["", "Primary Suppliers"]

SRK_SEARCH_URL = "https://pure.srk.one/web/search/specific-search"

SRK_FILTER_LABELS = {
    "clarity": "Clarity",
    "colour": "Colour",
    "cut": "Cut",
    "polish": "Polish",
    "symmetry": "Symmetry",
    "fluorescence": "Fluorescence",
    "lab": "Certificate",
    "luster": "Luster",
    "shade": "Shades",
}

SRK_RESULT_COLUMNS = [
    "Sr No.", "Shape", "Carat", "Clarity", "Colour", "Shade", "Cut",
    "Polish", "Symmetry", "Fluorescence", "Luster", "Lab", "Total Depth",
    "SGS Comment", "Discount (Off%)", "Stone ID", "Video Link URL",
    "Key to Symbol", "Lab Comment",
]

# scraped-table-header -> our-output-column
SRK_COLUMN_MAP = {
    "Shape": "Shape",
    "Carat": "Carat",
    "Clarity": "Clarity",
    "Color": "Colour",
    "Shd": "Shade",
    "Cut": "Cut",
    "Pol": "Polish",
    "Sym": "Symmetry",
    "Fluor": "Fluorescence",
    "Lust": "Luster",
    "Cert": "Lab",
    "TD": "Total Depth",
    "SGS Comment": "SGS Comment",
    "Off%": "Discount (Off%)",
    "Key To Symbol": "Key to Symbol",
    "LAB Comments": "Lab Comment",
}