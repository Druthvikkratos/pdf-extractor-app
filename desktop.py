import os
import sys
import threading
import time

import uvicorn
import webview

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

from app.main import app

HOST = "127.0.0.1"
PORT = 8080


def run_server():
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    time.sleep(1.0)  # give uvicorn a moment to bind the port

    webview.create_window(
        "Invoice Extractor",
        f"http://{HOST}:{PORT}",
        width=1000,
        height=750,
        resizable=True,
    )
    webview.start()