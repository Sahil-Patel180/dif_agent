"""
config.py — central place for selectors + dropdown option lists.

Rapaport's search page uses custom label/button components tied to hidden
inputs — NOT plain <select> for shape/size/color/clarity/fluorescence/lab.
Those are clicked via the label's `for` attribute. Only a few fields
(depth%, carat) are real text <input>.
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
    # --- confirmed ---
    "username_field": "#emailUserName",
    "password_field": "#password",
    "login_button": "#btn-login",

    "depth_percent_from": "input[id='filter.depth.depthPercentFrom']",
    "depth_percent_to": "input[id='filter.depth.depthPercentTo']",

    "search_button": "button[type='submit'][form='classicSearchForm']",
    "result_rows": "div[class*='searchResultTable-tableRow']",
    "result_cells": "div[class*='table-col']",  # direct children of a row, in visual column order

    "company_name": "div[class*='seller-col-new__CompanyNameRow']",
    "cert_link": "a[href*='certificateviewer']",

    # --- still TODO: verify via DevTools ---
    "carat_min_input": "#caratMin",          # TODO: verify — text input in Size row
    "carat_max_input": "#caratMax",          # TODO: verify
}


def shape_label(shape_name: str) -> str:
    """e.g. shape_label('Round') -> label[for='filter.shape.shapes.Round']"""
    return f"label[for='filter.shape.shapes.{shape_name}']"


def size_range_label(range_text: str) -> str:
    """e.g. size_range_label('0.30 - 0.39') -> matches preset size button"""
    return f"label[for='{range_text}']"


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


# visual column order in the results grid (from live screenshot header row)
RESULT_COLUMNS = [
    "Seller", "Status", "Rating", "Location", "Shape", "Size", "Color",
    "Shade", "Clarity", "Cut", "Polish", "Symmetry", "Fluorescence", "Lab",
    "%Rap (Back Discount)", "$/Ct", "Total", "Depth", "Table",
    "Measurements", "Diamond Lot #", "Diamond Stock #",
]

SHAPE_OPTIONS = ["", "Round", "Pear", "Oval", "Marquise", "Heart", "Radiant",
                  "Princess", "Emerald", "Asscher", "Sq. Emerald"]
GRADE_OPTIONS = ["", "3X", "EX-", "VG+", "VG-"]  # quick Finish presets (Cut+Pol+Sym together)
COLOR_OPTIONS = ["", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]
CLARITY_OPTIONS = ["", "FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2", "I1"]
FLUORESCENCE_OPTIONS = ["", "None", "Very Slight", "Faint / Slight", "Medium", "Strong", "Very Strong"]
LAB_OPTIONS = ["", "GIA", "GIA DOR", "HRD", "IGI", "AGS", "CGL", "DBIOD", "GCAL", "GHI", "GII"]