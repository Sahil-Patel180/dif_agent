"""
excel_export.py — build downloadable Excel report (Summary + Details).
Summary sheet gets From/To Date header rows (rows 1-2) above the table
(row 4), matching report layout.
"""
from io import BytesIO
from datetime import date
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
    cols_present = [c for c in mapping if c in df.columns]
    return df[cols_present].rename(columns=mapping)


def _write_summary_with_dates(writer, summary_df, report_date_from: date, report_date_to: date):
    """Rows 1-2: From/To Date. Row 3: blank. Row 4+: table (startrow=3, 0-idx)."""
    ws_name = "Summary"
    summary_out = select_and_rename(summary_df, SUMMARY_COLUMNS)
    summary_out.to_excel(writer, sheet_name=ws_name, index=False, startrow=3)

    ws = writer.sheets[ws_name]
    ws["A1"] = "From Date"
    ws["B1"] = report_date_from.strftime("%d-%m-%Y")
    ws["A2"] = "To Date"
    ws["B2"] = report_date_to.strftime("%d-%m-%Y")


def build_excel(summary_df: pd.DataFrame, df: pd.DataFrame,
                 report_date_from: date, report_date_to: date) -> BytesIO:
    output = BytesIO()
    details_out = select_and_rename(df, DETAILS_COLUMNS)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        _write_summary_with_dates(writer, summary_df, report_date_from, report_date_to)
        details_out.to_excel(writer, sheet_name="Details", index=False)
    output.seek(0)
    return output


def save_excel(summary_df: pd.DataFrame, df: pd.DataFrame, path: str,
               report_date_from: date, report_date_to: date):
    details_out = select_and_rename(df, DETAILS_COLUMNS)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _write_summary_with_dates(writer, summary_df, report_date_from, report_date_to)
        details_out.to_excel(writer, sheet_name="Details", index=False)