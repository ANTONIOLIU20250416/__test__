"""Data model for drawing dimension extraction results."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# Recognised dimension categories. "other" is the catch-all for anything
# that doesn't fit (e.g. free-text notes such as heat-treatment callouts).
DIMENSION_TYPES = (
    "linear",
    "diameter",
    "radius",
    "angle",
    "thread",
    "gdt",
    "surface_finish",
    "hardness",
    "other",
)


@dataclass
class Dimension:
    """A single dimensioned feature / measurement requirement read off a drawing."""

    item_no: int
    feature: str
    dimension_type: str = "other"
    nominal_value: Optional[float] = None
    upper_tol: Optional[float] = None
    lower_tol: Optional[float] = None
    unit: str = "mm"
    upper_limit: Optional[float] = None
    lower_limit: Optional[float] = None
    is_critical: bool = False
    gdt_symbol: Optional[str] = None
    measurement_method: str = ""
    location_ref: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        # Derive upper/lower limits from nominal + tolerance when the
        # extractor didn't already compute them.
        if self.nominal_value is not None:
            if self.upper_limit is None and self.upper_tol is not None:
                self.upper_limit = round(self.nominal_value + self.upper_tol, 6)
            if self.lower_limit is None and self.lower_tol is not None:
                self.lower_limit = round(self.nominal_value + self.lower_tol, 6)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Dimension":
        known = {f: data.get(f) for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DrawingInfo:
    """Header metadata identifying the drawing / part being inspected."""

    drawing_no: str = ""
    part_name: str = ""
    material: str = ""
    revision: str = ""
    general_tolerance: str = ""
    default_unit: str = "mm"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DrawingInfo":
        known = {f: data.get(f) for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DrawingAnalysis:
    """Full result of interpreting one engineering drawing."""

    drawing_info: DrawingInfo = field(default_factory=DrawingInfo)
    dimensions: list[Dimension] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DrawingAnalysis":
        info = DrawingInfo.from_dict(data.get("drawing_info", {}) or {})
        dims = [Dimension.from_dict(d) for d in data.get("dimensions", []) or []]
        warnings = list(data.get("warnings", []) or [])
        return cls(drawing_info=info, dimensions=dims, warnings=warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "drawing_info": self.drawing_info.to_dict(),
            "dimensions": [d.to_dict() for d in self.dimensions],
            "warnings": self.warnings,
        }
