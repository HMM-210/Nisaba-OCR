```markdown
# Nisaba OCR

[![CER](https://img.shields.io/badge/CER-11.09%25-brightgreen)]()
[![Local](https://img.shields.io/badge/100%25-Local-blue)]()
[![No Internet](https://img.shields.io/badge/No%20Internet-Required-success)]()
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

نظام تعرّف ضوئي عربي (OCR) محلي، يعمل بلا إنترنت، بلا تكلفة، بخصوصية مطلقة.

---

## لماذا Nisaba؟

| المشكلة | Nisaba |
|---------|:------:|
| GPT-4o يكلف ~$0.01/صورة | **مجاني** |
| Gemini يرسل بياناتك لسيرفر | **محلي 100%** |
| السحابة تحتاج إنترنت دائم | **يعمل offline** |
| EasyOCR: CER = 23.85% | **Nisaba: 11.09%** |
| Tesseract: CER = 16.7% | **Nisaba: 11.09%** |

**إن كنت تعمل على مستندات عربية حساسة، ولا يمكنك إرسالها للسحابة، Nisaba هو الحل الوحيد.**

---

## النتائج التجريبية

اختُبر المشروع على **459 صورة عربية** من مجموعة [ISI-PPT](https://huggingface.co/datasets/ahmedheakl/arocrbench_isippt):

| النموذج | CER | النوع |
|---------|:---:|-------|
| Gemini-2.0-Flash | 6.00% | سحابي |
| GPT-4o | 8.00% | سحابي |
| **Nisaba OCR** | **11.09%** | **محلي** |
| GPT-4o-mini | 15.00% | سحابي |
| Tesseract 5 | ~28.9% | محلي |
| EasyOCR | ~23.85% | محلي |
| Qwen2-VL | 103.00% | محلي |

**زمن المعالجة**: 63 دقيقة لـ 459 صورة = **8.2 ثانية/صورة**.
**التكلفة**: صفر.
**الخصوصية**: البيانات لا تخرج من جهازك.

### رحلة التحسين

| الإصدار | CER | التحسين |
|---------|:---:|---------|
| v0.1 — Otsu الأولي | 57.64% | نقطة البداية |
| v0.2 — تنظيف متسامح | 51.13% | +6.5 نقطة |
| v0.3 — معالجة لونية (Netra-CV) | 23.57% | +27.5 نقطة |
| **v0.4 — إصلاح كتابة `_sources`** | **11.09%** | **+12.5 نقطة** |

---

## الفكرة

بدل الاعتماد على محرّك واحد، يمرّ النص عبر **ست مراحل متتالية**، كل واحدة تقرّر: هل النتيجة جيدة بما يكفي؟ أم أرفعها للمرحلة التالية؟

```
صورة
  ↓
[1] تنظيف + معالجة لونية    ── Netra-CV، تكبير ×5، تصحيح ميلان
  ↓
[2] تقطيع إلى كلمات         ── PP-OCRv6_small_det، فصل ودمج
  ↓
[3] Tesseract              ── المحرّك السريع (عتبة: 0.90)
  ↓
[4] PP-OCRv6 عربي          ── المحرّك الأدق (عتبة: 0.85)
  ↓
[5] Qari OCR (VL)          ── نموذج رؤية للمستعصي (عتبة: 0.92)
  ↓
[6] إضافة الترقيم          ── محاذاة مع Tesseract
  ↓
نص نهائي
```

كل مرحلة تُنفَّذ **فقط** عندما تفشل التي قبلها. توفير في الوقت (Tesseract أسرع بكثير من Qari)، والحفاظ على الدقة (Qari يُستدعى فقط للصعب).

---

## المتطلبات

- **Docker Desktop** (Windows / macOS / Linux)
- **مساحة فارغة**: ~4 GB (الصورة + النماذج)
- **RAM**: 8 GB على الأقل (يُفضَّل 16)

لا يحتاج إلى Python، ولا pip، ولا Tesseract، ولا أي مكتبة. كل شيء داخل Docker.

---

## التشغيل

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

**البناء الأول** يستغرق 15-40 دقيقة (يُنزّل Python, PyTorch, PaddleOCR, Transformers, Qwen2-VL).
**بعد البناء**، كل تشغيل لاحق يأخذ ثوانٍ قليلة.

---

## النماذج

المشروع يستخدم نموذجين مدرّبين مسبقاً، تُحمَّل من Hugging Face:

| النموذج | الاستخدام | الرابط |
|---------|-----------|--------|
| **Arabic PP-OCRv6 Small Rec** | القراءة العامة (المرحلة 4) | [medyas/arabic_PP-OCRv6_small_rec](https://huggingface.co/medyas/arabic_PP-OCRv6_small_rec) |
| **Qari OCR 0.2.2.1 VL-2B** | القراءة الصعبة (المرحلة 5) | [NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct](https://huggingface.co/NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct) |

النموذجان ليسا مضمّنين في المستودع. للحصول عليهما:

```bash
git clone https://huggingface.co/medyas/arabic_PP-OCRv6_small_rec models/arabic_rec
git clone https://huggingface.co/NAMAA-Space/Qari-OCR-0.2.2.1-VL-2B-Instruct models/qari_merged_fp16
```

---

## بنية المشروع

```
Nisaba-OCR/
├── 1ـNisabaـOCRـcleaning.py               المرحلة 1: التنظيف
├── 2ـNisabaـOCRـcutـtoـwords.py            المرحلة 2: التقطيع
├── 3ـNisabaـOCRـtesseract.py               المرحلة 3: Tesseract
├── 4ـNisabaـOCRـarabicـPP-OCRv6ـsmallـrec.py  المرحلة 4: PP-OCRv6
├── 5ـNisabaـOCRـQariـOCR.py                المرحلة 5: Qari
├── 6ـNisabaـOCRـalignـpunct.py             المرحلة 6: الترقيم
├── NisabaـOCRـfunctions.py                دوال مشتركة
├── NisabaـOCRـparallel.py                 التوازي حسب RAM
├── NisabaـOCRـorganizer.py                منظّم خط الأنابيب
├── NisabaـOCRـserver.py                   خادم FastAPI + SSE
├── NisabaـOCRـbenchmark.py                اختبار ISI-PPT
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

---

## كيف يعمل التوازي

محرّك التوازي يحسب عدد العمليات من **RAM المتاح فعلياً**:

| المحرّك | العملية الواحدة |
|---------|:---:|
| Tesseract | 500 MB |
| PP-OCRv6 | 1000 MB |
| Qari VL | 2500 MB |

على جهاز بـ 16GB RAM:
- Tesseract: 10 عمليات
- PP-OCRv6: 6 عمليات
- Qari: 2 عمليتان

النتيجة تُحفظ في `config/config.json`.

---

## القيود الصادقة

Nisaba **ليس مثالياً**. هذه حدوده الحقيقية:

### 1) 11 صورة من 459 فشلت بالكامل

**السبب**: كاشف الأسطر (`PP-OCRv6_small_det`) يفشل على:
- الأسطر القصيرة جداً (3-6 كلمات)
- النصوص بلونين منفصلين في سطر واحد
- الأسطر الفارسية

**الحل المستقبلي**: كاشف أسطر مخصص، أو ترتيب حسب مركز السطر الرأسي.

### 2) `isi_0037` نموذج للحالة الصعبة

النص بلونين (مثلاً أسود + ذهبي) → الكاشف يرى سطرين → الترتيب خطأ.
**CER = 75.68%** لهذه الصورة وحدها.

### 3) 6 صور بخطأ CER > 20%

أخطاء قراءة على كلمات معقدة، أو ترقيم دخيل، أو خطوط غير معتادة.

### 4) الفارق مع Gemini (6%)

5 نقاط. **قابل للإغلاق** بتحسين واحد: **معالجة على مستوى السطر بدل الكلمة**. متوقع في v0.5.

---

## الإفصاح

صُمِّم هذا المشروع هندسياً وأُدير تطويره سطراً بسطر بمساعدة الذكاء الاصطناعي (كتابة الكود). الأفكار المعمارية، خط الأنابيب، قرارات التصميم، واختيار المقاييس والمعايير من تصميم المؤلف. هذا إفصاح صادق عن طبيعة العمل، لا يُنقص من قيمة المشروع الهندسية.

---

## الترخيص

MIT

---

## روابط

- [ISI-PPT Dataset](https://huggingface.co/datasets/ahmedheakl/arocrbench_isippt)
- [KITAB-Bench (ACL 2025)](https://github.com/mbzuai-oryx/KITAB-Bench)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [Qwen2-VL](https://github.com/QwenLM/Qwen2-VL)
```
