# Star Rays original-discount stage

Current pipeline:

Rapaport scrape
→ Company + Vendor Stock #
→ Star Rays lookup for Star Rays rows
→ Star Rays `RAP.%`
→ `Original Discount %` inserted immediately beside `%Rap (Back Discount)`
→ Summary + Excel export

## Environment

```env
STARRAYS_USERNAME=
STARRAYS_PASSWORD=
# Alternative accepted name:
STARRAYS_USER_ID=
# Optional:
STARRAYS_PROFILE_DIR=
```

`app.py` needs no Excel/UI change for the new column: `build_excel()` writes the
entire DataFrame to `Details`, so the inserted column is exported automatically.

## Star Rays selectors confirmed from supplied DevTools screenshots

- Login user ID: `#Email`
- Login password: `#Password`
- Login: `button[type='submit']`
- Stock search input: `#TxtSearchByRefCertNo`
- Search icon: `img[alt='search']`
- Results: DataTables-style `table > thead/tbody`
- Target result columns: `REF.NO/DNA` and `RAP.%`

The result parser discovers the `RAP.%` column by header text instead of hard-coding
its column index.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

First Star Rays run should use `headless=False` so authentication/session behavior
can be observed. Later runs can use `headless=True`.

The Star Rays browser profile is separate from Rapaport:
`browser_profile_starrays/`.

No credentials are written into source code.
