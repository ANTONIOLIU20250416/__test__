from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field


class Verdict(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    UNVERIFIED = "UNVERIFIED"

    def __str__(self) -> str:
        return self.value


class EnvCertStatus(str, Enum):
    VALID = "VALID"
    EXPIRING_SOON = "EXPIRING_SOON"
    EXPIRED = "EXPIRED"

    def __str__(self) -> str:
        return self.value


class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    country: Optional[str] = None
    contact: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MaterialSpec(SQLModel, table=True):
    """Reference library entry: one alloy grade under one standard."""

    id: Optional[int] = Field(default=None, primary_key=True)
    alloy_code: str = Field(index=True)          # e.g. "C46400"
    alloy_name: str                               # e.g. "Naval Brass"
    standard: str = Field(index=True)             # e.g. "ASTM B124"
    category: str                                 # copper_alloy | iron | steel
    # {"Cu": {"min":59,"max":62}, "Zn": {"remainder": true}, ...} values in wt%
    chemistry_limits: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # {"tensile_strength_mpa": {"min":379}, "elongation_pct": {"min":15}, ...}
    mechanical_limits: dict = Field(default_factory=dict, sa_column=Column(JSON))
    notes: Optional[str] = None
    is_demo_data: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Certificate(SQLModel, table=True):
    """An uploaded Material Test Report / mill certificate."""

    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")
    file_name: str
    part_number: Optional[str] = None
    po_reference: Optional[str] = None
    heat_number: Optional[str] = None
    alloy_code_claimed: Optional[str] = None
    standard_claimed: Optional[str] = None
    raw_text: str = ""
    text_source: str = "plain_text"               # native_pdf | ocr | plain_text
    extracted_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    extraction_method: str = "heuristic"          # ai | heuristic | manual
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class ComplianceResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    certificate_id: int = Field(foreign_key="certificate.id")
    spec_id: Optional[int] = Field(default=None, foreign_key="materialspec.id")
    overall_verdict: Verdict = Verdict.UNVERIFIED
    element_results: list = Field(default_factory=list, sa_column=Column(JSON))
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class EnvCertificate(SQLModel, table=True):
    """Environmental / regulatory declaration tracked per supplier (RoHS, REACH, Prop65, conflict minerals...)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: int = Field(foreign_key="supplier.id")
    cert_type: str                                # RoHS | REACH | Prop65 | Conflict Minerals | DZR | Other
    reference_no: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    file_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_type: str
    entity_id: int
    action: str
    details: dict = Field(default_factory=dict, sa_column=Column(JSON))
    actor: str = "system"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
