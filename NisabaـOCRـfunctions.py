import os
import json
import time
import re as _re
import threading

RESULTS_DIR = "3-the result"
RESULTS_FILE = os.path.join(RESULTS_DIR, "theـresult.json")
WORDS_DIR = "2-words"

try:
    import importlib as _importlib
    _parallel = _importlib.import_module("NisabaـOCRـparallel")
    _json_lock = _parallel.get_json_lock()
except Exception:
    _parallel = None
    _json_lock = threading.Lock()


def ensure_setup():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False)


def _atomic_write(data):
    tmp_path = RESULTS_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, RESULTS_FILE)


def _load():
    if not os.path.exists(RESULTS_FILE):
        return {}
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
        return json.loads(content) if content else {}


def record_attempt(word_image, source_image, engine, text, confidence, decision):
    with _json_lock:
        _record_internal(word_image, source_image, engine, text, confidence, decision)


def _record_internal(word_image, source_image, engine, text, confidence, decision):
    data = _load()
    entry = data.get(word_image, {
        "source_image": source_image,
        "final_text": None,
        "final_status": "pending",
        "attempts": []
    })
    entry["attempts"].append({
        "engine": engine,
        "text": text,
        "confidence": confidence,
        "decision": decision,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    if decision == "accepted":
        entry["final_text"] = text
        entry["final_status"] = "accepted"
    elif decision == "failed":
        entry["final_text"] = text
        entry["final_status"] = "failed_final"
    else:
        entry["final_status"] = "escalated"

    data[word_image] = entry
    _atomic_write(data)


def record_batch_attempts(attempts):
    with _json_lock:
        data = _load()
        for word_image, source_image, engine, text, confidence, decision in attempts:
            entry = data.get(word_image, {
                "source_image": source_image,
                "final_text": None,
                "final_status": "pending",
                "attempts": []
            })
            entry["attempts"].append({
                "engine": engine,
                "text": text,
                "confidence": confidence,
                "decision": decision,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            if entry["final_status"] not in ("accepted", "failed_final"):
                if decision == "accepted":
                    entry["final_text"] = text
                    entry["final_status"] = "accepted"
                elif decision == "failed":
                    entry["final_text"] = text
                    entry["final_status"] = "failed_final"
                else:
                    entry["final_status"] = "escalated"
            data[word_image] = entry
        _atomic_write(data)


def get_pending_word_images():
    if not os.path.exists(WORDS_DIR):
        return []
    return sorted([
        f for f in os.listdir(WORDS_DIR)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ])


def finalize_word(word_image):
    path = os.path.join(WORDS_DIR, word_image)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def parse_brk_from_filename(filename):
    if not filename:
        return 0
    m = _re.search(r"__BRK(\d+)__", filename)
    return int(m.group(1)) if m else 0


def get_parallel():
    return _parallel


def cleanup_after_stage():
    if _parallel is not None:
        try:
            _parallel.cleanup_after_stage()
        except Exception:
            pass
    import gc
    gc.collect()


def strip_tashkeel(text):
    if not text:
        return text
    return _re.sub(r'[\u064B-\u065F\u0670]', '', text)


def get_summary():
    data = _load()
    per_engine_final = {}
    status_counts = {}
    for key, entry in data.items():
        if key.startswith("_"):
            continue
        status = entry.get("final_status", "pending")
        status_counts[status] = status_counts.get(status, 0) + 1
        if entry["attempts"]:
            last_engine = entry["attempts"][-1]["engine"]
            per_engine_final.setdefault(last_engine, 0)
            per_engine_final[last_engine] += 1
    return {
        "total_words": len(data),
        "status_counts": status_counts,
        "stopped_at_engine": per_engine_final
    }


def record_punctuated_text(source_image, punctuated_text):
    with _json_lock:
        data = _load()
        sources = data.get("_sources", {})
        sources[source_image] = {
            "punctuated_text": punctuated_text,
            "punctuated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        data["_sources"] = sources
        _atomic_write(data)


def get_punctuated_text(source_image):
    data = _load()
    return data.get("_sources", {}).get(source_image, {}).get("punctuated_text")

DEFAULT_SETTINGS = {
    "language": "ar",
    "stages_enabled": {"1": True, "2": True, "3": True,
                       "4": True, "5": True, "6": True},
    "thresholds": {"tesseract": 0.90, "ppocrv6": 0.85, "qari": 0.92},
    "qari": {"max_new_tokens": 32},
    "cleaning": {"upscale_factor": 5},
    "words": {"min_size_ratio": 0.40, "attach_gap_ratio": 0.30},
}


def get_settings():
    config = _load_config_file()
    settings = config.get("settings", {})
    merged = {}
    for key, default_val in DEFAULT_SETTINGS.items():
        if isinstance(default_val, dict):
            merged[key] = {**default_val, **settings.get(key, {})}
        else:
            merged[key] = settings.get(key, default_val)
    return merged


def get_setting(path, default=None):
    parts = path.split(".")
    value = get_settings()
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default
    return value


def is_stage_enabled(stage_id):
    return bool(get_setting(f"stages_enabled.{stage_id}", True))


def _load_config_file():
    config_path = os.path.join("config", "config.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}