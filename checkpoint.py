"""
checkpoint.py — crash-safe incremental save + resume for bulk runs.

Problem this solves: bulk runs (SRK today, Rapaport next) used to hold every
scraped row only in memory and write the Excel report once at the very end.
Power loss / crash / force-quit mid-run at row 3000 of 4000 = everything
lost. Fix: append each row's result to a CSV on disk (fsynced) the moment
it's scraped, plus a small progress marker — a restarted run then skips
everything already done instead of starting over.
"""

import os
import json
import hashlib
import pandas as pd


def file_hash(data: bytes) -> str:
    """Stable short hash of the uploaded bulk-input file's raw bytes — used
    to make sure a 'resume' only kicks in for the SAME input file, not a
    different one that happens to reuse the checkpoint dir."""
    return hashlib.sha256(data).hexdigest()[:16]


def paths_for(checkpoint_dir: str, run_id: str):
    os.makedirs(checkpoint_dir, exist_ok=True)
    return (
        os.path.join(checkpoint_dir, f"{run_id}_results.csv"),
        os.path.join(checkpoint_dir, f"{run_id}_progress.json"),
    )


def append_checkpoint(csv_path: str, df: pd.DataFrame, input_row: int):
    """Append one row's results to disk immediately, then fsync — data is
    safe on disk before this call returns, survives power loss right after."""
    out = df.copy()
    out.insert(0, "Input Row", input_row)
    header = not os.path.exists(csv_path)
    out.to_csv(csv_path, mode="a", header=header, index=False)
    try:
        fd = os.open(csv_path, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except Exception:
        pass  # best-effort fsync — some filesystems/mounts don't support it, csv write above already landed


def write_progress(progress_path: str, last_row: int, run_id: str):
    """Atomic write (tmp file + os.replace) — never leaves a half-written,
    corrupt progress.json behind if power cuts mid-write."""
    tmp = progress_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"last_completed_row": last_row, "run_id": run_id}, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, progress_path)


def load_progress(progress_path: str, run_id: str) -> int:
    """Returns last_completed_row for THIS run_id, or 0 if no match
    (different input file, or genuinely a fresh run)."""
    if not os.path.exists(progress_path):
        return 0
    try:
        with open(progress_path) as f:
            data = json.load(f)
    except Exception:
        return 0
    if data.get("run_id") != run_id:
        return 0
    return int(data.get("last_completed_row", 0))


def load_checkpoint_df(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def clear_checkpoint(csv_path: str, progress_path: str):
    """Call once a run finished fully and its Excel report was built
    successfully — starts the NEXT run of this same input file clean
    instead of resuming a finished run forever."""
    for p in (csv_path, progress_path):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass