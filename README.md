# Nisaba OCR

[![CER](https://img.shields.io/badge/CER-11.09%25-brightgreen)]()
[![Local](https://img.shields.io/badge/100%25-Local-blue)]()
[![No Internet](https://img.shields.io/badge/No%20Internet-Required-success)]()
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

[العربية](#العربية) | [English](#english)

---

<a name="العربية"></a>
## العربية

نظام تعرّف ضوئي عربي (OCR) محلي بالكامل، مجاني، وخاص — يعمل بلا إنترنت، بلا تكلفة API، وبلا خروج أي بيانات من جهازك.

### لماذا Nisaba؟

| المشكلة | Nisaba |
|---|:---:|
| GPT-4o يكلف ~$0.01/صورة | **مجاني** |
| Gemini يرسل بياناتك لسيرفر | **محلي 100%** |
| السحابة تحتاج إنترنت دائم | **يعمل offline بالكامل** |
| EasyOCR: CER = 23.85% | **Nisaba: 11.09%** |
| Tesseract: CER = 28.9%+ | **Nisaba: 11.09%** |

إن كنت تعمل على مستندات عربية حساسة لا يمكنك إرسالها للسحابة، Nisaba مبني خصيصاً لهذا السيناريو.

### النتائج التجريبية

اختُبر المشروع على **459 صورة عربية حقيقية** من مجموعة [ISI-PPT](https://huggingface.co/datasets/ahmedheakl/arocrbench_isippt):

| النموذج | CER | النوع |
|---|:---:|---|
| Gemini-2.0-Flash | 6.00% | سحابي |
| GPT-4o | 8.00% | سحابي |
| **Nisaba OCR** | **11.09%** | **محلي** |
| GPT-4o-mini | 15.00% | سحابي |
| Tesseract 5 | ~28.9% | محلي |
| EasyOCR | ~23.85% | محلي |
| Qwen2-VL (خام، بلا ضبط دقيق) | 103.00% | محلي |

**زمن المعالجة:** 63 دقيقة لـ459 صورة = **8.2 ثانية/صورة**
**التكلفة:** صفر
**الخصوصية:** لا تخرج أي بيانات من جهازك

#### رحلة التحسين

| الإصدار | CER | التحسين |
|---|:---:|---|
| v0.1 — Otsu الأولي | 57.64% | نقطة البداية |
| v0.2 — تنظيف متسامح | 51.13% | +6.5 نقطة |
| v0.3 — معالجة لونية (Netra-CV) | 23.57% | +27.5 نقطة |
| **v0.4 — إصلاح خطأ قياس في `_sources`** | **11.09%** | **+12.5 نقطة** |

*(قفزة v0.4 كشفت أساساً خطأ قياس سابقاً في سكربت المقارنة نفسه، لا تحسيناً جديداً بالنماذج — التحسين الحقيقي المبني على النماذج هو الانتقال v0.2 إلى v0.3. يبقى 11.09% الرقم الدقيق والحالي.)*

### الفكرة

بدل الاعتماد على محرّك واحد، تمر كل كلمة عبر **ست مراحل متتالية**، كل واحدة تقرّر: هل النتيجة جيدة بما يكفي؟ أم أرفعها للمرحلة التالية؟

```
صورة
  │
  ▼
[1] تنظيف + معالجة لونية    ── Netra-CV، تكبير ×5، تصحيح ميلان
  │
  ▼
[2] تقطيع إلى كلمات         ── PP-OCRv6_small_det، فصل ودمج
  │
  ▼
[3] Tesseract              ── المحرّك السريع (عتبة: 0.90)
  │
  ▼
[4] PP-OCRv6 عربي          ── المحرّك الأدق (عتبة: 0.85)
  │
  ▼
[5] Qari OCR (رؤية بصرية)   ── نموذج رؤية للمستعصي (عتبة: 0.92)
  │
  ▼
[6] إضافة الترقيم          ── محاذاة مع Tesseract
  │
  ▼
نص نهائي
```

كل مرحلة تُنفَّذ **فقط** عندما تفشل التي قبلها، مما يوفّر الوقت (Tesseract أسرع بكثير من Qari) ويحافظ على الدقة (Qari يُستدعى فقط للكلمات الصعبة).

### المتطلبات

- **Docker Desktop** (Windows / macOS / Linux)
- **مساحة فارغة:** ~4 GB (الصورة + النماذج)
- **RAM:** 8 GB على الأقل (يُفضَّل 16)

لا يحتاج إلى Python، ولا pip، ولا Tesseract، ولا أي تثبيت يدوي — كل شيء داخل Docker.

### التشغيل

```bash
git clone https://github.com/HMM-210/Nisaba-OCR.git
cd Nisaba-OCR
docker compose build
docker compose up
```

ثم افتح المتصفح على:

```
http://localhost:8000
```

**البناء الأول:** 15-40 دقيقة (يُنزّل Python, PyTorch, PaddleOCR, Transformers, Qwen2-VL).
**كل تشغيل لاحق:** ثوانٍ قليلة.

### النماذج

يستخدم المشروع نموذجين مدرّبين مسبقاً، تُحمَّل من Hugging Face:

| النموذج | الاستخدام | الرابط |
|---|---|---|
| **Arabic PP-OCRv6 Small Rec** | القراءة العامة (المرحلة 4) | [medyas/arabic_PP-OCRv6_small_rec](https://huggingface.co/medyas/arabic_PP-OCRv6_small_rec) |
| **Qari OCR 0.2.2.1 VL-2B** | القراءة الصعبة (المرحلة 5) | [NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct](https://huggingface.co/NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct) |

النموذجان ليسا مضمّنين في المستودع. للحصول عليهما:

```bash
git clone https://huggingface.co/medyas/arabic_PP-OCRv6_small_rec models/arabic_rec
git clone https://huggingface.co/NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct models/qari_merged_fp16
```

### بنية المشروع

```
Nisaba-OCR/
├── 1_Nisaba_OCR_cleaning.py               المرحلة 1: التنظيف
├── 2_Nisaba_OCR_cut_to_words.py           المرحلة 2: التقطيع
├── 3_Nisaba_OCR_tesseract.py              المرحلة 3: Tesseract
├── 4_Nisaba_OCR_arabic_PP-OCRv6_small_rec.py  المرحلة 4: PP-OCRv6
├── 5_Nisaba_OCR_Qari_OCR.py               المرحلة 5: Qari
├── 6_Nisaba_OCR_align_punct.py            المرحلة 6: الترقيم
├── Nisaba_OCR_functions.py                دوال مشتركة
├── Nisaba_OCR_parallel.py                 التوازي حسب RAM
├── Nisaba_OCR_organizer.py                منظّم خط الأنابيب
├── Nisaba_OCR_server.py                   خادم FastAPI + SSE
├── Nisaba_OCR_benchmark.py                اختبار ISI-PPT
├── web/                                    الواجهة
│   ├── index.html
│   ├── style.css
│   └── app.js
├── models/                                 النماذج (غير مرفوعة)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .gitignore
```

### كيف يعمل التوازي

يحسب محرّك التوازي عدد العمليات من **RAM المتاح فعلياً**:

| المحرّك | العملية الواحدة |
|---|:---:|
| Tesseract | 500 MB |
| PP-OCRv6 | 1000 MB |
| Qari VL | 2500 MB |

على جهاز بـ16GB RAM، يصل عادة إلى: Tesseract 10 عمليات، PP-OCRv6 6 عمليات، Qari عمليتان.

يُحفظ الإعداد المقاس في `config/config.json`.

### القيود الصادقة

Nisaba **ليس مثالياً**. هذه حدوده الحقيقية حالياً:

**1) 11 صورة من 459 فشلت بالكامل.** السبب: كاشف الأسطر (`PP-OCRv6_small_det`) يفشل على الأسطر القصيرة جداً (3-6 كلمات)، والنصوص بلونين منفصلين في سطر واحد، والأسطر الفارسية. الحل المستقبلي: كاشف أسطر مخصص، أو ترتيب حسب مركز السطر الرأسي.

**2) `isi_0037` — حالة صعبة نموذجية.** نص بلونين (أسود + ذهبي) → الكاشف يرى سطرين → الترتيب يختل. CER لهذي الصورة وحدها: 75.68%.

**3) 6 صور بخطأ CER أعلى من 20%.** أخطاء قراءة على كلمات معقدة، أو ترقيم دخيل، أو خطوط غير معتادة.

**4) فارق 5 نقاط مع Gemini.** فارق حقيقي قابل للإغلاق، والتحسين الأكثر ترجيحاً: معالجة على مستوى السطر بدل الكلمة، متوقع في v0.5.

### المشروع قابل للتطور — ما زال في بداياته

هذا المشروع مصمَّم صراحة ليستمر بالتحسن، وبنيته مبنية لهذا بالذات:

- **كاشف أسطر مخصص** يغلق فجوة الـ11 صورة الفاشلة بالكامل.
- **التعرّف على مستوى السطر** بدل الكلمة — التغيير الأرجح لإغلاق الفارق المتبقي مع النماذج السحابية.
- **نموذج مدرَّب لكشف علامات الترقيم**، بدل خطوة المحاذاة القائمة على القواعد حالياً.
- **نماذج مضغوطة/مُقطَّرة** لاستهلاك ذاكرة أقل وسرعة أعلى على أجهزة أضعف.
- **مجموعة اختبار أوسع وأكثر تنوعاً**، تتجاوز ISI-PPT، تشمل خط اليد والنصوص المختلطة عربي/إنجليزي.

كل مرحلة في خط الأنابيب مستقلة وقابلة للاستبدال بتصميمها — نموذج أقوى، كاشف أفضل، أو خطوة محاذاة أذكى يمكن إدخالها دون المساس بباقي النظام. الكاسكيد السداسي ليس السقف، بل الأساس الذي بُني المشروع ليكبر منه، نحو تكافؤ حقيقي مع نتائج النماذج السحابية الحالية — أو تجاوزها لاحقاً.

### الإفصاح

صُمِّم هذا المشروع هندسياً وأُدير تطويره سطراً بسطر بمساعدة الذكاء الاصطناعي (كتابة الكود). الأفكار المعمارية، خط الأنابيب، قرارات التصميم، واختيار المقاييس والمعايير من تصميم المؤلف. هذا إفصاح صادق عن طبيعة العمل، لا يُنقص من قيمة المشروع الهندسية.

### الترخيص

MIT

### روابط

- [ISI-PPT Dataset](https://huggingface.co/datasets/ahmedheakl/arocrbench_isippt)
- [KITAB-Bench (ACL 2025)](https://github.com/mbzuai-oryx/KITAB-Bench)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [Qwen2-VL](https://github.com/QwenLM/Qwen2-VL)

---

<a name="english"></a>
## English

A fully local, free, and private Arabic OCR system. No internet connection required, no API costs, and no data ever leaves your machine.

### Why Nisaba?

| The problem | Nisaba |
|---|:---:|
| GPT-4o costs ~$0.01/image | **Free** |
| Gemini sends your data to a server | **100% local** |
| Cloud OCR needs a constant connection | **Works fully offline** |
| EasyOCR: CER = 23.85% | **Nisaba: 11.09%** |
| Tesseract: CER = 28.9%+ | **Nisaba: 11.09%** |

If you work with sensitive Arabic documents that can't be sent to the cloud, Nisaba is built specifically for that case.

### Benchmark Results

Evaluated on **459 real Arabic images** from the [ISI-PPT dataset](https://huggingface.co/datasets/ahmedheakl/arocrbench_isippt):

| Model | CER | Type |
|---|:---:|---|
| Gemini-2.0-Flash | 6.00% | Cloud |
| GPT-4o | 8.00% | Cloud |
| **Nisaba OCR** | **11.09%** | **Local** |
| GPT-4o-mini | 15.00% | Cloud |
| Tesseract 5 | ~28.9% | Local |
| EasyOCR | ~23.85% | Local |
| Qwen2-VL (base, no fine-tuning) | 103.00% | Local |

**Processing time:** 63 minutes for 459 images → **8.2 seconds/image**
**Cost:** Zero
**Privacy:** No data ever leaves your machine

#### Development Journey

| Version | CER | Change |
|---|:---:|---|
| v0.1 — initial Otsu thresholding | 57.64% | starting point |
| v0.2 — more tolerant cleaning | 51.13% | +6.5 points |
| v0.3 — color-aware preprocessing (Netra-CV) | 23.57% | +27.5 points |
| **v0.4 — fixed a `_sources` measurement bug** | **11.09%** | **+12.5 points** |

*(The v0.4 jump mainly exposed a pre-existing measurement bug in the benchmark script, rather than a new model improvement — the true model-driven gain is the v0.2 → v0.3 step. 11.09% remains the accurate, current figure.)*

### How It Works

Instead of relying on a single OCR engine, every word passes through **six sequential stages**. Each one asks: is this result good enough, or should it escalate to the next stage?

```
image
  │
  ▼
[1] Cleaning + color processing   — Netra-CV, 5× upscale, deskew
  │
  ▼
[2] Word segmentation             — PP-OCRv6_small_det, split & merge
  │
  ▼
[3] Tesseract                     — fast engine (threshold: 0.90)
  │
  ▼
[4] PP-OCRv6 Arabic                — more accurate engine (threshold: 0.85)
  │
  ▼
[5] Qari OCR (Vision-Language)     — for hard cases (threshold: 0.92)
  │
  ▼
[6] Punctuation alignment          — aligned against Tesseract's output
  │
  ▼
final text
```

Each stage runs **only** when the one before it fails — keeping things fast (Tesseract is far cheaper than Qari) while preserving accuracy (Qari is invoked only for genuinely hard words).

### Requirements

- **Docker Desktop** (Windows / macOS / Linux)
- **Free disk space:** ~4 GB (image + models)
- **RAM:** 8 GB minimum (16 GB recommended)

No Python, no pip, no Tesseract, and no manual library installs — everything runs inside Docker.

### Running It

```bash
git clone https://github.com/HMM-210/Nisaba-OCR.git
cd Nisaba-OCR
docker compose build
docker compose up
```

Then open your browser at:

```
http://localhost:8000
```

**First build:** 15–40 minutes (downloads Python, PyTorch, PaddleOCR, Transformers, Qwen2-VL).
**Every run after that:** a few seconds.

### Models

Nisaba uses two pretrained models, pulled from Hugging Face:

| Model | Used for | Link |
|---|---|---|
| **Arabic PP-OCRv6 Small Rec** | General reading (stage 4) | [medyas/arabic_PP-OCRv6_small_rec](https://huggingface.co/medyas/arabic_PP-OCRv6_small_rec) |
| **Qari OCR 0.2.2.1 VL-2B** | Hard cases (stage 5) | [NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct](https://huggingface.co/NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct) |

Neither model is bundled in the repository. Fetch them with:

```bash
git clone https://huggingface.co/medyas/arabic_PP-OCRv6_small_rec models/arabic_rec
git clone https://huggingface.co/NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct models/qari_merged_fp16
```

### Project Structure

```
Nisaba-OCR/
├── 1_Nisaba_OCR_cleaning.py               Stage 1: cleaning
├── 2_Nisaba_OCR_cut_to_words.py           Stage 2: word segmentation
├── 3_Nisaba_OCR_tesseract.py              Stage 3: Tesseract
├── 4_Nisaba_OCR_arabic_PP-OCRv6_small_rec.py  Stage 4: PP-OCRv6
├── 5_Nisaba_OCR_Qari_OCR.py               Stage 5: Qari
├── 6_Nisaba_OCR_align_punct.py            Stage 6: punctuation
├── Nisaba_OCR_functions.py                shared utilities
├── Nisaba_OCR_parallel.py                 RAM-aware parallelism
├── Nisaba_OCR_organizer.py                pipeline orchestrator
├── Nisaba_OCR_server.py                   FastAPI + SSE server
├── Nisaba_OCR_benchmark.py                ISI-PPT benchmark runner
├── web/                                    front-end
│   ├── index.html
│   ├── style.css
│   └── app.js
├── models/                                 models (not committed)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .gitignore
```

### How Parallelism Works

The parallel engine computes worker counts from **actually available RAM**:

| Engine | Per-worker cost |
|---|:---:|
| Tesseract | 500 MB |
| PP-OCRv6 | 1000 MB |
| Qari VL | 2500 MB |

On a 16 GB machine, this typically resolves to: 10 Tesseract workers, 6 PP-OCRv6 workers, 2 Qari workers.

The measured configuration is cached in `config/config.json`.

### Honest Limitations

Nisaba is **not perfect**. Here are its real, current limits:

**1) 11 of 459 images failed completely.** Cause: the line detector (`PP-OCRv6_small_det`) struggles with very short lines (3–6 words), two differently-colored text runs on the same line, and Persian-script lines. Planned fix: a dedicated line detector, or ordering by each line's vertical center.

**2) `isi_0037` — a representative hard case.** Two-colored text (e.g. black + gold) causes the detector to see two separate lines, breaking reading order. CER for this single image: 75.68%.

**3) 6 images with CER above 20%.** Misreads on complex words, stray punctuation, or unusual fonts.

**4) A 5-point gap with Gemini.** A real, closeable gap — the most promising fix is line-level rather than word-level recognition, planned for v0.5.

### This Project Is Built to Grow — It's Still Early

Nisaba is explicitly designed to keep improving, and its architecture is built for exactly that:

- **A dedicated line detector** to close the 11-image failure gap entirely.
- **Line-level recognition** instead of word-level — the change most likely to close the remaining gap with cloud models.
- **A trained punctuation-detection model**, replacing today's rule-based alignment step with something that generalizes further.
- **Quantized / distilled models** for lower memory use and faster inference on weaker hardware.
- **A larger, more diverse benchmark set**, beyond ISI-PPT, including handwritten and mixed Arabic/English documents.

Every stage in the pipeline is independent and swappable by design — a stronger model, a better detector, or a smarter alignment step can be dropped in without touching the rest of the system. The six-stage cascade isn't the ceiling; it's the foundation the project was built to grow from, toward real parity with — or eventually beyond — today's cloud-based results.

### Disclosure

This project was engineered and its development directed, line by line, with AI assistance for code writing. The architecture, the pipeline design, every design decision, and the choice of metrics and evaluation standards are the author's own. This is an honest disclosure of how the work was done, not a disclaimer on its engineering value.

### License

MIT

### Links

- [ISI-PPT Dataset](https://huggingface.co/datasets/ahmedheakl/arocrbench_isippt)
- [KITAB-Bench (ACL 2025)](https://github.com/mbzuai-oryx/KITAB-Bench)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [Qwen2-VL](https://github.com/QwenLM/Qwen2-VL)
