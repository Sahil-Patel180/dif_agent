"""
excel_export.py — build downloadable Excel report (Summary + Details).
Selects + renames columns to final report format before write.
"""
from io import BytesIO
import pandas as pd

SUMMARY_COLUMNS = {
    "Company": "Company",
    "Location": "Location",
    "Vendor Stock #": "Vendor stock #",
    "Max Discount %": "Max discount",
    "Report Date": "Report date",
    "Key to Symbols": "Key to symbols",
}

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
    """Keep only cols in mapping (skip missing), rename to final label, mapping order kept."""
    cols_present = [c for c in mapping if c in df.columns]
    return df[cols_present].rename(columns=mapping)


def build_excel(summary_df: pd.DataFrame, df: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    summary_out = select_and_rename(summary_df, SUMMARY_COLUMNS)
    details_out = select_and_rename(df, DETAILS_COLUMNS)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_out.to_excel(writer, sheet_name="Summary", index=False)
        details_out.to_excel(writer, sheet_name="Details", index=False)
    output.seek(0)
    return output


def save_excel(summary_df: pd.DataFrame, df: pd.DataFrame, path: str):
    summary_out = select_and_rename(summary_df, SUMMARY_COLUMNS)
    details_out = select_and_rename(df, DETAILS_COLUMNS)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary_out.to_excel(writer, sheet_name="Summary", index=False)
        details_out.to_excel(writer, sheet_name="Details", index=False)