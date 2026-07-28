import csv
import io
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
from .extraction import extract_mtr_data
from .models import Certificate, ComplianceResult, EnvCertificate, MaterialSpec, Supplier, Verdict
from .ocr import get_document_text
from .seed_data import seed_if_empty

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="MTR Compliance Platform")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def on_startup():
    init_db()
    with Session(engine) as session:
        seed_if_empty(session)


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
    supplier_id: int = Form(...),
    part_number: str = Form(""),
    po_reference: str = Form(""),
    alloy_override: str = Form(""),
    standard_override: str = Form(""),
    use_ai: bool = Form(False),
    session: Session = Depends(get_session),
):
    raw = file.file.read()
    text, text_source = get_document_text(file.filename, raw)

    if not text.strip():
        suppliers = session.exec(select(Supplier)).all()
        return templates.TemplateResponse(request, "upload.html", {
            "suppliers": suppliers,
            "error": "No text could be read from this file, even after local OCR — it may be blank, corrupted, or too low-resolution to recognize.",
        })

    extracted, method = extract_mtr_data(text, allow_ai=use_ai)
    alloy_code = alloy_override.strip() or extracted.get("alloy_code")
    standard = standard_override.strip() or extracted.get("standard")

    cert = Certificate(
        supplier_id=supplier_id,
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
        "text_source": text_source, "extraction_method": method, "ai_requested": use_ai, "file_name": file.filename,
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
