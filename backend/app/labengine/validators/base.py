from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationResult:
    passed: bool
    score: int
    feedback: str
    pending: bool = False  # qo'lda baholash kerak


@dataclass
class ValidationContext:
    config: dict[str, Any]       # manifestdagi validation.config (xeshlangan)
    max_score: int
    submitted: dict[str, Any]    # talaba yuborgan ma'lumot
    instance: Any                # LabInstance
    scans: list[list[dict]]      # shu instansiyadagi skanlar
    provider: Any                # VirtualizationProvider

    def machine(self, name: str | None = None):
        name = name or self.config.get("machine")
        for m in self.instance.machines:
            if m.name == name:
                return m
        return None
