import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd

from config import (
    SRK_SEARCH_URL, SRK_ROOT_URL, SRK_SIDEBAR_SEARCH_NAV,
    SRK_FILTER_LABELS, SRK_COLUMN_MAP, SRK_RESULT_COLUMNS,
    SRK_COLOUR_SCALE, SRK_CLARITY_SCALE, SRK_RANGE_ALL, expand_scale_range,
    CHECKPOINT_DIR,
)
from checkpoint import (
    paths_for, append_checkpoint, write_progress, load_progress,
    load_checkpoint_df,
)


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


def apply_shape(driver, shape, timeout=10):
    shapes = shape if isinstance(shape, (list, tuple)) else [shape]
    for s in shapes:
        xpath = f"//span[@class='shape-label' and text()='{s}']/ancestor::a"

        try:
            el = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )

            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                el
            )

            time.sleep(0.15)

            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)

        except Exception:
            count = driver.execute_script(
                "return document.evaluate(arguments[0], document, null, "
                "XPathResult.UNORDERED_NODE_SNAPSHOT_TYPE, null).snapshotLength;",
                xpath
            )
            print(
                f"[srk][debug] apply_shape xpath match count={count}, "
                f"url={driver.current_url!r}, title={driver.title!r}, "
                f"readyState={driver.execute_script('return document.readyState')!r}"
            )
            try:
                driver.save_screenshot(f"srk_debug_apply_shape_FAILURE_{s}.png")
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


# Colour and Clarity are graded SCALES, so callers can hand over a From/To
# pair instead of listing every value. SRK's own page has no range control —
# they're plain multi-select chips — so the pair gets expanded here into
# every value between the two ends and each chip is clicked in turn.
# Order lives in config.SRK_COLOUR_SCALE / SRK_CLARITY_SCALE.
SRK_RANGE_FILTERS = {
    "clarity": SRK_CLARITY_SCALE,
    "colour": SRK_COLOUR_SCALE,
}


def resolve_range_filters(filters: dict) -> dict:
    """Normalise clarity/colour into plain chip lists before clicking.

    Accepts either form, so nothing that already worked breaks:
      - filters['clarity'] = 'VVS1' or ['VVS1','VVS2']  -> used as-is
      - filters['clarity_from'] / ['clarity_to']        -> expanded to a range

    'All' (or a blank end) means the filter isn't applied at all — SRK
    returns everything when no chip in a section is selected."""
    resolved = dict(filters)
    for key, scale in SRK_RANGE_FILTERS.items():
        if resolved.get(key):
            continue  # explicit list/value wins over the From/To pair
        from_val = _clean(resolved.get(f"{key}_from"))
        to_val = _clean(resolved.get(f"{key}_to"))
        if not from_val and not to_val:
            continue
        # One end left blank/'All' but the other set: treat the blank end as
        # the far end of the scale rather than silently dropping the filter.
        if not from_val or from_val == SRK_RANGE_ALL:
            from_val = scale[0] if to_val and to_val != SRK_RANGE_ALL else SRK_RANGE_ALL
        if not to_val or to_val == SRK_RANGE_ALL:
            to_val = scale[-1] if from_val != SRK_RANGE_ALL else SRK_RANGE_ALL
        values = expand_scale_range(scale, from_val, to_val)
        if values:
            resolved[key] = values
            print(f"[srk] {key} range {from_val}-{to_val} -> {values}")
    return resolved


def apply_filters(driver, filters: dict):
    """
    filters keys: shape, carat_from, carat_to, clarity, colour, shade,
    cut, polish, symmetry, fluorescence, luster, lab,
    total_depth_from, total_depth_to
    """
    filters = resolve_range_filters(filters)

    if filters.get("shape"):
        print(f"[srk] applying shape={filters['shape']}")
        apply_shape(driver, filters["shape"])

    print("[srk] applying carat range")
    apply_carat_range(driver, filters.get("carat_from"), filters.get("carat_to"))
    print("[srk] applying total depth range")
    apply_total_depth_range(driver, filters.get("total_depth_from"), filters.get("total_depth_to"))

    for key, label in SRK_FILTER_LABELS.items():
        vals = filters.get(key)
        if not vals:
            continue
        vals = vals if isinstance(vals, (list, tuple)) else [vals]
        for val in vals:
            print(f"[srk] clicking {key}={val} (label={label})")
            if key in SRK_SELECTBUTTON_ID_KEYS:
                click_option_by_selectbutton_id(driver, SRK_SELECTBUTTON_ID_KEYS[key], val)
            elif key in SRK_BOX_ID_KEYS:
                click_option_by_box_id(driver, SRK_BOX_ID_KEYS[key], val)
            else:
                click_option_near_label(driver, label, val)
        print(f"[srk] window handles alive: {driver.window_handles}")


def open_modify_search(driver, timeout=10, required=True):
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
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        ).click()
        return
    except Exception:
        pass
    print("[srk] reset_search: no Reset button found yet (no search submitted) — no-op")


def get_preview_count(driver, timeout=6.0, settle=0.6):
    """Read SRK live result count, waiting for it to SETTLE.

    Reading the DOM directly (rather than a Selenium WebDriverWait on
    #searchfooter label) is still the fast path. What changed: the count is
    recomputed asynchronously after every chip click, so the old 1.5s
    snapshot could read a STALE number — or nothing at all — and return
    None. None is not 0, so run() sailed past its zero-result guard, clicked
    Search on a search that matches nothing, and then sat in
    EC.url_contains("search-result") until it timed out. Clicking a whole
    clarity/colour RANGE (6+ chips instead of 2) made that race much easier
    to lose.

    Now: poll until the same value has been seen continuously for `settle`
    seconds, then return it. Returns int, or None if the footer never
    produced a number within `timeout`.
    """
    import re
    script = """
        const el = document.querySelector('#searchfooter label');
        return el ? (el.innerText || el.textContent || '').trim() : '';
    """
    deadline = time.monotonic() + timeout
    stable_value = None
    stable_since = None
    last_text = ''
    while time.monotonic() < deadline:
        try:
            text = (driver.execute_script(script) or '').strip()
            last_text = text
            # Thousand separators must go before int() — "1,234 Stones"
            # otherwise parses as 1 and every downstream size calculation is
            # wrong.
            m = re.search(r"([\d,]+)", text)
            value = int(m.group(1).replace(",", "")) if m else None
        except Exception:
            value = None

        if value is not None:
            if value == stable_value:
                if time.monotonic() - stable_since >= settle:
                    return value
            else:
                stable_value = value
                stable_since = time.monotonic()
        time.sleep(0.08)

    if stable_value is not None:
        return stable_value  # never settled, but a number was seen — use the last one
    print(f"[srk] preview count unreadable (footer text={last_text!r})")
    return None


def _click_search_button(driver, timeout=15):
    """Click the real submit control.

    Confirmed DOM: the submit button is id='searchBtn' — the SAME element
    reset_search() targets, whose label just flips to 'Reset Search' once a
    search has been run. The old locator here was
    //button[normalize-space(text())='Search'], which is fragile: the label
    sits inside a child span, so normalize-space(text()) is empty on the
    real button and the xpath matched some other inert 'Search' element.
    Result: element_to_be_clickable passed, .click() did nothing, no
    navigation ever happened, and the caller timed out with a healthy
    500-stone preview count on screen.
    """
    xpath = "//button[@id='searchBtn' and not(contains(normalize-space(.),'Reset'))]"
    try:
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
    except Exception:
        # Fall back to the old text match rather than failing outright — if
        # the id ever changes this keeps working.
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(normalize-space(.),'Search')]"))
        )

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    time.sleep(0.15)
    try:
        btn.click()
    except Exception:
        # Chip clicks can leave an overlay/tooltip covering the footer; a JS
        # click bypasses the intercept check.
        driver.execute_script("arguments[0].click();", btn)
    print(f"[srk] search submitted (btn id={btn.get_attribute('id')!r})")


def _results_ready(driver, timeout):
    """Search is done when EITHER the route changes to /search-result OR the
    grid paints cells. Waiting only on the URL was too strict — the SPA
    sometimes renders results in place without a route change, which read as
    a failure even though data was right there."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if "search-result" in (driver.current_url or ""):
                return True
            if driver.find_elements(By.TAG_NAME, "igx-grid-cell"):
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def run_search(driver, timeout=15, wait_for_new_results=False):
    """wait_for_new_results=True: used from the modify-search flow, where the URL
    never changes (still /search-result from the previous run) so url_contains is
    a no-op check. Instead, grab a cell that belongs to the OLD result set before
    clicking, then wait for it to go stale — that's the real signal new data landed.

    Returns True when results are up, False when nothing came back (caller
    treats that as an empty result set instead of crashing the run).
    """
    old_cell = None
    if wait_for_new_results:
        try:
            old_cell = driver.find_element(By.TAG_NAME, "igx-grid-cell")
        except Exception:
            old_cell = None

    _click_search_button(driver, timeout=timeout)

    if wait_for_new_results and old_cell is not None:
        try:
            WebDriverWait(driver, timeout).until(EC.staleness_of(old_cell))
        except Exception:
            pass  # grid may re-use DOM nodes in place; fall through, scan will still run
        return True

    if _results_ready(driver, timeout):
        return True

    print(f"[srk] no results within {timeout}s (url={driver.current_url!r}) — "
          f"treating as 0 results")
    return False


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
        step = 300  # was 150 — half the horizontal stops, same coverage since scan itself is cheap
        pos = 0
        while pos < max_h:
            pos = min(pos + step, max_h)
            driver.execute_script(
                "arguments[0].scrollLeft = arguments[1]; "
                "arguments[0].dispatchEvent(new Event('scroll'));",
                h_scroller, pos,
            )
            time.sleep(0.12)  # was 0.18
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
        step = max(int(client_h * 0.65), 100)
        pos = 0
        while pos < max_v:
            pos = min(pos + step, max_v)
            driver.execute_script(
                "arguments[0].scrollTop = arguments[1]; "
                "arguments[0].dispatchEvent(new Event('scroll'));",
                v_scroller, pos,
            )
            time.sleep(0.18)  # was 0.25
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
        driver.execute_cdp_cmd(
            "Network.setBlockedURLs",
            {"urls": ["*://pure.srk.one/assets/js/disable-devtool.min.js"]},
        )
    except Exception as e:
        # was a silent `pass` before — if this call is ever failing, we need
        # to know, since a failed block here is the prime suspect for the
        # "row 1 times out on a blank page" failure.
        print(f"[srk][diag] _reassert_devtool_block FAILED: {type(e).__name__}: {e}")


def _diag_nav_state(driver, label=""):
    """Same idea as app.py's _diagnose_blank_page — prints to the TERMINAL,
    not the Streamlit page. Call this at the moment a navigation looks stuck
    so we're diagnosing the ACTUAL failing page, not just the /login page
    from Open Browser & Login (which always loads fine and tells us nothing
    about a later mid-run failure)."""
    try:
        print(f"[srk][diag]{' ' + label if label else ''} url:", driver.current_url)
        print(f"[srk][diag] readyState:", driver.execute_script("return document.readyState"))
        print(f"[srk][diag] body length:", len(driver.execute_script("return document.body.innerHTML")))
        for entry in driver.get_log("browser"):
            print(f"[srk][diag][console] {entry.get('level')}: {entry.get('message')}")
    except Exception as e:
        print(f"[srk][diag] diagnostic itself failed: {type(e).__name__}: {e}")


def run(driver, filters: dict, fetch_video=True, fresh_nav=True, panel_already_open=False):
    if fresh_nav:
        _reassert_devtool_block(driver)      # block BEFORE nav, not after

        # Do NOT hard-load SRK_SEARCH_URL directly — confirmed 09-Sep-2026
        # via console diag: a hard driver.get() straight to that deep route
        # throws "Cannot read properties of undefined (reading
        # 'ApplicationApi'/'AuditApi')" inside Angular's resolvers, and the
        # app bounces back to root. Root cause: some app-config init only
        # completes when the SPA boots from root, not from a deep-link hard
        # reload. Fix: land on root (matches the flow that already works
        # when logging in by hand), then CLICK the sidebar nav so Angular
        # does client-side routing instead of another full reload.
        if driver.current_url and "pure.srk.one" not in driver.current_url:
            driver.get(SRK_ROOT_URL)

        try:
            nav_el = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SRK_SIDEBAR_SEARCH_NAV))
            )
            nav_el.click()
            WebDriverWait(driver, 20).until(EC.url_contains("/web/search"))
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//span[@class='shape-label']"))
            )                                     # confirm Angular actually bootstrapped
        except Exception:
            # diagnose the ACTUAL failing page, right here, right now — not
            # the /login page from Open Browser & Login, which tells us
            # nothing about THIS navigation
            _diag_nav_state(driver, label="(row1 fresh_nav timeout)")
            raise
        _reassert_devtool_block(driver)        # re-poke once more post-load, cheap insurance
    elif panel_already_open:
        pass
    else:
        open_modify_search(driver, timeout=2, required=False)
        reset_search(driver)
        time.sleep(0.15)

    apply_filters(driver, filters)

    count = get_preview_count(driver)
    print(f"[srk] preview count = {count}")
    if count == 0:
        print("[srk] preview count = 0 — resetting now, moving to next input set")
        reset_search(driver)
        return pd.DataFrame(columns=SRK_RESULT_COLUMNS)

    # Scale the results-wait with how many diamonds actually matched — a
    # few-thousand-stone hit genuinely takes longer for SRK's backend to
    # return and for the grid to render than a 3-row hit, flat 15s was
    # timing out on the big ones. Capped at 60s so a real failure still
    # surfaces instead of hanging forever.
    result_timeout = min(60, 15 + (count or 0) // 300 * 5)

    if not run_search(driver, wait_for_new_results=not fresh_nav, timeout=result_timeout):
        reset_search(driver)
        return pd.DataFrame(columns=SRK_RESULT_COLUMNS)

    return parse_results(driver, fetch_video=fetch_video, timeout=result_timeout)


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


def _as_list(v, abbr_map=None):
    """Bulk-input cell -> list of cleaned values. Split on ',' or ';' for
    multi-select cells (e.g. LAB cell = 'GIA,IGI' -> ['GIA','IGI']).
    Single-value cells ('GIA') still work -> ['GIA']. Blank/NaN -> []."""
    v = _clean(v)
    if v is None:
        return []
    import re
    items = [p.strip() for p in re.split(r"[,;]", v) if p.strip()]
    if abbr_map:
        items = [abbr_map.get(p.upper(), p) for p in items]
    return items


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
    COLOUR, SHADE, CUT, POLISH, SYMMETRY, FLUORESCENCE, LUSTER, LAB 1, LAB 2,
    TOTAL DEPTH From/TOTAL DEPTH(From), TOTAL DEPTH To/TOTAL DEPTH(To).
    Single CARAT/TOTAL DEPTH cols and 'video Link' col ignored.
    """
    shape = _clean(row.get("SHAPE"))
    if shape:
        shape = SHAPE_ABBR.get(shape.upper(), shape)

    shade = _as_list(row.get("SHADE"), SHADE_ABBR)
    if not shade:
        shade = ["None"]  # blank cell = explicitly restrict to no-shade, not "leave site default"
        # (site's own default left this filter unrestricted and let e.g. Mix Tinge 1
        # stones slip into an otherwise all-None result set)

    fluor = _as_list(row.get("FLUORESCENCE"), FLUOR_ABBR)
    if not fluor:
        fluor = ["None"]  # same reasoning as shade above

    def _num(v):
        v = _clean(v)
        return float(v) if v is not None else None

    return {
        "shape": shape,
        "carat_from": _num(_get_col(row, "CARAT From", "CARAT(From)")),
        "carat_to": _num(_get_col(row, "CARAT To", "CARAT(To)")),
        "clarity": _as_list(row.get("CLARITY")),
        "colour": _as_list(row.get("COLOUR")),
        "shade": shade,
        "cut": _as_list(row.get("CUT")),
        "polish": _as_list(row.get("POLISH")),
        "symmetry": _as_list(row.get("SYMMETRY")),
        "fluorescence": fluor,
        "luster": _as_list(row.get("LUSTER"), LUSTER_ABBR),
        "lab": _as_list(row.get("LAB 1")) + _as_list(row.get("LAB 2")),  # 2 separate cols instead of comma-in-cell
        "total_depth_from": _num(_get_col(row, "TOTAL DEPTH From", "TOTAL DEPTH(From)")),
        "total_depth_to": _num(_get_col(row, "TOTAL DEPTH To", "TOTAL DEPTH(To)")),
    }


def _driver_alive(driver) -> bool:
    try:
        _ = driver.title
        return True
    except Exception:
        return False


def run_bulk(driver, bulk_df: "pd.DataFrame", progress_cb=None,
             run_id: str = None, checkpoint_dir: str = None, resume: bool = True,
             restart_every: int = 200, rebuild_driver_fn=None):
    """
    Full pipeline over every row of a bulk-input DataFrame.

    CRASH-SAFETY: every row's result is appended to a checkpoint CSV on disk
    (fsynced) the instant it's scraped, plus a progress.json marking the
    last completed row — see checkpoint.py. If this process dies (power
    loss, crash, force-quit) at row 3000 of 4000, calling run_bulk again
    with the SAME bulk_df, SAME run_id, and resume=True (the default)
    skips rows 1-3000 and continues from 3001 — nothing already scraped is
    lost or re-fetched. run_id should be a hash of the uploaded file's raw
    bytes (see app.py) so a resume only matches the SAME input file.

    SPEED-OVER-SCALE FIX: this site's Angular SPA leaks DOM/JS-heap state
    the longer one tab stays alive across thousands of searches — that's
    the real cause of "starts fast, crawls after a while", not per-row
    logic cost. Every `restart_every` rows we force a full fresh navigation
    (same as row 1) to reset the Angular app state before it degrades.
    If rebuild_driver_fn is given (zero-arg callable returning a new,
    already-logged-in driver), we go further and fully quit+relaunch the
    browser process itself, clearing native Chrome memory bloat too — the
    profile dir keeps the session so this SHOULD skip re-captcha, but
    that's unconfirmed for this site, so it defaults to off (None) and we
    just do the cheap fresh-nav restart instead.

    Returns (inputs_df, all_df, csv_path, progress_path). Caller decides
    when it's safe to checkpoint.clear_checkpoint(csv_path, progress_path)
    — e.g. only after the Excel report was built successfully.
    """
    checkpoint_dir = checkpoint_dir or os.path.join(CHECKPOINT_DIR, "srk")
    run_id = run_id or "unkeyed-run"  # caller should always pass a real hash — see app.py
    csv_path, progress_path = paths_for(checkpoint_dir, run_id)

    last_done = load_progress(progress_path, run_id) if resume else 0
    if last_done:
        print(f"[srk][bulk] resuming after row {last_done} (checkpoint: {csv_path})")

    bulk_start_time = time.perf_counter()
    input_records = []
    driver_dead = False
    panel_already_open = False
    first_processed_row = True  # tracks first row THIS PROCESS actually
    # runs — NOT literal i==1. On a resume, rows up to last_done are
    # skip-continued, so i==1 never executes; fresh_nav must fire on
    # whichever row is first to actually run, or the browser (freshly
    # opened, sitting on /web/dashboard after manual login) never
    # navigates to the search page at all and every selector wait times
    # out hunting for a search panel that was never opened.

    for i, (_, row) in enumerate(bulk_df.iterrows(), start=1):
        filters = bulk_row_to_filters(row)
        display_filters = {
            k: (", ".join(v) if isinstance(v, (list, tuple)) else v)
            for k, v in filters.items()
        }
        input_records.append({"Input Row": i, **display_filters})

        if progress_cb:
            progress_cb(i, len(bulk_df), filters)

        if i <= last_done:
            continue  # already scraped + checkpointed in a previous (crashed) run — don't re-fetch

        if driver_dead:
            print(f"[srk][bulk] row {i}: skipped, driver already dead")
            continue

        # periodic restart — resets Angular SPA state before it degrades.
        if restart_every and not first_processed_row and (i % restart_every == 1):
            if rebuild_driver_fn:
                print(f"[srk][bulk] row {i}: restart_every hit — relaunching browser")
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = rebuild_driver_fn()
                panel_already_open = False
            else:
                print(f"[srk][bulk] row {i}: restart_every hit — forcing fresh nav")
            fresh = True
        else:
            fresh = first_processed_row

        first_processed_row = False

        try:
            df = run(
                driver,
                filters,
                fetch_video=False,
                fresh_nav=fresh,
                panel_already_open=panel_already_open
            )

        except Exception as e:
            import traceback as _tb

            print(
                f"[srk][bulk] row {i} failed: "
                f"[{type(e).__name__}] {e}"
            )
            print(_tb.format_exc(limit=6))

            if not _driver_alive(driver):
                driver_dead = True

            try:
                driver.save_screenshot(
                    f"srk_debug_row{i}_FAILURE.png"
                )
            except Exception:
                pass

            panel_already_open = False
            continue

        panel_already_open = (len(df) == 0)

        append_checkpoint(csv_path, df, i)
        write_progress(progress_path, i, run_id)

        print(f"[srk][bulk] row {i}: {len(df)} results (checkpointed)")

    # Build final all_df from the checkpoint file, not an in-memory list —
    # this way a resumed run's output includes rows scraped in the EARLIER
    # (crashed) process too, not just this process's new rows.
    all_df = load_checkpoint_df(csv_path)
    if all_df.empty:
        all_df = pd.DataFrame(columns=["Input Row"] + SRK_RESULT_COLUMNS)

    inputs_df = pd.DataFrame(input_records)

    bulk_end_time = time.perf_counter()
    total_seconds = bulk_end_time - bulk_start_time

    print(
        f"[srk][bulk] TOTAL TIME: "
        f"{total_seconds:.2f} seconds "
        f"({total_seconds / 60:.2f} minutes)"
    )

    return inputs_df, all_df, csv_path, progress_path

def logout(driver, timeout=5):
    """Clean session close before driver.quit() — clicks Logout (id='logoutBox'
    under the header profile menu), then confirms the "Do you want to logout?"
    dialog's Yes button (no id on it, matched via ng-reflect-label)."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.ID, "logoutBox"))
        ).click()

        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[@ng-reflect-label='Yes']")
            )
        ).click()

        time.sleep(1)
    except Exception:
        print("[srk] logout: control not found/clickable — skipping, driver.quit() will proceed anyway")