import os
import sys
import json
import time
import shutil
import argparse
import threading
import importlib.util
from datetime import datetime
import importlib as _imp
import re as _re

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

AR = "\u0640"

CONFIG_DIR = os.path.join(BASE_DIR, "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
RAW_DIR = os.path.join(BASE_DIR, "0-raw photo")

OUTPUT_FOLDERS = [
    "1-cleaned photo",
    "2-words",
    "3-the result",
]

IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff')


STAGES = [
    (f"1{AR}Nisaba{AR}OCR{AR}cleaning.py",
     "تنظيف الصورة", "Cleaning"),
    (f"2{AR}Nisaba{AR}OCR{AR}cut{AR}to{AR}words.py",
     "تقطيع إلى كلمات", "Cut to words"),
    (f"3{AR}Nisaba{AR}OCR{AR}tesseract.py",
     "Tesseract", "Tesseract"),
    (f"4{AR}Nisaba{AR}OCR{AR}arabic{AR}PP-OCRv6{AR}small{AR}rec.py",
     "PP-OCRv6 عربي", "PP-OCRv6"),
    (f"5{AR}Nisaba{AR}OCR{AR}Qari{AR}OCR.py",
     "Qari OCR (VL)", "Qari OCR"),
    (f"6{AR}Nisaba{AR}OCR{AR}align{AR}punct.py",
     "إضافة الترقيم", "Punctuation"),
]


_cfg_lock = threading.Lock()
_pipeline_lock = threading.Lock()


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            c = f.read().strip()
            return json.loads(c) if c else {}
    except Exception:
        return {}


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with _cfg_lock:
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)


def update_status(**kwargs):
    config = load_config()
    status = config.get("status", {})
    status.update(kwargs)
    config["status"] = status
    save_config(config)


def init_status():
    config = load_config()
    if "status" not in config:
        config["status"] = {
            "state": "idle",
            "current_stage": None,
            "stages": [
                {"id": i + 1, "name_ar": ar, "name_en": en,
                 "status": "pending", "elapsed": None}
                for i, (_, ar, en) in enumerate(STAGES)
            ],
            "image": None,
            "started_at": None,
            "finished_at": None,
            "progress": 0,
            "message": "جاهز",
            "stop_requested": False,
            "start_requested": False,
        }
        save_config(config)


def get_first_image():
    if not os.path.isdir(RAW_DIR):
        return None
    for f in sorted(os.listdir(RAW_DIR)):
        if f.lower().endswith(IMAGE_EXTS):
            return f
    return None


def clean_output_folders():
    for folder in OUTPUT_FOLDERS:
        path = os.path.join(BASE_DIR, folder)
        os.makedirs(path, exist_ok=True)
        for name in os.listdir(path):
            fp = os.path.join(path, name)
            try:
                if os.path.isfile(fp) or os.path.islink(fp):
                    os.remove(fp)
                elif os.path.isdir(fp):
                    shutil.rmtree(fp)
            except Exception:
                pass


def get_processor_func(mod):
    func = getattr(mod, "process", None)
    if func:
        return func
    func = getattr(mod, "process_photos_with_paddleocr_words", None)
    if func:
        return func
    for name in dir(mod):
        if name.startswith("process") and callable(getattr(mod, name)):
            return getattr(mod, name)
    return None


def _passthrough_stage_1():
    raw_dir = os.path.join(BASE_DIR, "0-raw photo")
    cleaned_dir = os.path.join(BASE_DIR, "1-cleaned photo")
    os.makedirs(cleaned_dir, exist_ok=True)
    if not os.path.isdir(raw_dir):
        return
    for f in sorted(os.listdir(raw_dir)):
        if not f.lower().endswith(IMAGE_EXTS):
            continue
        src = os.path.join(raw_dir, f)
        dst = os.path.join(cleaned_dir, f"cleaned_{f}")
        try:
            shutil.copy2(src, dst)
        except Exception:
            pass


def _passthrough_stage_2():
    cleaned_dir = os.path.join(BASE_DIR, "1-cleaned photo")
    words_dir = os.path.join(BASE_DIR, "2-words")
    os.makedirs(words_dir, exist_ok=True)
    if not os.path.isdir(cleaned_dir):
        return
    for f in sorted(os.listdir(cleaned_dir)):
        if not f.lower().endswith(IMAGE_EXTS):
            continue
        base = os.path.splitext(f)[0]
        src = os.path.join(cleaned_dir, f)
        dst = os.path.join(words_dir, f"{base}_word_0000.png")
        try:
            shutil.copy2(src, dst)
        except Exception:
            pass


def _passthrough_stage_6():
    results_file = os.path.join(BASE_DIR, "3-the result", "theـresult.json")
    if not os.path.exists(results_file):
        return

    try:
        with open(results_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return

    def widx(name):
        m = _re.search(r"_word_(\d+)", name)
        return int(m.group(1)) if m else 0

    by_source = {}
    for word_img, entry in data.items():
        if word_img.startswith("_"):
            continue
        src = entry.get("source_image", "unknown")
        by_source.setdefault(src, []).append((word_img, entry))

    sources = data.get("_sources", {})
    for src, entries in by_source.items():
        entries.sort(key=lambda x: widx(x[0]))
        words = []
        for _, entry in entries:
            txt = (entry.get("final_text") or "").strip()
            if txt:
                words.append(txt)
        if not words:
            continue
        sources[src] = {
            "punctuated_text": " ".join(words),
            "punctuated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    data["_sources"] = sources
    tmp = results_file + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, results_file)
    except Exception:
        pass


class Pipeline:
    def __init__(self):
        self.running = False

    def run(self, image_name):
        with _pipeline_lock:
            if self.running:
                return
            self.running = True

        try:
            self._run_internal(image_name)
        finally:
            self.running = False

    def _run_internal(self, image_name):
        start = time.time()

        update_status(
            state="processing",
            current_stage=None,
            image=image_name,
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            finished_at=None,
            progress=0,
            message="بدء المعالجة...",
            stop_requested=False,
            stages=[
                {"id": i + 1, "name_ar": ar, "name_en": en,
                 "status": "pending", "elapsed": None}
                for i, (_, ar, en) in enumerate(STAGES)
            ],
        )

        clean_output_folders()

        _rs = _imp.import_module("NisabaـOCRـfunctions")

        for i, (filename, ar_name, en_name) in enumerate(STAGES):
            if not _rs.is_stage_enabled(i + 1):
                if i == 0:
                    _passthrough_stage_1()
                elif i == 1:
                    _passthrough_stage_2()
                elif i == 5:
                    _passthrough_stage_6()
                self._set_stage(i, "done", 0.0)
                continue

            if load_config().get("status", {}).get("stop_requested"):
                update_status(
                    state="stopped",
                    message="أُوقف بواسطة المستخدم",
                    finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
                return

            self._set_stage(i, "running")
            update_status(
                current_stage=i + 1,
                progress=int((i / len(STAGES)) * 100),
                message=f"جاري: {ar_name}",
            )

            path = os.path.join(BASE_DIR, filename)
            t0 = time.time()

            if not os.path.exists(path):
                self._set_stage(i, "error", 0.0)
                update_status(
                    state="error",
                    message=f"الملف غير موجود: {filename}",
                    finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
                return

            try:
                mod_name = f"_org_stage_{i}"
                spec = importlib.util.spec_from_file_location(mod_name, path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)

                func = get_processor_func(mod)
                if not func:
                    raise AttributeError(f"لا دالة process في {filename}")

                func()
                elapsed = time.time() - t0
                self._set_stage(i, "done", elapsed)

            except Exception as e:
                elapsed = time.time() - t0
                self._set_stage(i, "error", elapsed)
                update_status(
                    state="error",
                    message=f"{ar_name}: {type(e).__name__}: {e}",
                    finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
                return

        total = time.time() - start
        update_status(
            state="done",
            current_stage=None,
            progress=100,
            message=f"اكتمل في {total:.1f}ث",
            finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _set_stage(self, index, status, elapsed=None):
        config = load_config()
        stages = config.get("status", {}).get("stages", [])
        if index < len(stages):
            stages[index]["status"] = status
            if elapsed is not None:
                stages[index]["elapsed"] = round(elapsed, 2)
            status_obj = config.get("status", {})
            status_obj["stages"] = stages
            config["status"] = status_obj
            save_config(config)


class RawImageHandler(FileSystemEventHandler):
    def __init__(self, pipeline):
        super().__init__()
        self.pipeline = pipeline
        self.last_trigger = 0
        self.debounce = 2.0

    def _maybe_trigger(self, path):
        name = os.path.basename(path)
        if not name.lower().endswith(IMAGE_EXTS):
            return
        now = time.time()
        if now - self.last_trigger < self.debounce:
            return
        self.last_trigger = now
        time.sleep(1)
        threading.Thread(
            target=self.pipeline.run, args=(name,), daemon=True
        ).start()

    def on_created(self, event):
        if not event.is_directory:
            self._maybe_trigger(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._maybe_trigger(event.dest_path)


def watch_forever(pipeline):
    if not HAS_WATCHDOG:
        return
    os.makedirs(RAW_DIR, exist_ok=True)
    handler = RawImageHandler(pipeline)
    observer = Observer()
    observer.schedule(handler, RAW_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
            status = load_config().get("status", {})
            if status.get("start_requested"):
                config = load_config()
                config["status"]["start_requested"] = False
                save_config(config)
                img = get_first_image()
                if img:
                    threading.Thread(
                        target=pipeline.run, args=(img,), daemon=True
                    ).start()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def main():
    parser = argparse.ArgumentParser(description="Nisaba OCR Organizer")
    parser.add_argument("--once", action="store_true",
                        help="شغّل مرة واحدة ثم اخرج")
    parser.add_argument("--now", action="store_true",
                        help="شغّل فوراً بلا انتظار (لا يراقب)")
    args = parser.parse_args()

    init_status()
    pipeline = Pipeline()

    if args.now:
        img = get_first_image()
        if not img:
            return
        pipeline.run(img)
        return

    if args.once:
        img = get_first_image()
        if img:
            pipeline.run(img)
            return
        if not HAS_WATCHDOG:
            return
        handler = RawImageHandler(pipeline)
        observer = Observer()
        observer.schedule(handler, RAW_DIR, recursive=False)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
        return

    watch_forever(pipeline)


if __name__ == "__main__":
    main()