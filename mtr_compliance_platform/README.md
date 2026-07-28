# MTR Compliance Platform (prototype)

> Non-technical / first-time setup: see [使用說明.md](使用說明.md) (Traditional Chinese) —
> double-click `START_HERE.bat` (Windows) or `START_HERE.command` (Mac) after Python is installed.

An AI-assisted compliance management platform, in the spirit of Certivo/MTR.AI,
scoped for **plumbing-industry copper alloys and cast iron**: Material Test
Report (MTR) ingestion, chemistry/mechanical compliance checking against ASTM
and JIS specs, environmental/regulatory certificate tracking, a risk
dashboard, and an audit trail.

This is a working MVP built to validate the approach end-to-end, not a
production system — see **Known limitations** below before relying on it for
real QA/purchasing decisions.

## What it does

1. **Upload an MTR** — a native PDF, a scanned/photographed PDF or image
   (JPG/PNG/TIFF), or a `.txt` copy.
2. **Get text out of the document, for free.** Native PDFs are read directly
   (`pypdf`). Anything else — a scan, a photo of a paper cert, a PDF with no
   text layer — goes through **local OCR (Tesseract)**, entirely on-device.
   No network call, no API token spent on this step, regardless of volume.
   See **Local OCR pipeline** below.
3. **Structure the text into fields.** By default this is a **free,
   regex-based local parser** (heat number, alloy code, standard, chemistry,
   mechanical properties) — zero tokens. AI-assisted parsing (Claude) is
   available as an **opt-in checkbox** on the upload form for the rare
   document the local parser can't read; it only ever sends the already-OCR'd
   *text* (a few hundred tokens), never the image, so even the opt-in path is
   far cheaper than image/vision-based extraction.
4. **Compliance engine** matches the extracted alloy/standard against a spec
   library (chemistry + mechanical limits) and produces a per-element
   PASS / WARNING (within 5% of a limit) / FAIL / INFO verdict, plus an
   overall verdict.
5. **Environmental certificate tracker** — RoHS, REACH, Prop 65, Conflict
   Minerals, DZR, etc. per supplier, with expiry-date status (valid /
   expiring soon / expired).
6. **Risk dashboard** — pass/warning/fail counts, highest non-conformance-rate
   suppliers, certificates needing attention.
7. **Audit log** — every upload, compliance check, and export is timestamped,
   including which text source and parser were used, for audit readiness and
   token-spend transparency. Compliance results are exportable as CSV.

## Local OCR pipeline (no per-page API cost)

Scanned/photographed certificates are handled entirely locally:

1. `pypdf` tries to read a text layer directly. If a PDF yields at least ~40
   characters of native text, that's used as-is (`text_source = native_pdf`)
   — no OCR needed.
2. Otherwise (a scan, a photo, or an image upload), `PyMuPDF` renders each
   page to a 300 DPI image and **Tesseract OCR** reads it
   (`text_source = ocr`). Language pack: `eng+chi_tra+chi_sim+vie`, covering
   the languages these supplier certs are typically issued in.
3. The resulting text — regardless of source — goes through the same free
   local parser by default. There is no per-page or per-document API charge
   anywhere in this path.

This requires the Tesseract system binary and language data, which is **not**
a Python package and must be installed separately:

```bash
apt-get install tesseract-ocr tesseract-ocr-chi-tra tesseract-ocr-chi-sim tesseract-ocr-vie
```

(Add `tesseract-ocr-jpn` too if you also receive Japanese-language certs.)

## Spec library (seeded)

Copper alloys: `C46400` / `C46500` (naval brass, ASTM B124), `C36000`
(free-cutting brass, ASTM B16), and their JIS H3250 equivalents `C4640` /
`C3604`. Iron: ductile iron `65-45-12` (ASTM A536), `FCD450` (JIS G5502),
malleable iron `32510` (ASTM A47).

**⚠️ These limit values are representative figures compiled for this demo —
not a certified copy of the standard.** Before using this for real decisions,
replace every entry in `app/seed_data.py` with values verified against the
current official ASTM/JIS/CNS text. The `notes` field on every spec repeats
this disclaimer, and the UI shows it on the spec library and certificate
detail pages.

## Setup & run

```bash
# system dependency for local OCR (one-time, not a pip package)
apt-get install tesseract-ocr tesseract-ocr-chi-tra tesseract-ocr-chi-sim tesseract-ocr-vie

cd mtr_compliance_platform
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# optional — only needed if you plan to tick "Use AI-assisted parsing"
export ANTHROPIC_API_KEY=sk-ant-...

.venv/bin/uvicorn app.main:app --reload --port 8811
```

Open http://127.0.0.1:8811 — the dashboard. Try **Upload MTR** with one of
the sample certificates in `sample_data/`:

- `sample_mtr_c46400.txt` — clean cert, should come back **PASS**.
- `sample_mtr_c46400_fail.txt` — high lead/iron, low tensile strength,
  should come back **FAIL** (demonstrates dezincification-risk detection).
- `sample_mtr_c46400_scanned.png` — the same clean cert rendered as an image,
  to exercise the local-OCR path (`text_source = ocr`) — should also come
  back **PASS**, entirely without calling any API.

The SQLite database lives at `data/compliance.db` (gitignored) and is
recreated with seed data automatically if missing.

## Architecture

```
app/
  models.py       SQLModel tables: Supplier, MaterialSpec, Certificate,
                   ComplianceResult, EnvCertificate, AuditLog
  ocr.py           Local, free text extraction: native PDF text, else
                   PyMuPDF page rendering + Tesseract OCR
  extraction.py    OCR'd/native text -> structured fields (free regex parser
                   by default; opt-in Claude tool-use path)
  compliance.py    Spec matching + per-element PASS/WARNING/FAIL/INFO logic
  seed_data.py     Demo spec library + demo suppliers
  audit.py         Audit log writer + env-cert expiry status
  main.py          FastAPI routes
  templates/       Jinja2 pages (dashboard, upload, certificates, specs, ...)
```

## Known limitations (MVP scope)

- **OCR accuracy depends on scan/photo quality.** Tesseract does reasonably
  on clean 300 DPI scans of typed tables; skewed photos, low resolution, or
  handwritten certs will need better source images or a heavier OCR engine.
  Always spot-check `extracted_data` against the original document.
- **The local parser is regex-based**, so it expects roughly
  label-then-number patterns (e.g. "Cu 60.5", "Tensile Strength 58 ksi").
  Certs with unusual layouts may need the opt-in AI-assisted parsing
  checkbox, or a rule tweak in `extraction.py`.
- **Spec library ships with a small demo set**, but the `/specs` page supports
  add, edit, and delete (up to 12 chemistry elements + tensile/yield/
  elongation/hardness limits) — no code editing needed. Editing a seeded
  "Demo" spec flips it to "Custom" (it won't be silently reset later).
  Deleting a spec that a past certificate was checked against leaves that
  certificate's old result on record but "unmatched" for future checks.
- **No authentication / multi-tenant separation** — single-user local app.
  Add auth before deploying anywhere shared.
- **No PO/BOM linking** — certificates aren't yet tied to purchase order
  line items or parts the way Certivo/Pathnovo do; heat-number-to-PO
  matching would be the next major feature.
- **No regulatory-threshold checking (RoHS/REACH substance limits)** —
  currently just tracks *that* a declaration exists and its expiry, not
  substance-level PPM thresholds.
- **Env-cert file uploads aren't stored yet** — only metadata (type,
  reference no., dates) is captured; wiring up file storage is
  straightforward to add alongside the MTR upload path.
