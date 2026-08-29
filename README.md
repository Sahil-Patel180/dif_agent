# Rapaport Discount Agent

## Setup (run on your own machine — Rapaport is login-walled, can't run from here)

```bash
pip install streamlit playwright pandas openpyxl
playwright install chromium
```

## Fix the selectors (one-time, required)

`scraper.py` has placeholder selectors (`#username`, `#caratMin`, `table#resultsTable`, etc.)
marked `# TODO: verify selector`. They will NOT work until you swap them for the real ones:

1. Run the app: `streamlit run app.py`
2. Leave "Run headless" **unchecked** so you can watch the real browser
3. When it fails on a step, open the live Rapaport page yourself, press F12,
   click the inspect arrow, click the field (login box, shape dropdown, search button, result row)
4. Right-click the highlighted HTML → Copy → Copy selector
5. Paste that into the matching line in `scraper.py`
6. Re-run, repeat until login → filter → results all pass
7. Also fix `scrape_results()` — match the `cell_text(i)` index numbers to the
   real column order in Rapaport's result table (open one row, count columns left to right)

## Run

```bash
streamlit run app.py
```

Opens a form in your browser: enter creds, set filters (shape/carat/color/clarity/
cut/pol/sym/FL — matches your sheet's green columns), click **Run Search**.
Get: summary card (company, min %, max %, rows fetched) + full data table +
**Download Excel Report** button (Summary + Details sheets).

## Notes

- Creds are typed fresh each run, never saved to disk.
- `headless=True` once selectors confirmed working — faster, no visible browser.
- If Rapaport changes their page layout later, selectors break again — same fix process.
- Respect Rapaport's Terms of Service for automated access before running this at scale.