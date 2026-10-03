import os
import re
import json
import importlib
import subprocess
from collections import Counter

rs = importlib.import_module("NisabaـOCRـfunctions")

ENGINE_NAME = "align_punct_dynamic"

DEFAULT_SYMBOL_MAP = {
    ",": "،",
    ";": "؛",
    "?": "؟",
    "!": "!",
    ":": ":",
    ".": ".",
    "·": ".",
    "•": ".",
    "⁃": ".",
    "‧": ".",
}

ARABIC_PUNCT = set("،؛؟!:«»…")


def is_arabic_char(ch):
    return "\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F"


def is_arabic_digit(ch):
    return ch in "٠١٢٣٤٥٦٧٨٩"


def is_latin_letter(ch):
    return ch.isalpha() and ch.isascii()


def is_arabic_punct(ch):
    return ch in ARABIC_PUNCT


def is_latin_punct(ch):
    return ch in ".,;?!:()[]{}'\""


def is_whitespace(ch):
    return ch.isspace()


def is_suspicious_char(ch):
    if len(ch) != 1:
        return False
    if is_arabic_char(ch):
        return False
    if is_arabic_digit(ch) or ch.isdigit():
        return False
    if is_latin_letter(ch):
        return False
    if is_whitespace(ch):
        return False
    return True


def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            insert = curr[j - 1] + 1
            delete = prev[j] + 1
            replace = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(insert, delete, replace))
        prev = curr
    return prev[-1]


def similarity(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    d = levenshtein(a, b)
    return 1.0 - (d / max(len(a), len(b)))


def dynamic_threshold(word1, word2):
    max_len = max(len(word1), len(word2))
    if max_len <= 3:
        return 0.80
    elif max_len <= 6:
        return 0.75
    else:
        return 0.70


def is_punct_word(word):
    if not word:
        return False

    if all(is_arabic_punct(ch) or is_latin_punct(ch) or is_suspicious_char(ch)
           for ch in word):
        return True

    if word.isdigit() and len(word) <= 2:
        return True
    if all(is_arabic_digit(ch) for ch in word) and len(word) <= 2:
        return True

    return False


def normalize_punct_word(word, symbol_map):
    if not word:
        return None

    if (word.isdigit() or all(is_arabic_digit(ch) for ch in word)) and len(word) <= 2:
        return "..."

    if len(word) == 1:
        ch = word
        if ch in symbol_map:
            return symbol_map[ch]
        if is_arabic_punct(ch):
            return ch
        return None

    result = []
    for ch in word:
        if ch in symbol_map:
            result.append(symbol_map[ch])
        elif is_arabic_punct(ch):
            result.append(ch)
    if result:
        return "".join(result)
    return None


def build_dynamic_symbol_map(text_no_punct, text_with_punct):
    chars_in_1 = set(text_no_punct)

    chars_in_2 = set(text_with_punct)

    new_chars = chars_in_2 - chars_in_1

    dynamic_map = {}

    for src, dst in DEFAULT_SYMBOL_MAP.items():
        if src in chars_in_2:
            dynamic_map[src] = dst

    for ch in new_chars:
        if is_suspicious_char(ch):
            if is_arabic_punct(ch):
                dynamic_map[ch] = ch
            else:
                if ch.isdigit() or is_arabic_digit(ch):
                    dynamic_map[ch] = "..."

    return dynamic_map


def filter_by_frequency(text_with_punct, min_freq=1):
    freq = Counter(c for c in text_with_punct if not c.isspace())
    return freq


def align_words_dynamic(words1, words2, symbol_map, char_freq,
                        min_rare_freq=1):
    i = 0
    j = 0
    marks = []

    while i < len(words1) and j < len(words2):
        w1 = words1[i]
        w2 = words2[j]

        if is_punct_word(w2):
            punct = normalize_punct_word(w2, symbol_map)
            if punct:
                is_standard = all(c in ARABIC_PUNCT or c in ".،؛؟!:" for c in punct)
                if is_standard or char_freq.get(w2, 0) >= min_rare_freq:
                    marks.append((i - 1, punct))
            j += 1
            continue

        sim = similarity(w1, w2)
        threshold = dynamic_threshold(w1, w2)
        if sim >= threshold:
            i += 1
            j += 1
            continue

        best_j = None
        best_sim = 0.0
        for k in range(j + 1, min(j + 4, len(words2))):
            s = similarity(w1, words2[k])
            dyn_thr = dynamic_threshold(w1, words2[k])
            if s >= dyn_thr and s > best_sim:
                best_sim = s
                best_j = k

        if best_j is not None:
            for k in range(j, best_j):
                punct = normalize_punct_word(words2[k], symbol_map)
                if punct:
                    is_standard = all(c in ARABIC_PUNCT or c in ".،؛؟!:" for c in punct)
                    if is_standard or char_freq.get(words2[k], 0) >= min_rare_freq:
                        marks.append((i - 1, punct))
            j = best_j
            continue

        i += 1

    while j < len(words2):
        punct = normalize_punct_word(words2[j], symbol_map)
        if punct:
            marks.append((len(words1) - 1, punct))
        j += 1

    return marks


def apply_marks_to_words(words, marks):
    by_index = {}
    for idx, p in marks:
        by_index.setdefault(idx, []).append(p)

    result = []

    if -1 in by_index:
        result.append("".join(by_index[-1]))
        result.append(" ")

    for i, w in enumerate(words):
        result.append(w)
        if i in by_index:
            result.append("".join(by_index[i]))
        result.append(" ")

    text = "".join(result).strip()

    text = re.sub(r"\?\?+", "؟", text)
    text = re.sub(r"!!+", "!", text)
    text = re.sub(r"،،+", "،", text)
    text = re.sub(r"::+", ":", text)
    text = re.sub(r"\.\.\.\.+", "...", text)
    text = re.sub(r"\.\.(?!\.)", ".", text)

    text = text.rstrip("|\\/*+=<>@#$%^&_~`")

    return text


def run_tesseract_full(image_path):
    try:
        result = subprocess.run(
            ["tesseract", image_path, "stdout", "-l", "ara", "--psm", "6"],
            capture_output=True, text=True, timeout=120,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def process():
    rs.ensure_setup()

    if not os.path.exists(rs.RESULTS_FILE):
        return

    with open(rs.RESULTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        return

    by_source = {}
    for word_img, entry in data.items():
        src = entry.get("source_image", "unknown")
        by_source.setdefault(src, []).append((word_img, entry))

    cleaned_dir = "1-cleaned photo"

    for src in sorted(by_source.keys()):
        def widx(name):
            m = re.search(r"_word_(\d+)", name)
            return int(m.group(1)) if m else 0

        entries = sorted(by_source[src], key=lambda x: widx(x[0]))

        words = []
        for word_img, entry in entries:
            txt = (entry.get("final_text") or "").strip()
            if txt:
                words.append(txt)

        if not words:
            continue

        text_no_punct = " ".join(words)

        image_path = None
        for ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            candidate = os.path.join(cleaned_dir, src + ext)
            if os.path.exists(candidate):
                image_path = candidate
                break

        if not image_path:
            continue

        text_with_punct = run_tesseract_full(image_path)
        if not text_with_punct:
            continue

        words2 = text_with_punct.split()

        symbol_map = build_dynamic_symbol_map(text_no_punct, text_with_punct)

        char_freq = filter_by_frequency(text_with_punct)

        marks = align_words_dynamic(words, words2, symbol_map, char_freq)

        final_text = apply_marks_to_words(words, marks) if marks else text_no_punct

        rs.record_punctuated_text(src, final_text)


if __name__ == "__main__":
    process()