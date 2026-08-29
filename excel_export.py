"""
excel_export.py — build the downloadable Excel report (Summary + Details).
Summary is now a per-company DataFrame (Min/Max Discount%, $/Ct, Total,
row count per seller) — not a single aggregate row.
"""

from io import BytesIO
import pandas as pd


def build_excel(summary_df: pd.DataFrame, df: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        df.to_excel(writer, sheet_name="Details", index=False)
    output.seek(0)
    return output


def save_excel(summary_df: pd.DataFrame, df: pd.DataFrame, path: str):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        df.to_excel(writer, sheet_name="Details", index=False)