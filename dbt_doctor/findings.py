from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Finding:
    module: str          # e.g. "lineage", "testing", "duplicates"
    severity: Severity
    subject: str          # model/macro name this finding is about
    message: str          # short human-readable summary
    detail: str = ""      # optional longer explanation / "why"
    suggestion: str = ""  # optional recommended fix
    weight: float = 1.0   # deduction weight used by the scoring engine
    meta: dict = field(default_factory=dict)
