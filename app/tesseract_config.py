import shutil
import os
import pytesseract


def configure_tesseract():
    """Auto-detect tesseract binary. Works on Linux (Docker) and Windows (local)."""
    found = shutil.which("tesseract")
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
        return found

    # Common Windows install locations (fallback for local dev)
    windows_candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Users\Infomap\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    ]
    for path in windows_candidates:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return path

    print("⚠ Tesseract not found. OCR fallback (used by Amex) will fail until installed.")
    return None