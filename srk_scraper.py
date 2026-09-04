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
    WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    ).click()


def apply_carat_range(driver, from_val, to_val):
    if from_val is not None:
        el = driver.find_element(By.ID, "fromValue")
        el.clear()
        el.send_keys(str(from_val))
    if to_val is not None:
        el = driver.find_element(By.ID, "toValue")
        el.clear()
        el.send_keys(str(to_val))


def apply_total_depth_range(driver, from_val, to_val):
    if from_val is not None:
        el = driver.find_element(By.XPATH, "//input[@id='Total DepthFromValue']")
        el.clear()
        el.send_keys(str(from_val))
    if to_val is not None:
        el = driver.find_element(By.XPATH, "//input[@id='Total DepthToValue']")
        el.clear()
        el.send_keys(str(to_val))


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


def run_search(driver, timeout=15):
    btn = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(text())='Search']"))
    )
    btn.click()
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


def parse_results(driver, fetch_video=True, timeout=15):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.TAG_NAME, "igx-grid-cell"))
    )
    cells = driver.find_elements(By.TAG_NAME, "igx-grid-cell")
    print(f"[srk] found {len(cells)} igx-grid-cell elements")

    rows_data = {}   # rowindex -> {our_header: text}
    row_anchor = {}  # rowindex -> one cell, used to locate the row for video-link lookup

    for c in cells:
        rowindex = c.get_attribute("data-rowindex")
        if rowindex is None:
            continue
        described = c.get_attribute("aria-describedby") or ""
        field_key = described.split("_", 1)[1] if "_" in described else described
        header = SRK_FIELD_KEY_TO_HEADER.get(field_key)
        if not header:
            continue
        rows_data.setdefault(rowindex, {})[header] = c.text.strip()
        row_anchor.setdefault(rowindex, c)

    records = []
    for i, rowindex in enumerate(sorted(rows_data.keys(), key=int), start=1):
        raw = rows_data[rowindex]
        stone_id = raw.pop("Stone ID", "")

        rec = {"Sr No.": i, "Stone ID": stone_id}
        for src_col, out_col in SRK_COLUMN_MAP.items():
            rec[out_col] = raw.get(src_col, "")

        if fetch_video:
            try:
                row_el = row_anchor[rowindex].find_element(By.XPATH, "./ancestor::*[@role='row'][1]")
            except Exception:
                row_el = row_anchor[rowindex]
            rec["Video Link URL"] = get_video_link(driver, row_el)
        else:
            rec["Video Link URL"] = ""

        records.append(rec)

    df = pd.DataFrame(records)
    return df[SRK_RESULT_COLUMNS]


def run(driver, filters: dict, fetch_video=True):
    """Assumes driver already logged in / session active on pure.srk.one."""
    driver.get(SRK_SEARCH_URL)
    apply_filters(driver, filters)
    run_search(driver)
    return parse_results(driver, fetch_video=fetch_video)