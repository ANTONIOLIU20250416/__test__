import csv
import io
import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .audit import env_cert_status, log_action
from .compliance import evaluate_compliance, find_matching_spec
from .database import engine, get_session, init_db
from .extraction import extract_mtr_data, extract_mtr_data_from_images
from .models import Certificate, ComplianceResult, EnvCertificate, MaterialSpec, Supplier, Verdict
from .ocr import file_to_images, get_document_text
from .seed_data import sync_reference_data

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="MTR Compliance Platform")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def on_startup():
    init_db()
    with Session(engine) as session:
        sync_reference_data(session)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)):
    certs = session.exec(select(Certificate)).all()
    results = session.exec(select(ComplianceResult)).all()
    latest_by_cert = {}
    for r in results:
        prev = latest_by_cert.get(r.certificate_id)
        if prev is None or r.checked_at > prev.checked_at:
            latest_by_cert[r.certificate_id] = r

    verdict_counts = {v: 0 for v in Verdict}
    for r in latest_by_cert.values():
        verdict_counts[r.overall_verdict] += 1

    suppliers = {s.id: s for s in session.exec(select(Supplier)).all()}
    supplier_stats = {}
    for cert in certs:
        r = latest_by_cert.get(cert.id)
        if not r:
            continue
        name = suppliers.get(cert.supplier_id).name if cert.supplier_id in suppliers else "Unknown"
        stat = supplier_stats.setdefault(name, {"total": 0, "fail": 0, "warning": 0})
        stat["total"] += 1
        if r.overall_verdict == Verdict.FAIL:
            stat["fail"] += 1
        elif r.overall_verdict == Verdict.WARNING:
            stat["warning"] += 1
    risk_suppliers = sorted(
        ({"name": k, **v, "risk_rate": round((v["fail"] + v["warning"]) / v["total"] * 100, 1)}
         for k, v in supplier_stats.items() if v["total"]),
        key=lambda x: x["risk_rate"], reverse=True,
    )

    env_certs = session.exec(select(EnvCertificate)).all()
    expiring = [e for e in env_certs if env_cert_status(e.expiry_date) != "VALID"]

    return templates.TemplateResponse(request, "dashboard.html", {
        "verdict_counts": verdict_counts,
        "total_certs": len(certs),
        "risk_suppliers": risk_suppliers[:10],
        "expiring_env_certs": expiring,
        "env_cert_status": env_cert_status,
    })


@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request, session: Session = Depends(get_session)):
    suppliers = session.exec(select(Supplier)).all()
    return templates.TemplateResponse(request, "upload.html", {"suppliers": suppliers, "error": None})


@app.post("/upload")
def upload_submit(
    request: Request,
    file: UploadFile = File(...),
    supplier_id: str = Form(""),
    new_supplier_name: str = Form(""),
    part_number: str = Form(""),
    po_reference: str = Form(""),
    alloy_override: str = Form(""),
    standard_override: str = Form(""),
    use_ai: bool = Form(False),
    use_vision: bool = Form(False),
    session: Session = Depends(get_session),
):
    if new_supplier_name.strip():
        supplier = Supplier(name=new_supplier_name.strip())
        session.add(supplier)
        session.commit()
        session.refresh(supplier)
        resolved_supplier_id = supplier.id
        log_action(session, "Supplier", supplier.id, "created", {"name": supplier.name, "via": "upload_inline"})
    elif supplier_id.strip():
        resolved_supplier_id = int(supplier_id)
    else:
        suppliers = session.exec(select(Supplier)).all()
        return templates.TemplateResponse(request, "upload.html", {
            "suppliers": suppliers,
            "error": "Please select an existing supplier, or type a new supplier name.",
        })

    raw = file.file.read()
    text, text_source = get_document_text(file.filename, raw)

    extracted, method, vision_error = None, None, None
    if use_vision and os.environ.get("ANTHROPIC_API_KEY"):
        images = file_to_images(file.filename, raw)
        if images:
            try:
                extracted, method = extract_mtr_data_from_images(images), "ai_vision"
            except Exception as exc:  # network/SDK issues fall back to the text-based path
                vision_error = str(exc)

    if extracted is None:
        if not text.strip():
            suppliers = session.exec(select(Supplier)).all()
            detail = f" (AI vision also failed: {vision_error})" if vision_error else ", even after local OCR"
            return templates.TemplateResponse(request, "upload.html", {
                "suppliers": suppliers,
                "error": f"No text could be read from this file{detail} — it may be blank, corrupted, or too low-resolution to recognize.",
            })
        extracted, method = extract_mtr_data(text, allow_ai=use_ai)
        if vision_error:
            extracted["_vision_error"] = vision_error

    alloy_code = alloy_override.strip() or extracted.get("alloy_code")
    standard = standard_override.strip() or extracted.get("standard")

    cert = Certificate(
        supplier_id=resolved_supplier_id,
        file_name=file.filename,
        part_number=part_number or None,
        po_reference=po_reference or None,
        heat_number=extracted.get("heat_number"),
        alloy_code_claimed=alloy_code,
        standard_claimed=standard,
        raw_text=text[:20000],
        text_source=text_source,
        extracted_data=extracted,
        extraction_method=method,
    )
    session.add(cert)
    session.commit()
    session.refresh(cert)
    log_action(session, "Certificate", cert.id, "uploaded", {
        "text_source": text_source, "extraction_method": method,
        "ai_requested": use_ai, "vision_requested": use_vision, "file_name": file.filename,
    })

    spec = find_matching_spec(session, alloy_code, standard)
    verdict, element_results = evaluate_compliance(extracted, spec)
    result = ComplianceResult(
        certificate_id=cert.id,
        spec_id=spec.id if spec else None,
        overall_verdict=verdict,
        element_results=element_results,
    )
    session.add(result)
    session.commit()
    log_action(session, "Certificate", cert.id, "compliance_checked", {"verdict": verdict})

    return RedirectResponse(url=f"/certificates/{cert.id}", status_code=303)


@app.get("/certificates", response_class=HTMLResponse)
def certificates_list(request: Request, session: Session = Depends(get_session)):
    certs = session.exec(select(Certificate).order_by(Certificate.uploaded_at.desc())).all()
    suppliers = {s.id: s for s in session.exec(select(Supplier)).all()}
    latest_result = {}
    for r in session.exec(select(ComplianceResult)).all():
        prev = latest_result.get(r.certificate_id)
        if prev is None or r.checked_at > prev.checked_at:
            latest_result[r.certificate_id] = r
    rows = [{"cert": c, "supplier": suppliers.get(c.supplier_id), "result": latest_result.get(c.id)} for c in certs]
    return templates.TemplateResponse(request, "certificates.html", {"rows": rows})


@app.get("/certificates/{cert_id}", response_class=HTMLResponse)
def certificate_detail(cert_id: int, request: Request, session: Session = Depends(get_session)):
    cert = session.get(Certificate, cert_id)
    results = session.exec(
        select(ComplianceResult).where(ComplianceResult.certificate_id == cert_id).order_by(ComplianceResult.checked_at.desc())
    ).all()
    result = results[0] if results else None
    spec = session.get(MaterialSpec, result.spec_id) if result and result.spec_id else None
    supplier = session.get(Supplier, cert.supplier_id) if cert.supplier_id else None
    return templates.TemplateResponse(request, "certificate_detail.html", {
        "cert": cert, "result": result, "spec": spec, "supplier": supplier,
    })


CERT_MECHANICAL_FIELDS = [
    ("tensile_strength_mpa", "tensile_value"),
    ("yield_strength_mpa", "yield_value"),
    ("elongation_pct", "elongation_value"),
    ("hardness_hb", "hardness_value"),
]


def _cert_form_rows(cert: Optional[Certificate] = None) -> list:
    rows = []
    items = list((cert.extracted_data.get("chemistry") or {}).items()) if cert else []
    for i in range(12):
        if i < len(items):
            name, value = items[i]
            rows.append({"name": name, "value": value})
        else:
            rows.append({"name": "", "value": ""})
    return rows


def _cert_mechanical_values(cert: Optional[Certificate] = None) -> dict:
    values = {k: "" for _, k in CERT_MECHANICAL_FIELDS}
    if cert:
        m = cert.extracted_data.get("mechanical") or {}
        for key, form_key in CERT_MECHANICAL_FIELDS:
            if key in m:
                values[form_key] = m[key]
    return values


def _parse_cert_edit_form(form) -> dict:
    chemistry = {}
    for i in range(1, 13):
        name = (form.get(f"el{i}_name") or "").strip()
        value = form.get(f"el{i}_value")
        if name and value:
            chemistry[name] = float(value)

    mechanical = {}
    for key, form_key in CERT_MECHANICAL_FIELDS:
        value = form.get(form_key)
        if value:
            mechanical[key] = float(value)

    return dict(
        heat_number=(form.get("heat_number") or "").strip() or None,
        alloy_code=(form.get("alloy_code") or "").strip().upper() or None,
        standard=(form.get("standard") or "").strip() or None,
        part_number=(form.get("part_number") or "").strip() or None,
        chemistry=chemistry,
        mechanical=mechanical,
    )


@app.get("/certificates/{cert_id}/edit", response_class=HTMLResponse)
def certificate_edit_form(cert_id: int, request: Request, session: Session = Depends(get_session)):
    cert = session.get(Certificate, cert_id)
    return templates.TemplateResponse(request, "certificate_edit.html", {
        "cert": cert,
        "el_rows": _cert_form_rows(cert),
        "mech": _cert_mechanical_values(cert),
    })


@app.post("/certificates/{cert_id}/edit")
async def certificate_edit_submit(cert_id: int, request: Request, session: Session = Depends(get_session)):
    cert = session.get(Certificate, cert_id)
    form = await request.form()
    fields = _parse_cert_edit_form(form)

    cert.heat_number = fields["heat_number"]
    cert.alloy_code_claimed = fields["alloy_code"]
    cert.standard_claimed = fields["standard"]
    cert.part_number = fields["part_number"]

    extracted = dict(cert.extracted_data)
    extracted["heat_number"] = fields["heat_number"]
    extracted["alloy_code"] = fields["alloy_code"]
    extracted["standard"] = fields["standard"]
    extracted["part_number"] = fields["part_number"]
    extracted["chemistry"] = fields["chemistry"]
    extracted["mechanical"] = fields["mechanical"]
    cert.extracted_data = extracted
    cert.extraction_method = "manual"
    session.add(cert)
    session.commit()

    spec = find_matching_spec(session, cert.alloy_code_claimed, cert.standard_claimed)
    verdict, element_results = evaluate_compliance(extracted, spec)
    result = ComplianceResult(
        certificate_id=cert.id,
        spec_id=spec.id if spec else None,
        overall_verdict=verdict,
        element_results=element_results,
    )
    session.add(result)
    session.commit()
    log_action(session, "Certificate", cert.id, "corrected", {"verdict": verdict})

    return RedirectResponse(url=f"/certificates/{cert.id}", status_code=303)


@app.get("/certificates/{cert_id}/export.csv")
def certificate_export(cert_id: int, session: Session = Depends(get_session)):
    cert = session.get(Certificate, cert_id)
    results = session.exec(
        select(ComplianceResult).where(ComplianceResult.certificate_id == cert_id).order_by(ComplianceResult.checked_at.desc())
    ).all()
    result = results[0] if results else None
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["group", "parameter", "value", "min", "max", "status"])
    for row in (result.element_results if result else []):
        writer.writerow([row["group"], row["parameter"], row["value"], row["min"], row["max"], row["status"]])
    buf.seek(0)
    log_action(session, "Certificate", cert_id, "exported")
    return StreamingResponse(buf, media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=compliance_{cert.heat_number or cert_id}.csv"
    })


@app.get("/specs", response_class=HTMLResponse)
def specs_list(request: Request, session: Session = Depends(get_session)):
    specs = session.exec(select(MaterialSpec).order_by(MaterialSpec.category, MaterialSpec.alloy_code)).all()
    return templates.TemplateResponse(request, "specs.html", {"specs": specs})


MECHANICAL_FORM_FIELDS = [
    ("tensile_strength_mpa", "tensile_min", "min"),
    ("yield_strength_mpa", "yield_min", "min"),
    ("elongation_pct", "elongation_min", "min"),
    ("hardness_hb", "hardness_max", "max"),
]


def _parse_spec_form(form) -> dict:
    chemistry_limits = {}
    for i in range(1, 13):
        name = (form.get(f"el{i}_name") or "").strip()
        if not name:
            continue
        if form.get(f"el{i}_remainder") == "true":
            chemistry_limits[name] = {"remainder": True}
            continue
        limit = {}
        min_v, max_v = form.get(f"el{i}_min"), form.get(f"el{i}_max")
        if min_v:
            limit["min"] = float(min_v)
        if max_v:
            limit["max"] = float(max_v)
        if limit:
            chemistry_limits[name] = limit

    mechanical_limits = {}
    for key, form_key, bound in MECHANICAL_FORM_FIELDS:
        value = form.get(form_key)
        if value:
            mechanical_limits[key] = {bound: float(value)}

    return dict(
        alloy_code=(form.get("alloy_code") or "").strip().upper(),
        alloy_name=(form.get("alloy_name") or "").strip(),
        standard=(form.get("standard") or "").strip(),
        category=form.get("category") or "copper_alloy",
        chemistry_limits=chemistry_limits,
        mechanical_limits=mechanical_limits,
        notes=(form.get("notes") or "").strip() or None,
    )


def _spec_form_rows(spec: Optional[MaterialSpec] = None) -> list:
    """Builds the 12 fixed element-row values (for pre-filling the edit form)."""
    rows = []
    items = list(spec.chemistry_limits.items()) if spec else []
    for i in range(12):
        if i < len(items):
            name, limit = items[i]
            rows.append({
                "name": name,
                "min": limit.get("min", ""),
                "max": limit.get("max", ""),
                "remainder": bool(limit.get("remainder")),
            })
        else:
            rows.append({"name": "", "min": "", "max": "", "remainder": False})
    return rows


def _spec_mechanical_values(spec: Optional[MaterialSpec] = None) -> dict:
    values = {"tensile_min": "", "yield_min": "", "elongation_min": "", "hardness_max": ""}
    if spec:
        m = spec.mechanical_limits
        if "tensile_strength_mpa" in m:
            values["tensile_min"] = m["tensile_strength_mpa"].get("min", "")
        if "yield_strength_mpa" in m:
            values["yield_min"] = m["yield_strength_mpa"].get("min", "")
        if "elongation_pct" in m:
            values["elongation_min"] = m["elongation_pct"].get("min", "")
        if "hardness_hb" in m:
            values["hardness_max"] = m["hardness_hb"].get("max", "")
    return values


@app.post("/specs")
async def specs_add(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    fields = _parse_spec_form(form)
    spec = MaterialSpec(**fields, is_demo_data=False)
    session.add(spec)
    session.commit()
    session.refresh(spec)
    log_action(session, "MaterialSpec", spec.id, "created", {"alloy_code": spec.alloy_code, "standard": spec.standard})
    return RedirectResponse(url="/specs", status_code=303)


@app.get("/specs/{spec_id}/edit", response_class=HTMLResponse)
def spec_edit_form(spec_id: int, request: Request, session: Session = Depends(get_session)):
    spec = session.get(MaterialSpec, spec_id)
    return templates.TemplateResponse(request, "spec_edit.html", {
        "spec": spec,
        "el_rows": _spec_form_rows(spec),
        "mech": _spec_mechanical_values(spec),
    })


@app.post("/specs/{spec_id}/edit")
async def spec_edit_submit(spec_id: int, request: Request, session: Session = Depends(get_session)):
    spec = session.get(MaterialSpec, spec_id)
    form = await request.form()
    fields = _parse_spec_form(form)
    for key, value in fields.items():
        setattr(spec, key, value)
    spec.is_demo_data = False
    session.add(spec)
    session.commit()
    log_action(session, "MaterialSpec", spec.id, "updated", {"alloy_code": spec.alloy_code, "standard": spec.standard})
    return RedirectResponse(url="/specs", status_code=303)


@app.post("/specs/{spec_id}/delete")
def spec_delete(spec_id: int, session: Session = Depends(get_session)):
    spec = session.get(MaterialSpec, spec_id)
    if spec:
        log_action(session, "MaterialSpec", spec.id, "deleted", {"alloy_code": spec.alloy_code, "standard": spec.standard})
        session.delete(spec)
        session.commit()
    return RedirectResponse(url="/specs", status_code=303)


@app.get("/suppliers", response_class=HTMLResponse)
def suppliers_list(request: Request, session: Session = Depends(get_session)):
    suppliers = session.exec(select(Supplier).order_by(Supplier.name)).all()
    return templates.TemplateResponse(request, "suppliers.html", {"suppliers": suppliers})


@app.post("/suppliers")
def suppliers_add(
    name: str = Form(...),
    country: str = Form(""),
    contact: str = Form(""),
    session: Session = Depends(get_session),
):
    supplier = Supplier(name=name.strip(), country=country.strip() or None, contact=contact.strip() or None)
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    log_action(session, "Supplier", supplier.id, "created", {"name": supplier.name})
    return RedirectResponse(url="/suppliers", status_code=303)


@app.get("/suppliers/{supplier_id}/edit", response_class=HTMLResponse)
def supplier_edit_form(supplier_id: int, request: Request, session: Session = Depends(get_session)):
    supplier = session.get(Supplier, supplier_id)
    return templates.TemplateResponse(request, "supplier_edit.html", {"supplier": supplier})


@app.post("/suppliers/{supplier_id}/edit")
def supplier_edit_submit(
    supplier_id: int,
    name: str = Form(...),
    country: str = Form(""),
    contact: str = Form(""),
    session: Session = Depends(get_session),
):
    supplier = session.get(Supplier, supplier_id)
    supplier.name = name.strip()
    supplier.country = country.strip() or None
    supplier.contact = contact.strip() or None
    session.add(supplier)
    session.commit()
    log_action(session, "Supplier", supplier.id, "updated", {"name": supplier.name})
    return RedirectResponse(url="/suppliers", status_code=303)


@app.post("/suppliers/{supplier_id}/delete")
def supplier_delete(supplier_id: int, session: Session = Depends(get_session)):
    supplier = session.get(Supplier, supplier_id)
    if supplier:
        log_action(session, "Supplier", supplier.id, "deleted", {"name": supplier.name})
        session.delete(supplier)
        session.commit()
    return RedirectResponse(url="/suppliers", status_code=303)


@app.get("/env-certificates", response_class=HTMLResponse)
def env_certs_list(request: Request, session: Session = Depends(get_session)):
    certs = session.exec(select(EnvCertificate).order_by(EnvCertificate.expiry_date)).all()
    suppliers = {s.id: s for s in session.exec(select(Supplier)).all()}
    all_suppliers = session.exec(select(Supplier)).all()
    rows = [{"cert": c, "supplier": suppliers.get(c.supplier_id), "status": env_cert_status(c.expiry_date)} for c in certs]
    return templates.TemplateResponse(request, "env_certs.html", {"rows": rows, "suppliers": all_suppliers})


@app.post("/env-certificates")
def env_certs_add(
    supplier_id: int = Form(...),
    cert_type: str = Form(...),
    reference_no: str = Form(""),
    issue_date: str = Form(""),
    expiry_date: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    cert = EnvCertificate(
        supplier_id=supplier_id,
        cert_type=cert_type,
        reference_no=reference_no or None,
        issue_date=date.fromisoformat(issue_date) if issue_date else None,
        expiry_date=date.fromisoformat(expiry_date) if expiry_date else None,
        notes=notes or None,
    )
    session.add(cert)
    session.commit()
    session.refresh(cert)
    log_action(session, "EnvCertificate", cert.id, "created", {"cert_type": cert_type})
    return RedirectResponse(url="/env-certificates", status_code=303)


@app.get("/audit-log", response_class=HTMLResponse)
def audit_log_view(request: Request, session: Session = Depends(get_session)):
    from .models import AuditLog
    entries = session.exec(select(AuditLog).order_by(AuditLog.timestamp.desc())).all()
    return templates.TemplateResponse(request, "audit_log.html", {"entries": entries})
