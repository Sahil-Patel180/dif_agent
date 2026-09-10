"""
excel_export.py — build downloadable Excel report (Details only, no Summary sheet).
"""
from io import BytesIO
import pandas as pd

DETAILS_COLUMNS = {
    "Company": "Company",
    "Location": "Location",
    "Shape": "Shape",
    "Size": "Size",
    "Color": "Color",
    "Clarity": "Clarity",
    "Cut": "Cut",
    "Polish": "Polish",
    "Symmetry": "Symmetry",
    "Fluorescence": "Fluorescence",
    "Lab": "Lab",
    "%Rap (Back Discount)": "%RAP",
    "Depth": "Depth",
    "Table": "Table",
    "Measurements": "Measurements",
    "Ratio": "Ratio",
    "Vendor Stock #": "Vendor stock #",
    "Key to Symbols": "Key to symbols",
    "Report Date": "Report date",
    "Report Comment": "Report comment",
}


def select_and_rename(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    cols_present = [c for c in mapping if c in df.columns]
    return df[cols_present].rename(columns=mapping)


def _add_fixed_columns(details_out: pd.DataFrame) -> pd.DataFrame:
    """Shade & Luster aren't scraped from Rapaport — fixed constant values per spec."""
    details_out["Shade"] = "None"
    details_out["Luster"] = "Ex"
    return details_out


def build_excel(df: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    details_out = _add_fixed_columns(select_and_rename(df, DETAILS_COLUMNS))
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        details_out.to_excel(writer, sheet_name="Details", index=False)
    output.seek(0)
    return output


def save_excel(df: pd.DataFrame, path: str):
    details_out = _add_fixed_columns(select_and_rename(df, DETAILS_COLUMNS))
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        details_out.to_excel(writer, sheet_name="Details", index=False)