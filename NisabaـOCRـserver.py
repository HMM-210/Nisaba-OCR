import os
import sys
import json
import time
import shutil
import asyncio
import threading
import subprocess
import webbrowser
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import (
    FileResponse, JSONResponse, StreamingResponse
)
import uvicorn


BASE_DIR = Path(__file__).parent.resolve()
os.chdir(BASE_DIR)

CONFIG_FILE = BASE_DIR / "config" / "config.json"
RESULTS_FILE = BASE_DIR / "3-the result" / "theـresult.json"
WEB_DIR = BASE_DIR / "web"
ORGANIZER = BASE_DIR / "NisabaـOCRـorganizer.py"
RAW_DIR = BASE_DIR / "0-raw photo"

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = 8000

IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff')


app = FastAPI(title="Nisaba OCR", docs_url=None, redoc_url=None)

_cfg_lock = threading.Lock()


def load_config():
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            c = f.read().strip()
            return json.loads(c) if c else {}
    except Exception:
        return {}


def save_config(config):
    CONFIG_FILE.parent.mkdir(exist_ok=True)
    with _cfg_lock:
        tmp = str(CONFIG_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)


def update_status(**kwargs):
    with _cfg_lock:
        config = load_config()
        status = config.get("status", {})
        status.update(kwargs)
        config["status"] = status
        tmp = str(CONFIG_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)


def get_punctuated_texts():
    if not RESULTS_FILE.exists():
        return {}
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("_sources", {})
    except Exception:
        return {}


@app.get("/api/status")
def api_status():
    return load_config().get("status", {})


@app.get("/api/result")
def api_result():
    sources = get_punctuated_texts()
    return {"sources": sources}


@app.post("/api/start")
def api_start():
    update_status(start_requested=True, stop_requested=False)
    return {"ok": True}


@app.post("/api/stop")
def api_stop():
    update_status(stop_requested=True)
    return {"ok": True}


@app.post("/api/clear")
def api_clear():
    for folder in ["0-raw photo", "1-cleaned photo", "2-words", "3-the result"]:
        p = BASE_DIR / folder
        p.mkdir(exist_ok=True)
        for f in p.iterdir():
            try:
                if f.is_file():
                    f.unlink()
                elif f.is_dir():
                    shutil.rmtree(f)
            except Exception:
                pass
    update_status(state="idle", message="تم المسح", progress=0,
                  current_stage=None,
                  stages=[])
    return {"ok": True}


@app.get("/api/settings")
def api_settings_get():
    config = load_config()
    return config.get("settings", {})


@app.post("/api/settings")
async def api_settings_post(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)

    with _cfg_lock:
        config = load_config()
        settings = config.get("settings", {})
        if isinstance(data, dict):
            settings.update(data)
        config["settings"] = settings

        tmp = str(CONFIG_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)

    return {"ok": True, "settings": settings}


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    name = file.filename or "uploaded.png"
    name = "".join(c for c in name if c not in "/\\:*?\"<>|")
    if not name.lower().endswith(IMAGE_EXTS):
        return JSONResponse(
            {"ok": False, "error": "صيغة غير مدعومة"},
            status_code=400,
        )

    RAW_DIR.mkdir(exist_ok=True)

    for f in RAW_DIR.iterdir():
        if f.is_file() and f.name.lower().endswith(IMAGE_EXTS):
            try:
                f.unlink()
            except OSError:
                pass

    target = RAW_DIR / name
    with open(target, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    update_status(start_requested=True, stop_requested=False)

    return {"ok": True, "name": name}


@app.get("/api/stream")
async def api_stream(request: Request):
    async def gen():
        last = None
        yield ": connected\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                status = load_config().get("status", {})
                s = json.dumps(status, ensure_ascii=False)
                if s != last:
                    last = s
                    yield f"data: {s}\n\n"
            except Exception:
                pass
            await asyncio.sleep(0.4)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/style.css")
def css():
    return FileResponse(WEB_DIR / "style.css", media_type="text/css")


@app.get("/app.js")
def js():
    return FileResponse(WEB_DIR / "app.js",
                        media_type="application/javascript")


_organizer_proc = None
_organizer_lock = threading.Lock()


def start_organizer():
    global _organizer_proc
    with _organizer_lock:
        if _organizer_proc and _organizer_proc.poll() is None:
            return
        if not ORGANIZER.exists():
            return
        _organizer_proc = subprocess.Popen(
            [sys.executable, str(ORGANIZER)],
            cwd=str(BASE_DIR),
        )


def stop_organizer():
    global _organizer_proc
    with _organizer_lock:
        if _organizer_proc and _organizer_proc.poll() is None:
            try:
                _organizer_proc.terminate()
                _organizer_proc.wait(timeout=5)
            except Exception:
                try:
                    _organizer_proc.kill()
                except Exception:
                    pass
        _organizer_proc = None


def main():
    if not WEB_DIR.exists():
        return

    start_organizer()

    def open_browser():
        if HOST == "0.0.0.0":
            return
        time.sleep(1.2)
        try:
            webbrowser.open(f"http://{HOST}:{PORT}")
        except Exception:
            pass
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
    finally:
        stop_organizer()


if __name__ == "__main__":
    main()