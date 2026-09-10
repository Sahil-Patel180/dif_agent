"""
scraper.py — Rapaport trade site automation.
Uses label-click pattern for shape/size/color/clarity/fluorescence/lab
(these are custom components, not <select>). See config.py for selector
templates. Company name + report date require an extra click+PDF-open
per stone — set include_report_date=False to skip that for speed.

WINDOWS NOTE: Streamlit runs your script in a worker thread that doesn't
inherit Python's default ProactorEventLoop (needed on Windows for
Playwright to spawn the browser subprocess). Running Playwright directly
there throws NotImplementedError. Fix: run it inside a fresh thread where
we explicitly set the Proactor event loop policy first — see run().

CHECKPOINTING: Rapaport search is a single continuous scrape (not
row-by-row bulk like SRK), so crash-safety works per SCROLL BATCH instead
of per input row — every batch of newly-found unique rows gets appended
to a checkpoint CSV (fsynced) the instant it's collected, see
collect_all_rows(). run_id is derived from the filter set itself (same
search = same run_id), so re-running the same search after a crash
auto-resumes: already-checkpointed rows get preloaded into `seen` and
skipped on re-scroll instead of re-processed.
"""

import os
import re
import sys
import json
import time
import asyncio
import threading
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import sync_playwright
import pandas as pd

from config import (
    LOGIN_URL, SELECTORS, RESULT_COLUMNS, PROFILE_DIR, NO_BGM_LABEL, CHECKPOINT_DIR,
    shape_label, color_label, clarity_label,
    fluorescence_label, lab_label, finish_quick_button, show_only_label,
)
from checkpoint import (
    file_hash, paths_for, append_checkpoint, write_progress, load_progress,
    load_checkpoint_df,
)


def login(page, username: str, password: str):
    page.goto(LOGIN_URL)
    page.wait_for_load_state("domcontentloaded")

    # Saved profile already trusted -> Rapaport auto-redirects past login.
    # Confirm by waiting for the Diamonds nav link (dashboard marker)
    # instead of networkidle — chat widget/ad banners keep network busy
    # forever, so networkidle can hang indefinitely and never fire.
    if page.query_selector(SELECTORS["username_field"]) is None:
        page.wait_for_selector("a[href='#/search/rn']", timeout=60000)
        return

    page.fill(SELECTORS["username_field"], username)
    page.fill(SELECTORS["password_field"], password)
    page.click(SELECTORS["login_button"])

    # If an OTP screen appears (new device), give time for manual entry —
    # only happens on first run per profile. Waits up to 2 minutes for the
    # Diamonds nav link to show up, meaning login (and OTP, if any) is done.
    page.wait_for_selector("a[href='#/search/rn']", timeout=120000)


def goto_search_page(page):
    """Login lands on Dashboard, not the filters page. A raw page.goto()
    hash-jump can skip the SPA's router init — click the actual nav link
    instead, same as a real user would, then wait for Shape section to
    render before any filter clicks are attempted. Uses page.click()
    (not query_selector+click) so Playwright re-locates the element fresh
    right before clicking — React re-renders can detach a grabbed handle."""
    try:
        page.click("a[href='#/search/rn']", timeout=15000)
    except Exception:
        page.goto(f"{LOGIN_URL}#/search/rn")
    page.wait_for_selector(shape_label("Round"), timeout=90000)


def expand_measurements_if_needed(page):
    """Depth% inputs live under the collapsed 'Measurements' section —
    only click to expand if they're not already visible/interactable."""
    if page.is_visible(SELECTORS["depth_percent_from"]):
        return
    page.click(SELECTORS["measurements_expand_button"])
    page.wait_for_selector(SELECTORS["depth_percent_from"], timeout=15000)


def apply_filters(page, filters: dict):
    """
    Applied in this exact order: Shape, Size, Color, Clarity, No BGM,
    Finish, Fluorescence, Grading Report, Show Only, Depth% (Measurements).

    filters dict keys expected:
      shape: str (e.g. 'Round')
      carat_min, carat_max: float — real text inputs now confirmed
      color_min, color_max: str single letters (e.g. 'H')
      clarity_min, clarity_max: str (e.g. 'VVS1')
      finish: str one of '3X','EX-','VG+','VG-' — sets Cut+Pol+Sym together
      fluorescence: str (e.g. 'None')
      lab: str (e.g. 'IGI')
      report_date_from, report_date_to: str 'MM/DD/YYYY' — Grading Report date range
      show_only: str (e.g. 'Primary Suppliers')
      depth_min, depth_max: float or None — optional depth% range
    """

    # 1. Shape
    if filters.get("shape"):
        page.click(shape_label(filters["shape"]))

    # 2. Size (carat)
    if filters.get("carat_min") is not None:
        page.fill(SELECTORS["carat_from_input"], str(filters["carat_min"]))
    if filters.get("carat_max") is not None:
        page.fill(SELECTORS["carat_to_input"], str(filters["carat_max"]))

    # 3. Color
    if filters.get("color_min"):
        page.click(color_label(filters["color_min"]))
    if filters.get("color_max") and filters["color_max"] != filters.get("color_min"):
        page.click(color_label(filters["color_max"]))

    # 4. Clarity
    if filters.get("clarity_min"):
        page.click(clarity_label(filters["clarity_min"]))
    if filters.get("clarity_max") and filters["clarity_max"] != filters.get("clarity_min"):
        page.click(clarity_label(filters["clarity_max"]))

    # 4b. No BGM — always forced on, not user-toggleable
    page.click(NO_BGM_LABEL)

    # 5. Finish (Cut+Polish+Symmetry quick preset)
    if filters.get("finish"):
        page.click(finish_quick_button(filters["finish"]))

    # 6. Fluorescence
    if filters.get("fluorescence"):
        page.click(fluorescence_label(filters["fluorescence"]))

    # 7. Grading Report (Lab)
    if filters.get("lab"):
        page.click(lab_label(filters["lab"]))

    # 7b. Report Date range (also under Grading Report section)
    # Real <input type="text"> (react-datepicker) — fill directly with
    # MM/DD/YYYY text, then Escape to close any calendar popup it opens.
    if filters.get("report_date_from"):
        page.fill(SELECTORS["report_date_from_input"], filters["report_date_from"])
        page.keyboard.press("Escape")
    if filters.get("report_date_to"):
        page.fill(SELECTORS["report_date_to_input"], filters["report_date_to"])
        page.keyboard.press("Escape")

    # 8. Show Only
    if filters.get("show_only"):
        page.click(show_only_label(filters["show_only"]))

    # 9. Depth% (under Measurements — expand first). Optional — only
    # touched when at least one side is set.
    if filters.get("depth_min") is not None or filters.get("depth_max") is not None:
        expand_measurements_if_needed(page)
        if filters.get("depth_min") is not None:
            page.fill(SELECTORS["depth_percent_from"], str(filters["depth_min"]))
        if filters.get("depth_max") is not None:
            page.fill(SELECTORS["depth_percent_to"], str(filters["depth_max"]))

    page.click(SELECTORS["search_button"])
    page.wait_for_selector(SELECTORS["result_rows"], timeout=60000)


def get_total_result_count(page) -> int | None:
    """Reads the '312 Diamonds' style heading at the top of results to know
    how many rows we're aiming to load. Returns None if not found (falls
    back to stall-detection only in load_all_result_rows)."""
    try:
        text = page.locator("text=/\\d+\\s+Diamonds?/i").first.inner_text(timeout=5000)
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else None
    except Exception:
        return None


def _extract_row_record(row) -> dict | None:
    """Pulls one row's cell text into a dict keyed by RESULT_COLUMNS."""
    cells = row.query_selector_all(SELECTORS["result_cells"])
    if not cells:
        return None

    def cell_text(j):
        return cells[j].inner_text().strip() if j < len(cells) else None

    record = {col: cell_text(j) for j, col in enumerate(RESULT_COLUMNS)}
    record["Company"] = parse_company_from_seller(record.get("Seller"))
    return record


def _row_key(record: dict) -> str:
    """Unique key for de-duping across scroll steps. Prefers the real
    Diamond Lot #/Stock #, falls back to a composite of visible fields
    if those are blank for some reason."""
    key = record.get("Diamond Lot #") or record.get("Diamond Stock #")
    if key:
        return str(key)
    return "|".join(str(record.get(k)) for k in [
        "Seller", "Size", "Color", "Clarity", "%Rap (Back Discount)", "$/Ct",
    ])


def collect_all_rows(page, context, expected_total: int | None = None,
                      include_report_date: bool = False, max_iterations: int = 400,
                      checkpoint_csv_path: str = None, checkpoint_progress_path: str = None,
                      run_id: str = None, resume: bool = True):
    """
    This grid is VIRTUALIZED — rows scrolled past get unmounted from the
    DOM (confirmed live: row count fluctuates 33-58 while scrolling instead
    of growing monotonically). A single 'scroll everything then scrape'
    pass can't work here — earlier rows vanish before we reach them.

    Instead: scrape whatever's currently in the DOM at EVERY scroll step,
    dedupe by unique key, and keep going until the unique count hits
    expected_total or stalls (no new uniques for several rounds).

    CRASH-SAFETY: each scroll batch's newly-found unique rows are appended
    to checkpoint_csv_path (fsynced) the instant they're collected — see
    checkpoint.py. 'Input Row' column in that CSV holds the scroll
    iteration number here, not a real input row (this is single-pass, not
    bulk-row like SRK). On resume, previously-checkpointed rows are
    preloaded into `seen` so re-scrolling from the top just skips
    duplicates instead of re-processing them.
    """
    seen: dict[str, dict] = {}

    if resume and checkpoint_csv_path and os.path.exists(checkpoint_csv_path):
        existing_df = load_checkpoint_df(checkpoint_csv_path)
        for _, r in existing_df.iterrows():
            record = r.to_dict()
            seen[_row_key(record)] = record
        if seen:
            print(f"[collect_all_rows] resumed {len(seen)} rows from checkpoint ({checkpoint_csv_path})")

    stall = 0

    for i in range(max_iterations):
        rows = page.query_selector_all(SELECTORS["result_rows"])
        new_records = []

        for row_index, row in enumerate(rows):
            record = _extract_row_record(row)
            if not record:
                continue
            key = _row_key(record)
            if key in seen:
                continue

            if include_report_date:
                try:
                    # Re-query fresh right before clicking — clicking an
                    # earlier row in THIS SAME loop re-renders the grid
                    # (expand animation), detaching handles for rows after
                    # it. Reusing the captured 'row' here was silently
                    # failing to actually click (stale handle).
                    fresh_rows = page.query_selector_all(SELECTORS["result_rows"])
                    if row_index < len(fresh_rows):
                        target = fresh_rows[row_index]
                        target.click()
                        page.wait_for_selector(
                            SELECTORS["expanded_detail_value"].format(label="Report Date"),
                            timeout=8000,
                        )
                        record["Report Date"] = get_expanded_detail(page, "Report Date")
                        record["Report Comment"] = get_expanded_detail(page, "Report Comment")

                        # collapse it again right away — leaving rows
                        # expanded means multiple 'Report Date' panels sit
                        # in the DOM at once, so the next lookup can grab
                        # the WRONG (already-open) row's value, and the
                        # extra panel elements shift indices for rows
                        # after this one. One row open at a time only.
                        target.click()
                        page.wait_for_timeout(300)
                except Exception:
                    record["Report Date"] = None
                    record["Report Comment"] = None

            seen[key] = record
            new_records.append(record)

        if new_records:
            new_df = pd.DataFrame(new_records)
            if checkpoint_csv_path:
                append_checkpoint(checkpoint_csv_path, new_df, i)
            if checkpoint_progress_path and run_id:
                write_progress(checkpoint_progress_path, len(seen), run_id)

        print(f"[collect_all_rows] iteration {i}: {len(seen)} unique rows collected"
              + (f" / {expected_total} expected" if expected_total else "")
              + f" (+{len(new_records)} this round, checkpointed)")

        if expected_total and len(seen) >= expected_total:
            break
        if not new_records:
            stall += 1
            if stall >= 15:
                print("[collect_all_rows] stalled — no new unique rows found, stopping")
                break
        else:
            stall = 0

        if rows:
            try:
                rows[-1].scroll_into_view_if_needed(timeout=5000)
            except Exception:
                pass

        container = page.query_selector(SELECTORS["result_scroll_container"])
        if container:
            try:
                # overscroll past current bottom each time, not just to
                # current scrollHeight — forces a real scroll delta even
                # when already near the bottom, which is what actually
                # triggers the next batch fetch
                page.evaluate("el => el.scrollTop = el.scrollHeight + 2000", container)
            except Exception:
                pass

        page.mouse.move(700, 600)
        page.mouse.wheel(0, 2500)

        # give the next batch time to actually fetch + render — scales up
        # the longer we've been stalled, since it "takes a moment" per the
        # site's own behavior, not an instant response
        wait_ms = 900 + (stall * 700)
        page.wait_for_timeout(min(wait_ms, 6000))

    return list(seen.values())


def parse_company_from_seller(seller_text: str | None) -> str | None:
    """Seller cell text is like 'SK\\nSKRISHNA' — 2-letter code + company
    name on the next line. No row-click needed, it's already there."""
    if not seller_text:
        return None
    lines = [l.strip() for l in seller_text.split("\n") if l.strip()]
    return lines[-1] if lines else seller_text.strip()


def get_expanded_detail(page, label: str) -> str | None:
    """Reads a field from the expanded row detail panel by its visible
    label text (e.g. 'Report Date', 'Key to Symbols', 'Report Comment') —
    plain DOM text/title read, confirmed live, no PDF open needed. Caller
    must have already clicked the row to expand it."""
    try:
        selector = SELECTORS["expanded_detail_value"].format(label=label)
        el = page.query_selector(selector)
        if not el:
            return None
        return el.get_attribute("title") or el.inner_text().strip()
    except Exception:
        return None


def scrape_results(page, context, include_report_date: bool = False,
                    checkpoint_csv_path: str = None, checkpoint_progress_path: str = None,
                    run_id: str = None, resume: bool = True) -> pd.DataFrame:
    """
    Scrapes the (virtualized) results grid via incremental scroll+collect —
    see collect_all_rows() for why a single-pass scrape can't work here,
    and for checkpoint/resume behavior.
    """
    expected_total = get_total_result_count(page)
    records = collect_all_rows(
        page, context, expected_total=expected_total, include_report_date=include_report_date,
        checkpoint_csv_path=checkpoint_csv_path, checkpoint_progress_path=checkpoint_progress_path,
        run_id=run_id, resume=resume,
    )
    return pd.DataFrame(records)


def make_run_id(filters: dict) -> str:
    """Deterministic run_id from the filter set itself — same search =
    same run_id = resume auto-matches. Reuses checkpoint.py's file_hash()
    on the JSON bytes instead of a separate hashlib import."""
    payload = json.dumps(filters, sort_keys=True, default=str).encode()
    return file_hash(payload)


def run(username: str, password: str, company_name: str, filters: dict,
        headless: bool = True, include_report_date: bool = False, resume: bool = True):
    """
    Full pipeline: login -> filter -> scrape (all pages).

    Runs inside a dedicated thread with the Proactor event loop policy set
    explicitly (Windows fix — see module docstring). Safe no-op on
    macOS/Linux.

    Returns (df, checkpoint_csv_path, checkpoint_progress_path) — mirrors
    srk_scraper.run_bulk()'s return shape. Caller decides when it's safe
    to checkpoint.clear_checkpoint(csv_path, progress_path), e.g. only
    after the Excel report was built successfully.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_impl, username, password, company_name,
                                  filters, headless, include_report_date, resume)
        return future.result()


def _run_impl(username: str, password: str, company_name: str, filters: dict,
              headless: bool, include_report_date: bool, resume: bool):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    run_id = make_run_id(filters)
    checkpoint_dir = os.path.join(CHECKPOINT_DIR, "rapaport")
    csv_path, progress_path = paths_for(checkpoint_dir, run_id)

    start_time = time.perf_counter()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",   # use real installed Chrome, not bundled Chromium
            headless=headless,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(90000)  # 90s for every action, not just the 30s default
        try:
            login(page, username, password)
            goto_search_page(page)
            apply_filters(page, filters)
            df = scrape_results(
                page, context, include_report_date=include_report_date,
                checkpoint_csv_path=csv_path, checkpoint_progress_path=progress_path,
                run_id=run_id, resume=resume,
            )
        finally:
            context.close()

    total_seconds = time.perf_counter() - start_time
    print(
        f"[rapaport] TOTAL TIME: "
        f"{total_seconds:.2f} seconds "
        f"({total_seconds / 60:.2f} minutes)"
    )

    return df, csv_path, progress_path