"""
excel_export.py — build the downloadable Excel report (Summary + Details).
"""

from io import BytesIO
import pandas as pd


def build_excel(summary: dict, df: pd.DataFrame) -> BytesIO:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Summary", index=False)
        df.to_excel(writer, sheet_name="Details", index=False)
    output.seek(0)
    return output


def save_excel(summary: dict, df: pd.DataFrame, path: str):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Summary", index=False)
        df.to_excel(writer, sheet_name="Details", index=False)