import os
import time
import cv2
import numpy as np
from paddleocr import TextDetection
import importlib

_rs = importlib.import_module("NisabaـOCRـfunctions")
MIN_SIZE_RATIO = _rs.get_setting("words.min_size_ratio", 0.40)
ATTACH_GAP_RATIO = _rs.get_setting("words.attach_gap_ratio", 0.30)

PUNCT_LIKE = set(".,،؛;؟?!:…")


def get_line_components(line_gray, min_area_ratio=0.0008):
    h, w = line_gray.shape[:2]
    if h < 5 or w < 5:
        return []

    _, binary = cv2.threshold(
        line_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    noise_k = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, noise_k)

    vert_size = max(2, h // 8)
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vert_size))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, vert_kernel)

    horiz_size = max(2, h // 12)
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (horiz_size, 1))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, horiz_kernel)

    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    min_area = max(3, int(h * w * min_area_ratio))
    comps = []
    for i in range(1, num_labels):
        x, y, cw, ch, area = stats[i]
        if area < min_area or cw < 1 or ch < 1:
            continue
        comps.append((int(x), int(y), int(x + cw), int(y + ch)))

    comps.sort(key=lambda c: c[0])
    return comps


def compute_gaps(comps):
    gaps = []
    for i in range(1, len(comps)):
        gap = comps[i][0] - comps[i - 1][2]
        if gap > 0:
            gaps.append(float(gap))
    return gaps


def compute_word_threshold(all_gaps, all_line_heights):
    avg_h = float(np.mean(all_line_heights)) if all_line_heights else 20.0
    min_thresh = max(3.0, avg_h * 0.15)
    max_thresh = max(min_thresh + 1.0, avg_h * 0.80)

    if len(all_gaps) < 4:
        return min_thresh

    gaps_arr = np.array(all_gaps, dtype=np.float32)
    positive = gaps_arr[gaps_arr > 0]
    if len(positive) < 3:
        return min_thresh

    try:
        from skimage.filters import threshold_otsu
        otsu_val = float(threshold_otsu(positive))
    except Exception:
        otsu_val = float(np.median(positive))

    thresh = max(min_thresh, min(otsu_val, max_thresh))

    return thresh


def merge_components_into_words(comps, gap_threshold):
    if not comps:
        return []

    words = []
    current = list(comps[0])
    for c in comps[1:]:
        gap = c[0] - current[2]
        if gap > gap_threshold:
            words.append(tuple(current))
            current = list(c)
        else:
            current[2] = max(current[2], c[2])
            current[1] = min(current[1], c[1])
            current[3] = max(current[3], c[3])
    words.append(tuple(current))
    return words


def compute_pitches(sorted_line_boxes):
    pitches = []
    for i in range(len(sorted_line_boxes) - 1):
        y_cur = sorted_line_boxes[i][1]
        y_next = sorted_line_boxes[i + 1][1]
        pitches.append(max(1, y_next - y_cur))
    return pitches


def detect_paragraph_breaks(sorted_line_boxes, k=2.5):
    if len(sorted_line_boxes) < 3:
        return {}

    pitches = compute_pitches(sorted_line_boxes)
    if len(pitches) < 2:
        return {}

    pitches_arr = np.array(pitches, dtype=np.float32)
    median_pitch = float(np.median(pitches_arr))
    if median_pitch <= 0:
        return {}

    deviations = np.abs(pitches_arr - median_pitch)
    mad = float(np.median(deviations))
    if mad < 1.0:
        mad = median_pitch * 0.10

    threshold = median_pitch + k * mad

    breaks = {}
    for i, pitch in enumerate(pitches):
        if pitch > threshold:
            extra = pitch - median_pitch
            n_breaks = max(1, int(round(extra / median_pitch)))
            breaks[i] = n_breaks

    return breaks


def absorb_small_words(word_boxes, line_h, median_size):
    if not word_boxes:
        return []

    min_allowed = median_size * MIN_SIZE_RATIO
    max_attach_gap = line_h * ATTACH_GAP_RATIO

    words = [list(w) for w in word_boxes]

    merged = []

    for i, w in enumerate(words):
        wx1, wy1, wx2, wy2 = w
        word_w = wx2 - wx1
        word_h = wy2 - wy1
        word_size = max(word_w, word_h)

        is_small = word_size < min_allowed

        if not is_small:
            merged.append(w)
            continue

        if not merged:
            merged.append(w)
            continue

        prev = merged[-1]

        gap = prev[0] - wx2

        if gap < max_attach_gap:
            merged[-1][0] = min(prev[0], wx1)
            merged[-1][1] = min(prev[1], wy1)
            merged[-1][2] = max(prev[2], wx2)
            merged[-1][3] = max(prev[3], wy2)
            continue
        else:
            merged.append(w)
            continue

    return [tuple(w) for w in merged]


def process_photos_with_paddleocr_words():
    input_dir = "1-cleaned photo"
    output_dir = "2-words"

    os.makedirs(output_dir, exist_ok=True)
    if not os.path.exists(input_dir):
        return

    try:
        detector = TextDetection(model_name="PP-OCRv6_small_det")
    except Exception:
        raise

    files = sorted([
        f for f in os.listdir(input_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp'))
    ])
    if not files:
        return

    all_gaps = []
    all_line_heights = []
    cached = []

    total_start = time.time()

    for index, file_name in enumerate(files, start=1):
        image_path = os.path.join(input_dir, file_name)
        image = cv2.imread(image_path)
        if image is None:
            cached.append((file_name, []))
            continue

        h_orig, w_orig = image.shape[:2]

        try:
            output = detector.predict(image_path, batch_size=1)
            result = output[0]
            line_polys = result["dt_polys"]
        except Exception:
            cached.append((file_name, []))
            continue

        if line_polys is None or len(line_polys) == 0:
            cached.append((file_name, []))
            continue

        line_polys_sorted = sorted(
            line_polys,
            key=lambda p: float(np.array(p, dtype=np.float32)[:, 1].min())
        )

        lines_info = []
        for poly in line_polys_sorted:
            pts = np.array(poly, dtype=np.int32)
            lx, ly, lw, lh = cv2.boundingRect(pts)
            if lw < 5 or lh < 5:
                continue

            x_min = max(0, lx)
            y_min = max(0, ly)
            x_max = min(w_orig, lx + lw)
            y_max = min(h_orig, ly + lh)
            if x_max - x_min < 5 or y_max - y_min < 5:
                continue

            line_crop = image[y_min:y_max, x_min:x_max]
            if line_crop.size == 0:
                continue

            line_gray = cv2.cvtColor(line_crop, cv2.COLOR_BGR2GRAY)
            comps = get_line_components(line_gray)
            if not comps:
                continue

            gaps = compute_gaps(comps)
            all_gaps.extend(gaps)
            all_line_heights.append(y_max - y_min)

            lines_info.append(((x_min, y_min, x_max, y_max), comps))

        cached.append((file_name, lines_info))

    global_threshold = compute_word_threshold(all_gaps, all_line_heights)

    all_word_sizes = []
    for file_name, lines_info in cached:
        for (x_min, y_min, x_max, y_max), comps in lines_info:
            word_boxes = merge_components_into_words(comps, global_threshold)
            for (wx1, wy1, wx2, wy2) in word_boxes:
                w = wx2 - wx1
                h = wy2 - wy1
                all_word_sizes.append(max(w, h))

    if all_word_sizes:
        median_size = float(np.median(all_word_sizes))
    else:
        median_size = 0.0

    total_words = 0
    total_absorbed = 0

    for index, (file_name, lines_info) in enumerate(cached, start=1):
        if not lines_info:
            continue

        image_path = os.path.join(input_dir, file_name)
        image = cv2.imread(image_path)
        if image is None:
            continue

        h_orig, w_orig = image.shape[:2]
        base_name = os.path.splitext(file_name)[0]
        words_count = 0
        absorbed_here = 0

        line_boxes_sorted = [bbox for bbox, _ in lines_info]
        para_breaks = detect_paragraph_breaks(line_boxes_sorted)

        for line_idx, ((x_min, y_min, x_max, y_max), comps) in enumerate(lines_info):
            word_boxes = merge_components_into_words(comps, global_threshold)
            word_boxes = sorted(word_boxes, key=lambda w: -w[0])

            line_h = y_max - y_min
            before_count = len(word_boxes)
            word_boxes = absorb_small_words(word_boxes, line_h, median_size)
            absorbed_here += before_count - len(word_boxes)

            n_breaks_after = para_breaks.get(line_idx, 0)
            pad = max(6, int(line_h * 0.15))

            for word_idx, (wx1, wy1, wx2, wy2) in enumerate(word_boxes):
                abs_x_min = max(0, x_min + wx1 - pad)
                abs_x_max = min(w_orig, x_min + wx2 + pad)
                abs_y_min = max(0, y_min + wy1 - pad)
                abs_y_max = min(h_orig, y_min + wy2 + pad)
                if abs_x_max <= abs_x_min or abs_y_max <= abs_y_min:
                    continue

                cropped = image[abs_y_min:abs_y_max, abs_x_min:abs_x_max]
                if cropped.size == 0:
                    continue

                padded = cv2.copyMakeBorder(
                    cropped,
                    top=pad, bottom=pad, left=pad, right=pad,
                    borderType=cv2.BORDER_CONSTANT,
                    value=[255, 255, 255]
                )

                is_last_word = (word_idx == len(word_boxes) - 1)
                if is_last_word and n_breaks_after > 0:
                    marker = f"__BRK{n_breaks_after}__"
                else:
                    marker = ""

                output_path = os.path.join(
                    output_dir,
                    f"{base_name}_word_{words_count:04d}{marker}.png"
                )
                cv2.imwrite(output_path, padded)
                words_count += 1

        total_words += words_count
        total_absorbed += absorbed_here

    total_elapsed = time.time() - total_start
    avg = total_elapsed / len(files) if files else 0


if __name__ == "__main__":
    process_photos_with_paddleocr_words()