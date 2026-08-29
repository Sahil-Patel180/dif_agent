"""
config.py — central place for selectors + dropdown option lists.
Edit selectors here once verified via DevTools; scraper.py imports from here.
"""

LOGIN_URL = "https://trade.rapaport.com/"

SELECTORS = {
    "username_field": "#emailUserName",          # TODO: verify
    "password_field": "#password",          # TODO: verify
    "login_button": "btn-login",  # TODO: verify

    "shape_select": "#shapeSelect",          # TODO: verify
    "carat_min_input": "#caratMin",          # TODO: verify
    "carat_max_input": "#caratMax",          # TODO: verify
    "color_min_select": "#colorMin",         # TODO: verify
    "color_max_select": "#colorMax",         # TODO: verify
    "clarity_min_select": "#claritySelectMin",  # TODO: verify
    "clarity_max_select": "#claritySelectMax",  # TODO: verify
    "cut_select": "#cutSelect",              # TODO: verify
    "polish_select": "#polishSelect",        # TODO: verify
    "symmetry_select": "#symmetrySelect",    # TODO: verify
    "fluorescence_select": "#fluorescenceSelect",  # TODO: verify
    "search_button": "button#searchBtn",     # TODO: verify

    "result_rows": "table#resultsTable tbody tr",  # TODO: verify
}

# column index order inside each result row — fix once you count real table
RESULT_COLUMNS = [
    "Packet No.", "Shape", "Cts", "Col", "Cla", "Cut", "Pol", "Sym", "FL",
    "Lus", "Rap Price", "Quotation Price", "Back (Discount %)", "Lab",
    "Depth %", "Table", "Dia/LW", "Meas",
]

SHAPE_OPTIONS = ["", "RD", "PR", "EM", "OV", "MQ", "PS", "RA", "CU", "AS", "HS"]
GRADE_OPTIONS = ["", "EX", "VG", "GD", "FR", "PR"]
COLOR_OPTIONS = ["", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]
CLARITY_OPTIONS = ["", "FL", "IF", "VVS1", "VVS2", "VS1", "VS2", "SI1", "SI2", "I1"]
FLUORESCENCE_OPTIONS = ["", "NONE", "FA", "MED", "STG", "VST"]