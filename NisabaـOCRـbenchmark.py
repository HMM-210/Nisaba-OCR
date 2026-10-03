import gc
gc.disable()

import os
import sys
import json
import shutil
import re
import importlib.util

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.path.insert(0, BASE)

RAW = os.path.join(BASE, "0-raw photo")
TEMP = os.path.join(BASE, "_isi_images")
RESULTS = os.path.join(BASE, "3-the result", "theـresult.json")
REPORT_TXT = os.path.join(BASE, "nisaba_isi_report.txt")
REPORT_JSON = os.path.join(BASE, "nisaba_isi_report.json")
N = 50


def normalize(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(
                curr[j - 1] + 1,
                prev[j] + 1,
                prev[j - 1] + (0 if ca == cb else 1)
            ))
        prev = curr
    return prev[-1]


def download_images():
    from datasets import load_dataset

    print("\n[1/4] تحميل مجموعة ISI-PPT...")
    ds = load_dataset("ahmedheakl/arocrbench_isippt")
    split = list(ds.keys())[0]
    n = min(N, len(ds[split]))

    os.makedirs(TEMP, exist_ok=True)
    ground_truth = {}

    for i in range(n):
        item = ds[split][i]
        name = f"isi_{i:04d}.png"
        item["image"].save(os.path.join(TEMP, name))
        ground_truth[name] = normalize(item.get("text", ""))

    print(f"     ✅ {n} صورة محفوظة في {TEMP}")
    return ground_truth


def load_pipeline():
    print("\n[2/4] تحميل Nisaba...")
    spec = importlib.util.spec_from_file_location(
        "organizer", os.path.join(BASE, "NisabaـOCRـorganizer.py")
    )
    organizer = importlib.util.module_from_spec(spec)
    sys.modules["organizer"] = organizer
    spec.loader.exec_module(organizer)
    return organizer.Pipeline()


def process_images(pipeline, ground_truth):
    print("\n[3/4] تشغيل Nisaba على الصور...")
    os.makedirs(RAW, exist_ok=True)

    names = sorted(ground_truth.keys())
    nisaba_results = {}

    for idx, name in enumerate(names, 1):
        print(f"\n  [{idx}/{len(names)}] {name}")

        for f in os.listdir(RAW):
            fp = os.path.join(RAW, f)
            if os.path.isfile(fp):
                try:
                    os.remove(fp)
                except OSError:
                    pass

        shutil.copy2(os.path.join(TEMP, name), os.path.join(RAW, name))

        try:
            pipeline.run(name)
        except Exception as e:
            print(f"     ⚠️ خطأ: {e}")
            nisaba_results[name] = ""
            continue

        if os.path.exists(RESULTS):
            try:
                with open(RESULTS, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sources = data.get("_sources", {})
                if sources:
                    last = list(sources.values())[-1]
                    nisaba_results[name] = normalize(last.get("punctuated_text", ""))
            except Exception:
                nisaba_results[name] = ""

    return nisaba_results


def compute_report(ground_truth, nisaba_results):
    print("\n[4/4] حساب CER وكتابة التقرير...")

    details = []
    total_dist = 0
    total_len = 0
    count = 0

    for name in sorted(ground_truth.keys()):
        gt = ground_truth[name]
        pred = nisaba_results.get(name, "")
        if not gt:
            continue
        d = levenshtein(gt, pred)
        total_dist += d
        total_len += len(gt)
        count += 1
        details.append({
            "image": name,
            "ground_truth": gt,
            "nisaba": pred,
            "cer": round(d / len(gt), 4),
        })

    final_cer = total_dist / total_len if total_len > 0 else 0

    report = {
        "dataset": "ISI-PPT (AROCRBench)",
        "n_images": count,
        "nisaba_cer": round(final_cer, 4),
        "comparison": {
            "Gemini-2.0-Flash": 0.06,
            "GPT-4o": 0.08,
            "GPT-4o-mini": 0.15,
            "Qwen2-VL": 1.03,
            "Nisaba": round(final_cer, 4),
        },
        "details": details,
    }

    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(REPORT_TXT, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("  Nisaba OCR — نتائج ISI-PPT\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"عدد الصور: {count}\n")
        f.write(f"CER Nisaba: {final_cer * 100:.2f}%\n\n")
        f.write("المقارنة مع المنافسين:\n")
        f.write("  Gemini-2.0-Flash : 6.00%\n")
        f.write("  GPT-4o           : 8.00%\n")
        f.write("  GPT-4o-mini      : 15.00%\n")
        f.write("  Qwen2-VL         : 103.00%\n")
        f.write(f"  Nisaba           : {final_cer * 100:.2f}%\n\n")
        f.write("=" * 70 + "\n")
        f.write("  التفاصيل لكل صورة\n")
        f.write("=" * 70 + "\n\n")

        for d in details:
            f.write(f"📷 {d['image']}  (CER: {d['cer'] * 100:.1f}%)\n")
            f.write(f"   الأصل : {d['ground_truth']}\n")
            f.write(f"   Nisaba: {d['nisaba']}\n\n")

    print("\n" + "=" * 60)
    print(f"  CER Nisaba: {final_cer * 100:.2f}%")
    print("=" * 60)
    print(f"  Gemini-2.0-Flash : 6.00%")
    print(f"  GPT-4o           : 8.00%")
    print(f"  GPT-4o-mini      : 15.00%")
    print(f"  Qwen2-VL         : 103.00%")
    print(f"  Nisaba           : {final_cer * 100:.2f}%")
    print(f"\n  التقرير: {REPORT_TXT}")


def main():
    print("=" * 60)
    print("  Nisaba OCR — ISI-PPT Benchmark")
    print("=" * 60)

    ground_truth = download_images()
    pipeline = load_pipeline()
    nisaba_results = process_images(pipeline, ground_truth)
    compute_report(ground_truth, nisaba_results)


if __name__ == "__main__":
    main()