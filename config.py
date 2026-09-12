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
SRK_PROFILE_DIR = os.getenv(
    "SRK_PROFILE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile_srk"),
)

# Bulk-run checkpoints (crash-safe incremental save + resume) land here —
# one subfolder per platform, see checkpoint.py.
CHECKPOINT_DIR = os.getenv(
    "AGENT_CHECKPOINT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoints"),
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


def find_range(value: float, ranges: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Find the bucket whose From or To exactly equals value; else the
    bucket that CONTAINS value. Used to auto-settle the other side of a
    From/To pair once the user types one number (carat or depth%)."""
    for lo, hi in ranges:
        if value in (lo, hi):
            return (lo, hi)
    for lo, hi in ranges:
        if lo <= value <= hi:
            return (lo, hi)
    return None


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

SHAPE_OPTIONS = ["Round", "Pear", "Oval", "Marquise", "Heart", "Radiant",
                  "Princess", "Emerald", "Asscher", "Sq. Emerald"]
GRADE_OPTIONS = ["3X", "EX-", "VG+", "VG-"]
# Full white-colour scale. D-M are painted immediately; N-Z only mount
# after the "More" button under the colour picker is clicked — see
# COLOR_MORE_BUTTON / COLOR_BEHIND_MORE below.
COLOR_OPTIONS = ["D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
                  "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

# Confirmed from live DOM: the colour picker only renders D..M until this
# button is pressed, so label[for='filter.color.N'] and everything after it
# simply doesn't exist in the DOM yet and a click on it times out. Scoped
# to the colour section — clarity has a button with the same class.
COLOR_MORE_BUTTON = ("div[class*='color__StyledFromToPicker'] "
                     "button[class*='box-picker-from-to__More']")
COLOR_BEHIND_MORE = ["N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

CLARITY_OPTIONS = ["FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2",
                    "SI3", "I1", "I2", "I3"]
FLUORESCENCE_OPTIONS = ["None", "Very Slight", "Faint / Slight", "Medium", "Strong", "Very Strong"]
LAB_OPTIONS = ["GIA", "GIA DOR", "HRD", "IGI", "AGS", "CGL", "DBIOD", "GCAL",
                "GHI", "GII", "GSI", "NGTC", "PGS", "RAP", "RDC", "SGL"]
SHOW_ONLY_OPTIONS = ["Primary Suppliers"]

# Confirmed exact from live DOM (checkbox input under clarity section):
# <input id="filter.includedShade.noBGM" name="filter.includedShade.noBGM" type="checkbox" ...>
NO_BGM_LABEL = "label[for='filter.includedShade.noBGM']"

# Size ranges — confirmed from image. Seeds the carat From/To auto-settle
# in app.py; user still types a number, this just supplies the buckets.
CARAT_RANGES = [
    (1.00, 1.00), (1.01, 1.19), (1.20, 1.24), (1.25, 1.29), (1.30, 1.34),
    (1.35, 1.39), (1.40, 1.44), (1.45, 1.49), (1.50, 1.50), (1.51, 1.69),
    (1.70, 1.79), (1.80, 1.89), (1.90, 1.95), (1.96, 1.99), (2.00, 2.00),
    (2.01, 2.24), (2.25, 2.49), (2.50, 2.59), (2.60, 2.69), (2.70, 2.79),
    (2.80, 2.89), (2.90, 2.99), (3.00, 3.00), (3.01, 3.49), (3.50, 3.69),
    (3.70, 3.89), (3.90, 3.99), (4.00, 4.00), (4.01, 4.49), (4.50, 4.69),
    (4.70, 4.79), (4.80, 4.89), (4.90, 4.99), (5.00, 5.00), (5.01, 5.24),
    (5.25, 5.49), (5.50, 5.69), (5.70, 5.89), (5.85, 5.99),
]

# Total depth% ranges — confirmed from image (last two rows overlap:
# 5.70–5.89 then 5.85–5.99 — transcribed exactly as shown, your call to fix
# if that's a typo on the source sheet). Seeds the depth From/To auto-settle.
DEPTH_RANGES = [
    (58.0, 58.9), (59.0, 59.9), (60.0, 60.9), (61.0, 61.9), (62.0, 62.9),
    (63.0, 63.9), (64.0, 64.9), (65.0, 65.9), (66.0, 66.9),
]

SRK_LOGIN_URL = "https://pure.srk.one/login"
SRK_ROOT_URL = "https://pure.srk.one/"
# Confirmed 09-Sep-2026 from live DOM — actual sidebar nav route is
# /web/search, not /web/search/specific-search like this constant assumed
# before. Kept as the canonical "we ended up on the search page" URL.
SRK_SEARCH_URL = "https://pure.srk.one/web/search"

# Confirmed exact from live DOM (sidebar <a> element):
# <a ... router-link="search" href="/web/search" title="SPECIFIC SEARCH">
SRK_SIDEBAR_SEARCH_NAV = "a[href='/web/search']"

# SRK Colour / Clarity as ORDERED scales, so the UI can offer a From/To
# pair (like Rapaport) instead of one single value. SRK's own page has no
# range control — these are plain multi-select chips — so the app expands
# the chosen range into every value between the two ends and clicks each
# chip. Order below IS the grading order; don't re-sort it.
# Chip text must match the site's aria-label exactly.
SRK_COLOUR_SCALE = ["D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N-Z"]
SRK_CLARITY_SCALE = ["FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2",
                      "SI3", "I1", "I2", "I3"]

# Sentinel shown at the top of both From and To pickers. "All" on either
# side means "don't filter on this at all" — SRK returns everything when no
# chip is selected, so the correct action is to click nothing.
SRK_RANGE_ALL = "All"


def expand_scale_range(scale: list[str], from_val: str, to_val: str) -> list[str]:
    """Turn a From/To pair into the list of chips to click.

    'All' (or blank) on either end -> [] meaning leave the filter untouched.
    Reversed input (From=SI2, To=VVS1) is swapped rather than returning an
    empty list, so a mis-ordered pick still does the sensible thing."""
    if not from_val or not to_val:
        return []
    if from_val == SRK_RANGE_ALL or to_val == SRK_RANGE_ALL:
        return []
    if from_val not in scale or to_val not in scale:
        return []
    i, j = scale.index(from_val), scale.index(to_val)
    if i > j:
        i, j = j, i
    return scale[i:j + 1]


SRK_FILTER_LABELS = {    "clarity": "Clarity",
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