# Invoice Extractor

Upload client PDF invoices and get a clean, structured Excel file back — instantly, no manual data entry.

---

## Features

- **Multi-client support** — separate extraction logic for 5 vendor formats: Amex, Airplay, Novel, Pine Labs, and Aerom, selectable via tabs.
- **Drag-and-drop upload** — drop multiple PDFs at once, or click to browse.
- **Automatic field extraction** — pulls invoice numbers, dates, GSTIN, line items, tax breakdowns, and totals using text parsing (with OCR fallback for scanned PDFs).
- **Instant Excel export** — extracted data is written to a formatted `.xlsx` file, ready to download.
- **In-browser preview** — see the first 200 extracted rows in a table before downloading.
- **Per-file error reporting** — if a PDF fails to parse, you're told exactly which file and why, without losing the rest of the batch.
- **Clear Cache button** — wipes generated Excel files from local storage on demand.
- **Runs two ways**: as a hosted web app (Docker/Render) or as a standalone desktop app (`.exe`, no browser or install required).
- **Custom favicon and branded footer** with owner attribution and a self-updating copyright year.

---

## Project Structure

```
project/
├── app/
│   ├── main.py                  # FastAPI app, routes, session handling
│   ├── excel_builder.py         # Converts extracted records to .xlsx
│   ├── tesseract_config.py      # Auto-detects Tesseract binary (OCR)
│   ├── extractors/
│   │   ├── amex.py
│   │   ├── airplay.py
│   │   ├── novel.py
│   │   ├── pinelabs.py
│   │   └── aerom.py
│   └── static/
│       ├── index.html           # Frontend UI
│       ├── favicon.ico
│       ├── favicon-32x32.png
│       └── apple-touch-icon.png
├── desktop.py                   # Entry point for the desktop .exe build
├── requirements.txt
├── requirements-desktop.txt     # Adds pyinstaller + pywebview
├── Dockerfile
└── README.md
```

---

## Running the App Locally (Web Mode)

**Requirements:** Python 3.11+ recommended, Tesseract OCR installed (for Amex's scanned-PDF fallback).

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000** (or the port shown in the terminal) in your browser.

---

## Running via Docker

```bash
docker build -t invoice-extractor .
docker run -p 8080:8080 invoice-extractor
```

Open **http://localhost:8080**.

---

## Deploying to Render

1. Push your project to a GitHub repository.
2. Go to [render.com](https://render.com) → log in with GitHub.
3. **New +** → **Web Service** → select your repo.
4. Render auto-detects the `Dockerfile` → environment = **Docker**.
5. Choose the **Free** instance type.
6. Leave build/start commands blank (the Dockerfile's `CMD` handles it, and Render sets `$PORT` automatically).
7. Click **Create Web Service** and wait for the build to finish.
8. Every `git push` to the connected branch auto-redeploys.

**Free tier note:** the service spins down after ~15 minutes idle; the next request takes 30–60 seconds to wake it back up.

---

## Building the Desktop App (.exe)

This packages the app into a single native Windows application — no browser, no console window, no Python install required on the target machine.

**1. Install desktop-only dependencies:**
```bash
pip install -r requirements-desktop.txt
```
(This adds `pyinstaller` and `pywebview` on top of the base requirements.)

**2. Test it first, without building:**
```bash
python desktop.py
```
A native app window should open directly with the app inside it. If this works, the exe will work too.

**3. Build the exe:**
```bash
pyinstaller --onefile --windowed --add-data "app/static;app/static" --name InvoiceExtractor desktop.py
```

- `--onefile` bundles everything into a single `.exe`
- `--windowed` suppresses the console/command-prompt window
- `--add-data` packages the frontend files (HTML/CSS/JS) into the build

**4. Find and run it:**
```
dist\InvoiceExtractor.exe
```
Double-click it — a standalone app window opens directly, with no browser tab or terminal involved.

**Known limitation:** Tesseract OCR (used only for Amex's scanned-PDF fallback) is a separate native program and can't be bundled by PyInstaller. Any machine running the `.exe` still needs Tesseract installed separately if you expect scanned Amex invoices — otherwise text-based PDFs (the majority) work with no extra setup.

---

## Where Data Is Stored

- Generated `.xlsx` files are written to a temporary system folder (`%TEMP%\pdf_extractor_outputs` on Windows) and served for download from there.
- The **Clear Cache** button in the app header deletes these files and resets active sessions on demand.
- No invoice data is sent anywhere outside your own machine or your own deployed instance — extraction runs entirely server-side, locally.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ImportError: DLL load failed while importing _extra` (Windows, PyMuPDF) | Already resolved — the project uses `pypdfium2` instead of `fitz`/PyMuPDF, which doesn't hit this Windows DLL issue. |
| OCR fails for Amex PDFs | Confirm Tesseract is installed and discoverable (`tesseract_config.py` auto-detects common paths; check console output for a warning). |
| Render build fails | Check the build logs on the Render dashboard — usually a missing dependency or a typo in `requirements.txt`. |
| Exe won't start / missing module error | Rebuild with explicit `--hidden-import` flags for the missing `uvicorn`/`fastapi` submodule named in the error. |

---

**© Latish** — Invoice Extractor
