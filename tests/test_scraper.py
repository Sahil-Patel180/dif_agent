"""
test_scraper.py — sanity checks on discount % parsing + summary calc.
Run: pytest
Doesn't hit live Rapaport site (creds not available in CI) — only tests
the pure-logic pieces so regressions get caught fast.
"""

import pandas as pd
from scraper import compute_min_max_discount


def test_compute_min_max_discount_basic():
    df = pd.DataFrame({
        "Back (Discount %)": ["-66.27", "-59.36", "-70.10"]
    })
    result = compute_min_max_discount(df, "Test Co")
    assert result["Company"] == "Test Co"
    assert result["Min Discount %"] == -70.10
    assert result["Max Discount %"] == -59.36
    assert result["Rows Fetched"] == 3


def test_compute_min_max_discount_with_percent_signs():
    df = pd.DataFrame({
        "Back (Discount %)": ["-66.27%", "-59.36%"]
    })
    result = compute_min_max_discount(df, "Test Co")
    assert result["Min Discount %"] == -66.27
    assert result["Max Discount %"] == -59.36


def test_compute_min_max_discount_empty():
    df = pd.DataFrame({"Back (Discount %)": []})
    result = compute_min_max_discount(df, "Test Co")
    assert result["Rows Fetched"] == 0