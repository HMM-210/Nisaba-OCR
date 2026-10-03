import os
import cv2
import pytesseract
from pytesseract import Output
import importlib

rs = importlib.import_module("NisabaـOCRـfunctions")
parallel = rs.get_parallel()

ENGINE_NAME = "tesseract"
ACCEPT_THRESHOLD = rs.get_setting("thresholds.tesseract", 0.90)
IS_LAST_ENGINE = False


def recognize_word(image_path):
    image = cv2.imread(image_path)
    if image is None:
        return "", 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    try:
        data = pytesseract.image_to_data(
            gray, lang="ara", config="--psm 7", output_type=Output.DICT
        )
    except Exception:
        return "", 0.0
    texts, confidences = [], []
    for txt, conf in zip(data["text"], data["conf"]):
        txt = txt.strip()
        conf = float(conf)
        if txt and conf >= 0:
            texts.append(txt)
            confidences.append(conf)
    if not texts:
        return "", 0.0
    final_text = " ".join(texts)
    avg = (sum(confidences) / len(confidences)) / 100.0
    return final_text, avg


def process_word(word_image):
    image_path = os.path.join(rs.WORDS_DIR, word_image)
    text, confidence = recognize_word(image_path)
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
            engine_name=ENGINE_NAME,
            stage_module_path=os.path.abspath(__file__),
            load_func_name=None,
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