import os
import re
import importlib
from paddleocr import TextRecognition

rs = importlib.import_module("NisabaـOCRـfunctions")
parallel = rs.get_parallel()

ENGINE_NAME = "arabic_ppocrv6_small_rec"
PARALLEL_NAME = "ppocrv6"
ACCEPT_THRESHOLD = rs.get_setting("thresholds.ppocrv6", 0.85)
IS_LAST_ENGINE = False
MODEL_DIR = "models/arabic_rec"

_model = None


def pred_reverse(pred):
    out, cur = [], ""
    for c in pred:
        if not re.search(r"[a-zA-Z0-9 :*./%+-]", c):
            if cur:
                out.append(cur)
            out.append(c)
            cur = ""
        else:
            cur += c
    if cur:
        out.append(cur)
    return "".join(out[::-1])


def load_model():
    global _model
    if _model is None:
        _model = TextRecognition(
            model_name="PP-OCRv6_small_rec", model_dir=MODEL_DIR
        )
    return _model


def process_word(word_image):
    model = load_model()
    image_path = os.path.join(rs.WORDS_DIR, word_image)
    try:
        output = model.predict(input=image_path, batch_size=1)
        result = list(output)[0]
        raw_text = result["rec_text"]
        confidence = float(result["rec_score"])
        text = pred_reverse(raw_text) if raw_text else ""
    except Exception:
        text, confidence = "", 0.0
    if confidence >= ACCEPT_THRESHOLD:
        decision = "accepted"
    elif IS_LAST_ENGINE:
        decision = "failed"
    else:
        decision = "escalate"
    return (text, confidence, decision)


def process():
    try:
        rs.ensure_setup()
        pending = rs.get_pending_word_images()
        if not pending:
            return
        total = len(pending)

        counters = {"accepted": 0, "escalated": 0, "failed": 0}

        def progress(i, total, item, result):
            if result is None:
                return
            _, _, decision = result
            if decision in counters:
                counters[decision] += 1

        results = parallel.process_parallel(
            items=pending,
            worker_func=process_word,
            engine_name=PARALLEL_NAME,
            stage_module_path=os.path.abspath(__file__),
            model_load_func=load_model,
            load_func_name="load_model",
            progress_cb=progress,
        )

        attempts, to_finalize = [], []
        for word_image, result in results:
            if result is None:
                continue
            text, confidence, decision = result
            source_image = word_image.rsplit("_word_", 1)[0]
            attempts.append((word_image, source_image, ENGINE_NAME,
                             text, confidence, decision))
            if decision in ("accepted", "failed"):
                to_finalize.append(word_image)

        rs.record_batch_attempts(attempts)
        for w in to_finalize:
            rs.finalize_word(w)
    finally:
        rs.cleanup_after_stage()


if __name__ == "__main__":
    process()