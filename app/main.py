import os
import uuid
import time
import shutil
import tempfile
from typing import List
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.tesseract_config import configure_tesseract
from app.excel_builder import build_excel

from app.extractors.airplay import extract_airplay_pdf, AIRPLAY_COLUMNS
from app.extractors.amex import extract_amex_pdf, AMEX_COLUMNS
from app.extractors.novel import extract_novel_pdf, NOVEL_COLUMNS
from app.extractors.pinelabs import extract_pinelabs_pdf, PINELABS_COLUMNS
from app.extractors.aerom import extract_aerom_pdf, AEROM_COLUMNS


configure_tesseract()

app = FastAPI(title="PDF Invoice Extractor")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "pdf_extractor_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# session_id -> {"path": ..., "filename": ..., "created": ...}
SESSIONS = {}
SESSION_TTL_SECONDS = 3600  # 1 hour


CLIENT_CONFIG = {
    "amex": {
        "label": "Amex",
        "mode": "single",       # one dict per pdf
        "extract": extract_amex_pdf,
        "columns": AMEX_COLUMNS,
        "filename_key": "Filename",
        "output_name": "amex_output.xlsx",
    },
    "airplay": {
        "label": "Airplay",
        "mode": "multi",        # list of dicts per pdf, already tagged
        "extract": extract_airplay_pdf,
        "columns": AIRPLAY_COLUMNS,
        "filename_key": "Source File",
        "output_name": "airplay_output.xlsx",
    },
    "novel": {
        "label": "Novel",
        "mode": "single",
        "extract": extract_novel_pdf,
        "columns": NOVEL_COLUMNS,
        "filename_key": "File Name",
        "output_name": "novel_output.xlsx",
    },
    "pinelabs": {
        "label": "Pine Labs",
        "mode": "multi",
        "extract": extract_pinelabs_pdf,
        "columns": PINELABS_COLUMNS,
        "filename_key": "Filename",
        "output_name": "pinelabs_output.xlsx",
    },
    "aerom": {
        "label": "Aerom",
        "mode": "single",
        "extract": extract_aerom_pdf,
        "columns": AEROM_COLUMNS,
        "filename_key": "File Name",
        "output_name": "aerom_output.xlsx",
    },
}


def cleanup_old_sessions():
    now = time.time()
    expired = [sid for sid, s in SESSIONS.items() if now - s["created"] > SESSION_TTL_SECONDS]
    for sid in expired:
        try:
            os.remove(SESSIONS[sid]["path"])
        except OSError:
            pass
        SESSIONS.pop(sid, None)


@app.get("/api/clients")
def list_clients():
    return {key: {"label": cfg["label"]} for key, cfg in CLIENT_CONFIG.items()}


@app.post("/api/process/{client}")
async def process_pdfs(client: str, files: List[UploadFile] = File(...)):
    cleanup_old_sessions()

    if client not in CLIENT_CONFIG:
        raise HTTPException(status_code=404, detail=f"Unknown client '{client}'.")

    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    cfg = CLIENT_CONFIG[client]
    all_records = []
    errors = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        for upload in files:
            if not upload.filename.lower().endswith(".pdf"):
                errors.append({"file": upload.filename, "error": "Not a PDF file."})
                continue

            tmp_path = os.path.join(tmp_dir, upload.filename)
            try:
                with open(tmp_path, "wb") as f:
                    shutil.copyfileobj(upload.file, f)

                result = cfg["extract"](tmp_path)

                if cfg["mode"] == "single":
                    result[cfg["filename_key"]] = upload.filename
                    if not any(str(v).strip() for k, v in result.items() if k != cfg["filename_key"]):
                        errors.append({"file": upload.filename, "error": "No recognizable fields found."})
                        continue
                    all_records.append(result)
                else:
                    if not result:
                        errors.append({"file": upload.filename, "error": "No line items found."})
                        continue
                    all_records.extend(result)

            except Exception as e:
                errors.append({"file": upload.filename, "error": str(e)})

        if not all_records:
            raise HTTPException(
                status_code=422,
                detail={"message": "Extraction failed for all files.", "errors": errors}
            )

        session_id = str(uuid.uuid4())
        output_path = os.path.join(OUTPUT_DIR, f"{session_id}.xlsx")
        df = build_excel(all_records, cfg["columns"], output_path)

    SESSIONS[session_id] = {
        "path": output_path,
        "filename": cfg["output_name"],
        "created": time.time(),
    }

    preview_rows = df.head(200).fillna('').to_dict(orient="records")

    return JSONResponse({
        "session_id": session_id,
        "client": client,
        "filename": cfg["output_name"],
        "columns": cfg["columns"],
        "rows": preview_rows,
        "row_count": len(df),
        "preview_truncated": len(df) > 200,
        "errors": errors,
    })


@app.get("/api/download/{session_id}")
def download(session_id: str):
    session = SESSIONS.get(session_id)
    if not session or not os.path.exists(session["path"]):
        raise HTTPException(status_code=404, detail="File not found or session expired. Please re-run extraction.")

    return FileResponse(
        path=session["path"],
        filename=session["filename"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )



# Serve the frontend
app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "app", "static"), html=True), name="static")