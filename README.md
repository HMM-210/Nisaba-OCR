```markdown
# Nisaba OCR

نظام تعرّف ضوئي عربي (OCR) محلي، يعمل بلا إنترنت، مبني على خط أنابيب متعدد المحركات.

---

## الفكرة

بدل الاعتماد على محرّك واحد لقراءة كل شيء، يمرّ النص عبر ست مراحل متتالية، كل مرحلة تُقرّر: هل النتيجة جيدة بما يكفي لأقبلها؟ أم أرفعها للمرحلة التالية الأقوى؟

```
صورة
  ↓
[1] تنظيف الصورة          ── تكبير، إزالة ضجيج، تصحيح ميلان، قص الهوامش
  ↓
[2] تقطيع إلى كلمات       ── كشف الأسطر، فصل الكلمات، دمج العلامات الملتصقة
  ↓
[3] Tesseract             ── المحرّك السريع الخفيف (عتبة قبول: 0.90)
  ↓
[4] PP-OCRv6 عربي         ── المحرّك الأدق على المطبوع (عتبة: 0.85)
  ↓
[5] Qari OCR (VL)         ── نموذج رؤية للكلمات المستعصية (عتبة: 0.92)
  ↓
[6] إضافة الترقيم         ── محاذاة مع نتيجة Tesseract على الصورة الكاملة
  ↓
نص نهائي
```

كل مرحلة تُنفَّذ فقط عندما تفشل التي قبلها في تجاوز عتبة الثقة. هذا يوفّر الوقت (Tesseract أسرع بكثير من Qari) ويحافظ على الدقة (Qari يُستدعى فقط للصعب).

---

## المتطلبات

- **Docker Desktop** (Windows / macOS / Linux)
- **مساحة فارغة:** ~4 غيغابايت للصورة + النماذج
- **ذاكرة RAM:** 8 غيغابايت على الأقل (يُفضَّل 16)

لا يحتاج إلى:
- Python
- pip
- Tesseract
- أي مكتبة أخرى

كل شيء داخل صورة Docker.

---

## التشغيل

### للمستخدم النهائي

```bash
docker compose build
docker compose up
```

ثم افتح المتصفح على:

```
http://localhost:8000
```

### لأول مرة فقط

البناء الأول يستغرق 15-40 دقيقة حسب سرعة الإنترنت، لأنه يُنزّل:
- Python 3.10
- PyTorch (~800MB)
- PaddleOCR + PaddlePaddle (~500MB)
- Transformers + Qwen2-VL (~1GB)
- Tesseract مع حزمة اللغة العربية

بعد البناء الأول، كل تشغيل لاحق يأخذ ثوانٍ قليلة:

```bash
docker compose up
```

---

## النماذج

المشروع يستخدم نموذجين مدرّبين مسبقاً، تُحمَّل من Hugging Face:

| النموذج | الاستخدام | الرابط |
|---------|-----------|--------|
| **Arabic PP-OCRv6 Small Rec** | قراءة الكلمات (المرحلة 4) | [medyas/arabic_PP-OCRv6_small_rec](https://huggingface.co/medyas/arabic_PP-OCRv6_small_rec) |
| **Qari OCR 0.2.2.1 VL-2B** | قراءة الكلمات الصعبة (المرحلة 5) | [NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct](https://huggingface.co/NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct) |

النموذجان ليسا مضمّنين في المستودع (حجمهما عدة غيغابايتات). للحصول عليهما:

```bash
# النموذج الأول
git clone https://huggingface.co/medyas/arabic_PP-OCRv6_small_rec models/arabic_rec

# النموذج الثاني
git clone https://huggingface.co/NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct models/qari_merged_fp16
```

أو حمّلهما يدوياً من الرابطين وضعهما في `models/`.

---

## النتائج التجريبية

اختُبر المشروع على مجموعة **[ISI-PPT](https://huggingface.co/datasets/ahmedheakl/arocrbench_isippt)** (50 صورة أسطر مطبوعة نظيفة).

| النموذج | CER |
|---------|:---:|
| Gemini-2.0-Flash | 6.00% |
| GPT-4o | 8.00% |
| GPT-4o-mini | 15.00% |
| **Nisaba OCR** | **57.64%** |
| Qwen2-VL | 103.00% |

### ملاحظة منهجية مهمة

Nisaba مصمَّم لمعالجة **صفحات كاملة** حيث يعمل نموذج Qari على سياق واسع. بينما ISI-PPT مجموعة **أسطر معزولة**، كل صورة سطر واحد فقط. هذا يُقلّل من فعالية النموذج، لأن الكلمة تُقرأ بمعزل عن جاراتها.

المقارنة أعلاه يجب أن تُقرأ بهذا السياق: النماذج التجارية (Gemini, GPT-4o) ترى السطر كاملاً وتستفيد من السياق، بينما Nisaba يقطع السطر إلى كلمات منفردة قبل القراءة.

### التفوّق على Qwen2-VL

بمقارنة Nisaba (57.64%) مع Qwen2-VL الخام (103%)، يظهر أثر التتالي: Tesseract و PP-OCRv6 يعالجان معظم الكلمات، فلا يصل إلى Qari إلا الصعب منها. هذا وفّر 46 نقطة CER.

التقرير التفصيلي الكامل موجود في `nisaba_isi_report.txt`.

---

## بنية المشروع

```
Nisaba-AI/
│
├── 1ـNisabaـOCRـcleaning.py               المرحلة 1: التنظيف
├── 2ـNisabaـOCRـcutـtoـwords.py            المرحلة 2: التقطيع
├── 3ـNisabaـOCRـtesseract.py               المرحلة 3: Tesseract
├── 4ـNisabaـOCRـarabicـPP-OCRv6ـsmallـrec.py  المرحلة 4: PP-OCRv6
├── 5ـNisabaـOCRـQariـOCR.py                المرحلة 5: Qari
├── 6ـNisabaـOCRـalignـpunct.py             المرحلة 6: الترقيم
│
├── NisabaـOCRـfunctions.py                دوال مشتركة (JSON, locks)
├── NisabaـOCRـparallel.py                 التوازي حسب RAM المتاح
├── NisabaـOCRـorganizer.py                منظّم خط الأنابيب
├── NisabaـOCRـserver.py                   خادم FastAPI + SSE
├── NisabaـOCRـbenchmark.py                اختبار ISI-PPT
│
├── web/                                    الواجهة (HTML + CSS + JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── models/                                 النماذج (غير مرفوعة)
│   ├── arabic_rec/
│   └── qari_merged_fp16/
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .gitignore
```

---

## كيف يعمل التوازي

محرّك التوازي في `NisabaـOCRـparallel.py` يحسب عدد العمليات المتوازية من **RAM المتاح فعلياً**:

| المحرّك | استهلاك العملية الواحدة |
|---------|:---:|
| Tesseract | 500 MB |
| PP-OCRv6 | 1000 MB |
| Qari VL | 2500 MB |

على جهاز بـ 16GB RAM، يعطي هذا:
- Tesseract: 10 عمليات متوازية
- PP-OCRv6: 6 عمليات
- Qari: 2 عمليتان

النتيجة تُحفظ في `config/config.json` فلا تُعاد الحسبة كل مرة.

---

## الإفصاح

صُمِّم هذا المشروع هندسياً وأُدير تطويره سطراً بسطر بمساعدة الذكاء الاصطناعي (كتابة الكود). الأفكار المعمارية، خط الأنابيب، قرارات التصميم، واختيار المقاييس والمعايير من تصميم المؤلف. هذا إفصاح صادق عن طبيعة العمل، لا يُنقص من قيمة المشروع الهندسية.

---

## الترخيص

MIT

---

## روابط ذات صلة

- [ISI-PPT Dataset](https://huggingface.co/datasets/ahmedheakl/arocrbench_isippt)
- [KITAB-Bench (ACL 2025)](https://github.com/mbzuai-oryx/KITAB-Bench)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [Qwen2-VL](https://github.com/QwenLM/Qwen2-VL)
```