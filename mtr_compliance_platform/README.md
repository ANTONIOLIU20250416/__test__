# MTR Compliance Platform (prototype)

An AI-assisted compliance management platform, in the spirit of Certivo/MTR.AI,
scoped for **plumbing-industry copper alloys and cast iron**: Material Test
Report (MTR) ingestion, chemistry/mechanical compliance checking against ASTM
and JIS specs, environmental/regulatory certificate tracking, a risk
dashboard, and an audit trail.

This is a working MVP built to validate the approach end-to-end, not a
production system — see **Known limitations** below before relying on it for
real QA/purchasing decisions.

## What it does

1. **Upload an MTR** (text-extractable PDF or `.txt`) for a supplier shipment.
2. **AI extraction** pulls out heat number, alloy code, standard, chemical
   composition (wt%) and mechanical properties. Uses Claude when
   `ANTHROPIC_API_KEY` is set; otherwise falls back to a regex-based
   heuristic parser so the whole flow still works offline/without a key.
3. **Compliance engine** matches the extracted alloy/standard against a spec
   library (chemistry + mechanical limits) and produces a per-element
   PASS / WARNING (within 5% of a limit) / FAIL / INFO verdict, plus an
   overall verdict.
4. **Environmental certificate tracker** — RoHS, REACH, Prop 65, Conflict
   Minerals, DZR, etc. per supplier, with expiry-date status (valid /
   expiring soon / expired).
5. **Risk dashboard** — pass/warning/fail counts, highest non-conformance-rate
   suppliers, certificates needing attention.
6. **Audit log** — every upload, compliance check, and export is timestamped
   for audit readiness. Compliance results are exportable as CSV.

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
cd mtr_compliance_platform
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# optional — enables real AI extraction instead of the regex fallback
export ANTHROPIC_API_KEY=sk-ant-...

.venv/bin/uvicorn app.main:app --reload --port 8811
```

Open http://127.0.0.1:8811 — the dashboard. Try **Upload MTR** with one of
the sample certificates in `sample_data/`:

- `sample_mtr_c46400.txt` — clean cert, should come back **PASS**.
- `sample_mtr_c46400_fail.txt` — high lead/iron, low tensile strength,
  should come back **FAIL** (demonstrates dezincification-risk detection).

The SQLite database lives at `data/compliance.db` (gitignored) and is
recreated with seed data automatically if missing.

## Architecture

```
app/
  models.py       SQLModel tables: Supplier, MaterialSpec, Certificate,
                   ComplianceResult, EnvCertificate, AuditLog
  extraction.py    PDF/text -> structured data (Claude tool-use, or regex fallback)
  compliance.py    Spec matching + per-element PASS/WARNING/FAIL/INFO logic
  seed_data.py     Demo spec library + demo suppliers
  audit.py         Audit log writer + env-cert expiry status
  main.py          FastAPI routes
  templates/       Jinja2 pages (dashboard, upload, certificates, specs, ...)
```

## Known limitations (MVP scope)

- **Scanned/image-only PDFs are not OCR'd.** Only text-extractable PDFs and
  `.txt` work today. Adding Claude-vision or Tesseract OCR for scanned
  certs is the natural next step.
- **Spec library is a small demo set.** Real use needs the full grade list
  Legend Valve actually buys, sourced from the current standard text, plus
  a way to add/edit specs from the UI (currently seed-data only).
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
