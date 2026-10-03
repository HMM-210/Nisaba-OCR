import os
import time
import importlib
import cv2
import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

rs = importlib.import_module("NisabaـOCRـfunctions")
parallel = rs.get_parallel()

ENGINE_NAME = "qari_ocr_vl"
PARALLEL_NAME = "qari"
MODEL_DIR = "models/qari_merged_fp16"
ACCEPT_THRESHOLD = rs.get_setting("thresholds.qari", 0.92)
MAX_NEW_TOKENS = rs.get_setting("qari.max_new_tokens", 32)

IS_LAST_ENGINE = True
PROMPT = "Extract the text from this image. Return only the text, nothing else."

MAX_DIM = 640
MIN_DIM = 160

_model = None
_processor = None


def load_model():
    global _model, _processor
    if _model is not None:
        return _model, _processor
    try:
        _model = Qwen2VLForConditionalGeneration.from_pretrained(
            MODEL_DIR, torch_dtype=torch.float16,
            device_map="cpu", low_cpu_mem_usage=True,
        )
    except Exception:
        _model = Qwen2VLForConditionalGeneration.from_pretrained(
            MODEL_DIR, torch_dtype=torch.float32,
            device_map="cpu", low_cpu_mem_usage=True,
        )
    _processor = AutoProcessor.from_pretrained(MODEL_DIR)
    return _model, _processor


def smart_resize(image):
    h, w = image.shape[:2]
    original_size = (h, w)
    longest = max(h, w)
    shortest = min(h, w)
    scale = 1.0
    if longest > MAX_DIM:
        scale = MAX_DIM / longest
    elif shortest < MIN_DIM:
        scale = MIN_DIM / shortest
    if abs(scale - 1.0) > 0.01:
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        image = cv2.resize(image, (new_w, new_h), interpolation=interp)
    if len(image.shape) == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    new_size = image.shape[:2]
    return image, original_size, new_size


def recognize_one(model, processor, image_path):
    image = cv2.imread(image_path)
    if image is None:
        return "", 0.0, (0, 0), (0, 0)
    resized, orig_size, new_size = smart_resize(image)
    tmp_path = image_path + f".qari_tmp_{os.getpid()}.png"
    cv2.imwrite(tmp_path, resized)
    try:
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": f"file://{os.path.abspath(tmp_path)}"},
                {"type": "text", "text": PROMPT},
            ],
        }]
        text = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text], images=image_inputs, videos=video_inputs,
            padding=True, return_tensors="pt",
        )
        with torch.no_grad():
            result = model.generate(
                **inputs, max_new_tokens=MAX_NEW_TOKENS,
                output_scores=True, return_dict_in_generate=True,
            )
        generated_ids = result.sequences
        trimmed = [
            out_ids[len(in_ids):]
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = processor.batch_decode(
            trimmed, skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )[0].strip()
        if result.scores:
            probs_list = []
            for s, tid in zip(result.scores, trimmed[0]):
                p = torch.softmax(s[0], dim=-1)
                probs_list.append(p[tid].item())
            confidence = sum(probs_list) / len(probs_list) if probs_list else 0.0
        else:
            confidence = 0.0
        return output_text, confidence, orig_size, new_size
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


def process_word(word_image):
    model, processor = load_model()
    image_path = os.path.join(rs.WORDS_DIR, word_image)
    t0 = time.time()
    try:
        text, confidence, orig_size, new_size = recognize_one(
            model, processor, image_path
        )
    except Exception:
        text, confidence, orig_size, new_size = "", 0.0, (0, 0), (0, 0)
    elapsed = time.time() - t0
    text = rs.strip_tashkeel(text)
    if confidence >= ACCEPT_THRESHOLD:
        decision = "accepted"
    else:
        decision = "failed" if IS_LAST_ENGINE else "escalate"
    return (text, confidence, decision, elapsed, orig_size, new_size)


def process():
    total = 0
    try:
        rs.ensure_setup()
        pending = rs.get_pending_word_images()
        total = len(pending)
        if total == 0:
            return

        counters = {"accepted": 0, "failed": 0, "escalated": 0}

        def progress(i, total, item, result):
            if result is None or len(result) < 6:
                return
            text, confidence, decision, elapsed, orig_size, new_size = result
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

        attempts = []
        for word_image, result in results:
            if result is None or len(result) < 6:
                continue
            text, confidence, decision, elapsed, orig_size, new_size = result
            source_image = word_image.rsplit("_word_", 1)[0]
            attempts.append((word_image, source_image, ENGINE_NAME,
                             text, confidence, decision))

        rs.record_batch_attempts(attempts)

        for word_image, result in results:
            if result is not None:
                rs.finalize_word(word_image)

    except KeyboardInterrupt:
        pass
    except Exception:
        pass
    finally:
        rs.cleanup_after_stage()


if __name__ == "__main__":
    process()