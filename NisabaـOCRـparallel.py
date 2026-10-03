import os
import gc
import json
import time
import multiprocessing as mp
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


CONFIG_DIR = "config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CPU_CAP = os.cpu_count() or 4

WORKER_MB = {
    "tesseract": 500,
    "ppocrv6": 1000,
    "qari": 2500,
}


_json_lock = threading.Lock()

def get_json_lock():
    return _json_lock


def available_ram_mb():
    if not HAS_PSUTIL:
        return 8000.0
    return psutil.virtual_memory().available / (1024 * 1024)


def load_config():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)


def get_saved_workers(engine_name):
    config = load_config()
    if engine_name in config:
        return config[engine_name].get("workers")
    return None


def save_workers(engine_name, workers, worker_mb, available_mb):
    config = load_config()
    config[engine_name] = {
        "workers": workers,
        "worker_mb": worker_mb,
        "available_mb": int(available_mb),
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_config(config)


def calculate_workers(engine_name):
    worker_mb = WORKER_MB.get(engine_name, 1000)
    avail = available_ram_mb()

    if avail <= 0:
        workers = 1
    else:
        workers = int(avail / worker_mb)

    workers = max(1, min(workers, CPU_CAP))

    save_workers(engine_name, workers, worker_mb, avail)
    return workers


def get_workers(engine_name):
    w = get_saved_workers(engine_name)
    if w is not None:
        return w
    return calculate_workers(engine_name)


_GLOBAL = {}


def _init_child(stage_module_path, engine_name, load_func_name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        f"_stage_{engine_name}", stage_module_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _GLOBAL["module"] = mod

    if load_func_name:
        load_func = getattr(mod, load_func_name, None)
        if load_func:
            load_func()


def _run_one(item):
    mod = _GLOBAL.get("module")
    if mod is None:
        return (item, None)
    try:
        return (item, mod.process_word(item))
    except Exception:
        return (item, None)


def _process_with_multiprocessing(items, stage_module_path, engine_name,
                                   load_func_name, workers, progress_cb):
    results = {}
    done = 0

    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_child,
        initargs=(stage_module_path, engine_name, load_func_name),
    ) as ex:
        futures = {ex.submit(_run_one, item): item for item in items}
        for f in as_completed(futures):
            item = futures[f]
            try:
                _, result = f.result()
            except Exception:
                result = None
            results[item] = result
            done += 1
            if progress_cb and result is not None:
                progress_cb(done, len(items), item, result)

    return [(item, results.get(item)) for item in items]


def process_parallel(items, worker_func, engine_name,
                     stage_module_path=None,
                     model_load_func=None,
                     load_func_name=None,
                     progress_cb=None):
    if not items:
        return []

    total = len(items)
    workers = get_workers(engine_name)

    if workers <= 1 or stage_module_path is None:
        results = []
        for i, item in enumerate(items, 1):
            try:
                r = worker_func(item)
            except Exception:
                r = None
            results.append((item, r))
            if progress_cb and r is not None:
                progress_cb(i, total, item, r)
        return results

    try:
        results = _process_with_multiprocessing(
            items, stage_module_path, engine_name,
            load_func_name, workers, progress_cb
        )
    except Exception:
        results = []
        for i, item in enumerate(items, 1):
            try:
                r = worker_func(item)
            except Exception:
                r = None
            results.append((item, r))
            if progress_cb and r is not None:
                progress_cb(i, total, item, r)

    return results


def cleanup_after_stage():
    gc.collect()