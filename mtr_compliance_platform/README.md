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

1. **Upload an MTR** — a native PDF, a Word `.docx`, a scanned/photographed
   PDF or image (JPG/PNG/TIFF), or a `.txt` copy.
2. **Get text out of the document, for free.** Native PDFs are read directly
   (`pypdf`). Anything else — a scan, a photo of a paper cert, a PDF with no
   text layer — goes through **local OCR (Tesseract)**, entirely on-device.
   No network call, no API token spent on this step, regardless of volume.
   See **Local OCR pipeline** below.
3. **Structure the text into fields.** By default this is a **free,
   regex-based local parser** (heat number, alloy code, standard, chemistry,
   mechanical properties) — zero tokens. Two opt-in checkboxes on the upload
   form spend API tokens when the free parser isn't enough:
   - **"Use AI-assisted parsing"** — sends the already-OCR'd *text* to Claude
     (a few hundred tokens) instead of the regex parser.
   - **"Use Claude AI to read the image/scan directly"** — bypasses OCR
     entirely and sends the page image(s) to Claude's vision, for scans where
     Tesseract's OCR text came out wrong or unreadable. Costs more tokens
     than the text-based option since images cost more than the text they'd
     produce, so it's the last-resort option, not the default.
   Either way, if the extraction still comes out wrong, **every certificate's
   "Edit values" page** lets you type in/correct the chemistry and mechanical
   values by hand (free) and immediately re-runs the compliance check.
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
8. **Supplier management** — the `/suppliers` page lists, adds, edits, and
   deletes suppliers. The upload form also lets you type a brand-new
   supplier name directly instead of picking from the dropdown; it's
   created automatically on submit.

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

**When OCR gets it wrong**, there are two ways to recover, in order of cost:
1. Tick **"Use AI-assisted parsing"** on upload — sends the OCR'd text (not
   the image) to Claude, cheap but still limited by whatever OCR produced.
2. Tick **"Use Claude AI to read the image/scan directly"** — skips OCR
   entirely and sends the page image(s) straight to Claude's vision. Costs
   more tokens (images cost more than text) but can read scans OCR can't.
3. Or skip AI entirely and use the certificate's **"Edit values"** page to
   type in/correct the chemistry and mechanical values by hand — free, and
   immediately re-runs the compliance check with the corrected numbers.

## Spec library (seeded)

Two batches of seed specs, both created automatically on first run and synced
into any existing database on every subsequent startup (see `sync_reference_data`
below):

- **`SPECS`** (8 grades, marked "Demo" in the UI) — a small hand-compiled set:
  `C46400` / `C46500` (naval brass, ASTM B124), `C36000` (free-cutting brass,
  ASTM B16), JIS H3250 equivalents `C4640` / `C3604`, and irons `65-45-12`
  (ASTM A536), `FCD450` (JIS G5502), `32510` (ASTM A47).
- **`IMPORTED_SPECS`** (34 grades, marked "Custom") — imported from a
  user-provided `MTR_Analyzer.xlsm` (Standards_DB tab): copper alloys
  (C46400/B21, C46500/B21, C36300, C35200, C37700, C27450, C6806, C69300,
  C12200, CW617N, CW602N, HPb59-1, C83600, C84400, C85700, C87850, C87860,
  C89833/36/44, CAC203, CAC406, C23000), stainless (SS304/304L/316/316L, CF8,
  CF8M), carbon steel (A105, SAE 1008, ASTM A53 Gr.A, Q235), and grey iron
  (FC200) — covering ASTM, JIS, EN, GB/T, and SAE.

**⚠️ These limit values are for quick reference only — not a certified copy
of any standard.** Verify every entry against the current official
ASTM/JIS/EN/GB/T/SAE text before using this for real QA/purchasing
decisions. The `notes` field on every spec repeats this, and the UI shows
it on the spec library and certificate detail pages.

**Known data-quality notes on the imported set** (flag these if you're the
one who supplied `Standards_DB`):
- `Q235`'s carbon max was entered in the source as `22` (%) — physically
  impossible for steel — and has been corrected to `0.22` here, with the
  correction noted on that spec. Verify against your source.
- `C27450` had no standard cited in the source; stored as `standard = "N/A"`.
- `C36000`/`ASTM B16` already existed in the demo set with equivalent
  chemistry plus tensile/elongation limits the source didn't include, so the
  import skipped creating a duplicate and kept the existing (fuller) entry.
- A few rows encode constraints this app's per-element min/max model can't
  represent structurally (e.g. ASTM A53 Gr.A's "Cu+Ni+Cr+Mo+V ≤ 1.00" combined
  limit) — these are preserved in the spec's `notes` field but not
  automatically checked.

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
  seed_data.py     Demo + imported spec library, demo suppliers, idempotent sync
  audit.py         Audit log writer + env-cert expiry status
  main.py          FastAPI routes
  templates/       Jinja2 pages (dashboard, upload, certificates, specs, ...)
```

## Known limitations (MVP scope)

- **OCR accuracy depends on scan/photo quality.** Tesseract does reasonably
  on clean 300 DPI scans of typed tables; skewed photos, low resolution, or
  handwritten certs will need better source images or a heavier OCR engine.
  Always spot-check `extracted_data` against the original document.
- **The local parser handles two layouts**: simple "label then number" text
  (e.g. "Cu 60.5") and real-world tables (an element-symbol header row, a
  unit row, a limits row, then data rows - the format Legend's own MTR
  template uses). Table parsing works positionally off the header/units row
  since linear PDF/docx text extraction destroys visual column alignment.
  Certs with a genuinely different layout may still need the opt-in AI
  text-parsing or vision checkboxes, a rule tweak in `extraction.py`, or
  manual correction via the certificate's "Edit values" page.
- **Word `.docx` MTRs are supported** alongside PDF/image/`.txt` - table
  cells extract cleanly since docx preserves real cell boundaries (unlike
  PDF text, which just flattens a table's visual layout into a line of
  text). No OCR needed; it's read directly like a native PDF.
- **Supplier auto-detection is best-effort.** If you leave the upload
  form's supplier fields blank, it searches the certificate's text for an
  *existing* supplier's name. This only works when the document actually
  names the supplier as text somewhere - many real MTR templates (including
  Legend's own) only show the buyer's letterhead, not the supplier's name,
  in which case there's nothing to detect and you still need to pick or
  type the supplier yourself.
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
