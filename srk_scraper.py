import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd

from config import SRK_SEARCH_URL, SRK_FILTER_LABELS, SRK_COLUMN_MAP, SRK_RESULT_COLUMNS


def click_option_near_label(driver, label_text, value, timeout=10):
    """Find nearest element after a section label whose aria-label == value, click it."""
    xpath = (
        f"//*[self::div or self::b or self::strong or self::span]"
        f"[normalize-space(text())='{label_text}']"
        f"/following::div[@aria-label='{value}'][1]"
    )
    WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    ).click()


def click_option_by_box_id(driver, box_id_prefix, value, timeout=10):
    """Cut/Polish/Symmetry live in one shared 'Finishing' panel — confirmed real DOM ids
    are {prefix}LabelBox / {prefix}ComponentBox (e.g. cutComponentBox). Scoping the click
    to that box id avoids grabbing the wrong sibling's chip via document-order 'following::'.
    """
    xpath = f"//div[@id='{box_id_prefix}ComponentBox']//div[@aria-label='{value}']"
    WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    ).click()


# keys here confirmed/likely to share the Finishing sub-panel DOM pattern (LabelBox/ComponentBox by id)
# cut confirmed from live DOM inspection; polish/symmetry assumed same naming convention — verify if they still fail
# cut/polish/symmetry: wrapper ComponentBox id confirmed reliable
SRK_BOX_ID_KEYS = {"cut": "cut", "polish": "polish", "symmetry": "symmetry"}


def click_option_by_selectbutton_id(driver, selectbutton_id, value, timeout=10):
    """Luster/Shades: outer wrapper id is buggy on the site (leftover 'cutshingComponentBox'
    id reused from Cut), but the inner <p-selectbutton id="..."> widget id is clean and unique.
    """
    xpath = f"//p-selectbutton[@id='{selectbutton_id}']//div[@aria-label='{value}']"
    WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    ).click()


SRK_SELECTBUTTON_ID_KEYS = {"luster": "lusterMultiselect", "shade": "shadeMultiselect"}


def apply_shape(driver, shape: str, timeout=10):
    xpath = f"//span[@class='shape-label' and text()='{shape}']/ancestor::a"
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        ).click()
    except Exception:
        count = driver.execute_script(
            "return document.evaluate(arguments[0], document, null, "
            "XPathResult.UNORDERED_NODE_SNAPSHOT_TYPE, null).snapshotLength;",
            xpath
        )
        print(f"[srk][debug] apply_shape xpath match count={count}, "
              f"url={driver.current_url!r}, title={driver.title!r}, "
              f"readyState={driver.execute_script('return document.readyState')!r}")
        try:
            driver.save_screenshot("srk_debug_apply_shape_FAILURE.png")
            print("[srk] screenshot saved: srk_debug_apply_shape_FAILURE.png")
        except Exception:
            pass
        raise


def apply_carat_range(driver, from_val, to_val):
    if from_val is not None:
        el = driver.find_element(By.ID, "fromValue")
        el.clear()
        el.send_keys(str(from_val))
        print(f"[srk][debug] carat fromValue readback={el.get_attribute('value')!r} (wanted {from_val})")
    if to_val is not None:
        el = driver.find_element(By.ID, "toValue")
        el.clear()
        el.send_keys(str(to_val))
        print(f"[srk][debug] carat toValue readback={el.get_attribute('value')!r} (wanted {to_val})")


def apply_total_depth_range(driver, from_val, to_val):
    if from_val is not None:
        el = driver.find_element(By.XPATH, "//input[@id='Total DepthFromValue']")
        el.clear()
        el.send_keys(str(from_val))
        print(f"[srk][debug] depth fromValue readback={el.get_attribute('value')!r} (wanted {from_val})")
    if to_val is not None:
        el = driver.find_element(By.XPATH, "//input[@id='Total DepthToValue']")
        el.clear()
        el.send_keys(str(to_val))
        print(f"[srk][debug] depth toValue readback={el.get_attribute('value')!r} (wanted {to_val})")


def apply_filters(driver, filters: dict):
    """
    filters keys: shape, carat_from, carat_to, clarity, colour, shade,
    cut, polish, symmetry, fluorescence, luster, lab,
    total_depth_from, total_depth_to
    """
    if filters.get("shape"):
        print(f"[srk] applying shape={filters['shape']}")
        apply_shape(driver, filters["shape"])

    print("[srk] applying carat range")
    apply_carat_range(driver, filters.get("carat_from"), filters.get("carat_to"))
    print("[srk] applying total depth range")
    apply_total_depth_range(driver, filters.get("total_depth_from"), filters.get("total_depth_to"))

    for key, label in SRK_FILTER_LABELS.items():
        val = filters.get(key)
        if val:
            print(f"[srk] clicking {key}={val} (label={label})")
            if key in SRK_SELECTBUTTON_ID_KEYS:
                click_option_by_selectbutton_id(driver, SRK_SELECTBUTTON_ID_KEYS[key], val)
            elif key in SRK_BOX_ID_KEYS:
                click_option_by_box_id(driver, SRK_BOX_ID_KEYS[key], val)
            else:
                click_option_near_label(driver, label, val)
            print(f"[srk] window handles alive: {driver.window_handles}")


def open_modify_search(driver, timeout=10, required=True):
    """Click 'Modify Search' icon on the result page — opens filter panel back up
    WITHOUT navigating away / reloading. Confirmed real DOM: span#filter with class
    'modify-search-icon', wrapped in an <a>.
    required=False: tolerate the icon not being clickable — happens when the panel
    is ALREADY open (e.g. previous input set hit 0 results and we skipped Search,
    so the panel never closed). In that case just continue, nothing to open.
    """
    xpath = "//span[@id='filter' and contains(@class,'modify-search-icon')]/ancestor::a[1]"
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        ).click()
    except Exception:
        if required:
            raise
        print("[srk] modify-search icon not clickable — panel likely already open, continuing")


def reset_search(driver, timeout=10):
    """Inside the reopened filter panel, clear every filter left over from the
    previous input set before applying the next one. Confirmed real DOM: same
    id='searchBtn' as the final submit button, text reads 'Reset Search' in this state.
    """
    xpath = "//button[@id='searchBtn' and contains(normalize-space(.),'Reset')]"
    WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    ).click()


def get_preview_count(driver, timeout=5):
    """Filter panel shows a live '< N stones matching your criteria found.' label
    (id='searchfooter') as filters are picked, BEFORE the final Search click. If it
    reads 0, skip clicking Search + scanning entirely — saves a full round trip on
    empty input sets. Returns int or None if the label isn't there/unreadable.
    """
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#searchfooter label"))
        )
        import re
        m = re.search(r"(\d+)", el.text.strip())
        return int(m.group(1)) if m else None
    except Exception:
        return None


def run_search(driver, timeout=15, wait_for_new_results=False):
    """wait_for_new_results=True: used from the modify-search flow, where the URL
    never changes (still /search-result from the previous run) so url_contains is
    a no-op check. Instead, grab a cell that belongs to the OLD result set before
    clicking, then wait for it to go stale — that's the real signal new data landed.
    """
    old_cell = None
    if wait_for_new_results:
        try:
            old_cell = driver.find_element(By.TAG_NAME, "igx-grid-cell")
        except Exception:
            old_cell = None

    btn = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(text())='Search']"))
    )
    btn.click()

    if wait_for_new_results and old_cell is not None:
        try:
            WebDriverWait(driver, timeout).until(EC.staleness_of(old_cell))
        except Exception:
            pass  # grid may re-use DOM nodes in place; fall through, scan will still run
    else:
        WebDriverWait(driver, timeout).until(EC.url_contains("search-result"))


def get_video_link(driver, row_element, timeout=10):
    """Click row's diamond-details icon to open the shared overlay menu (id='mediaIconOverlay',
    positioned absolutely, lives OUTSIDE the row/table — a singleton reused+repositioned per
    click), then click 'HD Movie' inside that overlay, grab URL from new tab, close it.
    """
    try:
        icon = row_element.find_element(
            By.XPATH, ".//span[contains(@class,'grid-icon') and contains(@class,'icon-media')]"
        )
    except Exception:
        print("[srk] no video icon on this row, skipping")
        return ""
    try:
        icon.click()

        hd_movie = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//div[@id='mediaIconOverlay']//span[contains(@class,'dtl-icon-text') "
                "and normalize-space(text())='HD Movie']/ancestor::a[1]",
            ))
        )
        main_window = driver.current_window_handle
        hd_movie.click()
    except Exception:
        print("[srk] video icon found but hover/click flow failed, skipping")
        return ""

    try:
        WebDriverWait(driver, timeout).until(lambda d: len(d.window_handles) > 1)
    except Exception:
        return ""  # no new tab opened, no link found

    new_window = [w for w in driver.window_handles if w != main_window][0]
    driver.switch_to.window(new_window)
    video_url = driver.current_url
    driver.close()
    driver.switch_to.window(main_window)
    return video_url


# aria-describedby on each <igx-grid-cell> looks like "igx-grid-1_shape_key" — the part
# after the first underscore is a stable field id, confirmed live from DOM. Far more
# reliable than matching header text against a real <table> that doesn't exist here —
# this is an Angular Ignite UI grid (<igx-grid-cell> divs with role=gridcell), not a
# literal HTML table. TD (Total Depth) field id unconfirmed — check live DOM if it stays blank.
SRK_FIELD_KEY_TO_HEADER = {
    "product_name": "Stone ID",
    "shape_key": "Shape",
    "carat": "Carat",
    "clarity_key": "Clarity",
    "color_key": "Color",
    "certificate_key": "Cert",
    "total_depth_percent": "TD",
    "rap_off_display": "Off%",
    "cut_key": "Cut",
    "polish_key": "Pol",
    "symmetry_key": "Sym",
    "fluor_key": "Fluor",
    "shade_key": "Shd",
    "luster_key": "Lust",
    "sgs": "SGS Comment",
    "kts": "Key To Symbol",
    "lab_comment": "LAB Comments",
}


def _find_horizontal_scroller(driver):
    """Ignite UI grids drive column virtualization through a hidden helper div
    (class containing 'vhelper--horizontal') — scrolling the visible content div
    directly (previous approach) grabbed the wrong, much-smaller-range element.
    """
    return driver.execute_script("""
        let vh = document.querySelector('[class*="vhelper--horizontal"]');
        if (vh && vh.scrollWidth > vh.clientWidth) return vh;

        // fallback: walk up from a cell looking for anything that actually scrolls
        const cell = document.querySelector('igx-grid-cell');
        let el = cell;
        while (el) {
            if (el.scrollWidth > el.clientWidth + 5) return el;
            el = el.parentElement;
        }
        return null;
    """)


def _find_vertical_scroller(driver):
    """Row virtualization equiv of the horizontal one above — hidden helper div,
    class containing 'vhelper--vertical'. Fallback walks up checking scrollHeight
    instead of scrollWidth.
    """
    return driver.execute_script("""
        let vv = document.querySelector('[class*="vhelper--vertical"]');
        if (vv && vv.scrollHeight > vv.clientHeight) return vv;

        const cell = document.querySelector('igx-grid-cell');
        let el = cell;
        while (el) {
            if (el.scrollHeight > el.clientHeight + 5) return el;
            el = el.parentElement;
        }
        return null;
    """)


def _get_row_height(driver, default=40):
    h = driver.execute_script("""
        const c = document.querySelector('igx-grid-cell');
        return c ? c.getBoundingClientRect().height : 0;
    """)
    return h if h and h > 5 else default


def scan_full_grid(driver, timeout=15):
    """Row AND column virtualization both active on this grid — a cell only exists in
    DOM once its row is vertically in view AND its column is horizontally in view.
    So: outer loop = vertical (rows), inner loop = full horizontal sweep at each
    vertical stop. rows_data/row_anchor persist across every stop -> merges into one
    complete set regardless of scan order (first-non-blank-wins per cell).

    Speed: scan_once used to be N Selenium round-trips (one .text/.get_attribute
    per cell) — that per-cell network hop was the real cost, not the sleeps. Now a
    single execute_script pulls every visible cell's rowindex/field/text in one call.
    Vertical step is now page-sized (~90% of the grid's own viewport height) instead
    of ~1 row at a time — virtualization only cares about what's near viewport, a
    tiny per-row step was just re-scanning the same rendered rows over and over.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "igx-grid-cell"))
        )
    except Exception:
        print("[srk] no result grid appeared within timeout — treating as 0 results")
        return {}, {}

    rows_data = {}   # rowindex -> {our_header: text}
    row_anchor = {}  # rowindex -> True, just existence-tracking now (video-link path re-queries live)

    SCAN_JS = """
        const cells = document.querySelectorAll('igx-grid-cell');
        const out = [];
        for (const c of cells) {
            const ri = c.getAttribute('data-rowindex');
            if (ri === null) continue;
            const described = c.getAttribute('aria-describedby') || '';
            const us = described.indexOf('_');
            const key = us >= 0 ? described.slice(us + 1) : described;
            const stoneEl = c.querySelector('a.stoneid-text');
            const text = (stoneEl ? stoneEl.textContent : c.innerText || c.textContent || '').trim();
            out.push([ri, key, text]);
        }
        return out;
    """

    def scan_once():
        data = driver.execute_script(SCAN_JS)
        for rowindex, field_key, text in data:
            header = SRK_FIELD_KEY_TO_HEADER.get(field_key)
            if not header:
                continue
            row_dict = rows_data.setdefault(rowindex, {})
            if text:  # never let a blank/mid-render scan overwrite or block a real value
                row_dict[header] = text
            else:
                row_dict.setdefault(header, "")
            row_anchor.setdefault(rowindex, True)
        return len(data)

    h_scroller = _find_horizontal_scroller(driver)
    v_scroller = _find_vertical_scroller(driver)

    def horizontal_sweep(tag):
        n = scan_once()
        print(f"[srk] {tag} h-pos 0: {n} cells, {len(rows_data)} rows so far")
        if not h_scroller:
            return
        max_h = driver.execute_script(
            "return arguments[0].scrollWidth - arguments[0].clientWidth;", h_scroller
        )
        step = 150  # widened from 100 now that scan itself is cheap — fewer stops, still no gaps
        pos = 0
        while pos < max_h:
            pos = min(pos + step, max_h)
            driver.execute_script(
                "arguments[0].scrollLeft = arguments[1]; "
                "arguments[0].dispatchEvent(new Event('scroll'));",
                h_scroller, pos,
            )
            time.sleep(0.18)
            n = scan_once()
            print(f"[srk] {tag} h-pos {pos}/{max_h}: {n} cells, {len(rows_data)} rows so far")
        driver.execute_script(
            "arguments[0].scrollLeft = 0; arguments[0].dispatchEvent(new Event('scroll'));",
            h_scroller,
        )
        time.sleep(0.15)

    if v_scroller:
        driver.execute_script(
            "arguments[0].scrollTop = 0; arguments[0].dispatchEvent(new Event('scroll'));",
            v_scroller,
        )
        time.sleep(0.2)

    horizontal_sweep("v-pos 0")

    if v_scroller:
        max_v = driver.execute_script(
            "return arguments[0].scrollHeight - arguments[0].clientHeight;", v_scroller
        )
        client_h = driver.execute_script("return arguments[0].clientHeight;", v_scroller) or 400
        step = max(int(client_h * 0.85), 100)  # page-sized, ~15% overlap so no row-band gets skipped
        pos = 0
        while pos < max_v:
            pos = min(pos + step, max_v)
            driver.execute_script(
                "arguments[0].scrollTop = arguments[1]; "
                "arguments[0].dispatchEvent(new Event('scroll'));",
                v_scroller, pos,
            )
            time.sleep(0.25)
            horizontal_sweep(f"v-pos {pos}/{max_v}")
        driver.execute_script(
            "arguments[0].scrollTop = 0; arguments[0].dispatchEvent(new Event('scroll'));",
            v_scroller,
        )
    else:
        print("[srk] no vertical scroller found — grid may be single-page, or rows beyond viewport missed")

    print(f"[srk] scan done: {len(rows_data)} total rows")
    return rows_data, row_anchor


def parse_results(driver, fetch_video=True, timeout=15):
    rows_data, row_anchor = scan_full_grid(driver, timeout=timeout)

    if not rows_data:
        return pd.DataFrame(columns=SRK_RESULT_COLUMNS)

    records = []
    for i, rowindex in enumerate(sorted(rows_data.keys(), key=int), start=1):
        raw = rows_data[rowindex]
        stone_id = raw.pop("Stone ID", "")

        rec = {"Sr No.": i, "Stone ID": stone_id}
        for src_col, out_col in SRK_COLUMN_MAP.items():
            rec[out_col] = raw.get(src_col, "")

        if fetch_video:
            # video-link path needs a live Selenium element — row_anchor no longer stores
            # one (JS scan doesn't), so re-locate this row's cell by data-rowindex on demand.
            try:
                cell = driver.find_element(
                    By.CSS_SELECTOR, f"igx-grid-cell[data-rowindex='{rowindex}']"
                )
                row_el = cell.find_element(By.XPATH, "./ancestor::*[@role='row'][1]")
            except Exception:
                row_el = None
            rec["Video Link URL"] = get_video_link(driver, row_el) if row_el is not None else ""
        else:
            rec["Video Link URL"] = ""

        records.append(rec)

    df = pd.DataFrame(records)
    return df[SRK_RESULT_COLUMNS]


def _reassert_devtool_block(driver):
    """Site's anti-automation 'please close devtool' overlay-blocker only sticks for
    the page load it was set on — must re-poke it after every driver.get(), or it
    creeps back in and starts eating clicks a few navigations in (root cause of the
    bulk run dying at the same step every row).
    """
    try:
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": ["*disable-devtool*"]})
    except Exception:
        pass


def run(driver, filters: dict, fetch_video=True, fresh_nav=True):
    """Assumes driver already logged in / session active on pure.srk.one.
    fresh_nav=True: normal single-search path — full driver.get(SRK_SEARCH_URL).
    fresh_nav=False: bulk path after row 1 — stay on the result page, click
    'Modify Search' + 'Reset Search' instead of reloading (no full page nav, so
    no fresh 'please close devtool' race, and much faster than a full reload).
    """
    if fresh_nav:
        driver.get(SRK_SEARCH_URL)
        _reassert_devtool_block(driver)
    else:
        open_modify_search(driver, required=False)
        reset_search(driver)
        time.sleep(0.4)

    apply_filters(driver, filters)

    count = get_preview_count(driver)
    if count == 0:
        print("[srk] preview count = 0 — skipping Search click + scan for this input set")
        print(f"[srk][debug] url={driver.current_url!r} title={driver.title!r}")
        return pd.DataFrame(columns=SRK_RESULT_COLUMNS)

    run_search(driver, wait_for_new_results=not fresh_nav)
    return parse_results(driver, fetch_video=fetch_video)


# ---- bulk (multi-input-set) support -----------------------------------------

SHAPE_ABBR = {
    "RD": "Round", "OV": "Oval", "PS": "Pear", "EM": "Emerald", "LR": "L Radiant",
    "PR": "Princess", "SE": "Sq Emerald", "HT": "Heart", "MQ": "Marquise",
    "CU": "Cushion", "CP": "Cu Plasma", "TR": "Triangular",
}
SHADE_ABBR = {
    "N": "None", "NONE": "None", "NIL": "None",
    "MT1": "Mix Tinge 1", "MT2": "Mix Tinge 2",
    "PT": "Pink Tinge", "GT": "Green Tinge",
    "BR": "Brown", "BROWN": "Brown",
}
LUSTER_ABBR = {
    "EX": "Excellent", "VG": "Very Good", "G": "Good",
    "SM": "Slight Milky", "MM": "Medium Milky", "HM": "Heavy Milky",
}
FLUOR_ABBR = {
    "NONE": "None", "NIL": "None", "FA": "Faint", "FNT": "Faint",
    "MD": "Medium", "MED": "Medium", "ST": "Strong", "STG": "Strong",
    "VST": "Very Strong", "MD-BL": "Medium", "BL": "Strong",
}


def _clean(v):
    """Strip pandas NaN / blank cells -> None. Never returns literal 'nan' string."""
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    s = str(v).strip()
    if s == "" or s.lower() == "nan":
        return None
    return s


def _get_col(row, *names):
    """Try several header spellings — 'CARAT From' vs 'CARAT(From)' etc — first match wins."""
    for n in names:
        if n in row:
            v = row.get(n)
            if _clean(v) is not None:
                return v
    return None


def bulk_row_to_filters(row) -> dict:
    """One row of agent_srk_bulkinput.xlsx -> filters dict for run().
    Expected cols: SHAPE, CARAT From/CARAT(From), CARAT To/CARAT(To), CLARITY,
    COLOUR, SHADE, CUT, POLISH, SYMMETRY, FLUORESCENCE, LUSTER, LAB,
    TOTAL DEPTH From/TOTAL DEPTH(From), TOTAL DEPTH To/TOTAL DEPTH(To).
    Single CARAT/TOTAL DEPTH cols and 'video Link' col ignored.
    """
    shape = _clean(row.get("SHAPE"))
    if shape:
        shape = SHAPE_ABBR.get(shape.upper(), shape)

    luster = _clean(row.get("LUSTER"))
    if luster:
        luster = LUSTER_ABBR.get(luster.upper(), luster)

    shade = _clean(row.get("SHADE"))
    if shade:
        shade = SHADE_ABBR.get(shade.upper(), shade)
    else:
        shade = "None"  # blank cell = explicitly restrict to no-shade, not "leave site default"
        # (site's own default left this filter unrestricted and let e.g. Mix Tinge 1
        # stones slip into an otherwise all-None result set)

    fluor = _clean(row.get("FLUORESCENCE"))
    if fluor:
        fluor = FLUOR_ABBR.get(fluor.upper(), fluor)
    else:
        fluor = "None"  # same reasoning as shade above

    def _num(v):
        v = _clean(v)
        return float(v) if v is not None else None

    return {
        "shape": shape,
        "carat_from": _num(_get_col(row, "CARAT From", "CARAT(From)")),
        "carat_to": _num(_get_col(row, "CARAT To", "CARAT(To)")),
        "clarity": _clean(row.get("CLARITY")),
        "colour": _clean(row.get("COLOUR")),
        "shade": shade,
        "cut": _clean(row.get("CUT")),
        "polish": _clean(row.get("POLISH")),
        "symmetry": _clean(row.get("SYMMETRY")),
        "fluorescence": fluor,
        "luster": luster,
        "lab": _clean(row.get("LAB")),
        "total_depth_from": _num(_get_col(row, "TOTAL DEPTH From", "TOTAL DEPTH(From)")),
        "total_depth_to": _num(_get_col(row, "TOTAL DEPTH To", "TOTAL DEPTH(To)")),
    }


def _driver_alive(driver) -> bool:
    try:
        _ = driver.title
        return True
    except Exception:
        return False


def run_bulk(driver, bulk_df: "pd.DataFrame", progress_cb=None):
    """Sequential: input set 1 -> search -> full scroll-scan -> back to input page
    -> input set 2 -> ... Stacks all results into one ALL df, echoes inputs into
    an INPUTS df. Retries a row once on error; stops early (doesn't crash the rest)
    if the browser itself dies mid-run.
    Returns (inputs_df, all_df).
    """
    all_frames = []
    input_records = []
    driver_dead = False

    for i, (_, row) in enumerate(bulk_df.iterrows(), start=1):
        filters = bulk_row_to_filters(row)
        input_records.append({"Input Row": i, **filters})

        if progress_cb:
            progress_cb(i, len(bulk_df), filters)

        if driver_dead:
            print(f"[srk][bulk] row {i}: skipped, driver already dead")
            continue

        last_err = None
        df = None
        for attempt in (1, 2):
            try:
                # row 1 (or a retry after driver trouble): fresh nav. Otherwise modify-search.
                fresh = (i == 1 and attempt == 1)
                df = run(driver, filters, fetch_video=False, fresh_nav=fresh)
                break
            except Exception as e:
                last_err = e
                import traceback as _tb
                print(f"[srk][bulk] row {i} attempt {attempt} failed: "
                      f"[{type(e).__name__}] {e}")
                print(_tb.format_exc(limit=6))
                if not _driver_alive(driver):
                    driver_dead = True
                    break
                try:
                    driver.save_screenshot(f"srk_debug_row{i}_attempt{attempt}_FAILURE.png")
                except Exception:
                    pass

        if df is None:
            print(f"[srk][bulk] row {i}: giving up after retry ({last_err})")
            continue

        df.insert(0, "Input Row", i)
        all_frames.append(df)
        print(f"[srk][bulk] row {i}: {len(df)} results")

    all_df = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame(
        columns=["Input Row"] + SRK_RESULT_COLUMNS
    )
    inputs_df = pd.DataFrame(input_records)
    return inputs_df, all_df