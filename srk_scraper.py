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
SRK_BOX_ID_KEYS = {"cut": "cut", "polish": "polish", "symmetry": "symmetry"}


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
            if key in SRK_BOX_ID_KEYS:
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
    """Hover diamond-details icon, click 'HD Movie', grab URL from new tab, close it."""
    icon = row_element.find_element(
        By.XPATH, ".//a[@ng-reflect-dir-stone-multimedia-detail]"
    )
    ActionChains(driver).move_to_element(icon).perform()

    hd_movie = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(
            (By.XPATH, ".//span[contains(text(),'HD Movie')]/ancestor::a[1]")
        )
    )
    main_window = driver.current_window_handle
    hd_movie.click()

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


def parse_results(driver, fetch_video=True, timeout=15):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
    )
    headers = [th.text.strip() for th in driver.find_elements(By.CSS_SELECTOR, "table th")]
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

    records = []
    for i, row in enumerate(rows, start=1):
        cells = row.find_elements(By.TAG_NAME, "td")
        raw = {}
        for h, c in zip(headers, cells):
            raw[h] = c.text.strip()

        stone_id = raw.get("Diamond Details", "").split("\n")[0].strip()

        rec = {"Sr No.": i, "Stone ID": stone_id}
        for src_col, out_col in SRK_COLUMN_MAP.items():
            rec[out_col] = raw.get(src_col, "")

        rec["Video Link URL"] = get_video_link(driver, row) if fetch_video else ""
        records.append(rec)

    df = pd.DataFrame(records)
    return df[SRK_RESULT_COLUMNS]


def run(driver, filters: dict, fetch_video=True):
    """Assumes driver already logged in / session active on pure.srk.one."""
    driver.get(SRK_SEARCH_URL)
    apply_filters(driver, filters)
    run_search(driver)
    return parse_results(driver, fetch_video=fetch_video)