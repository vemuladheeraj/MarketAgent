"""Data-quality validation models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import DataQuality
from app.models.time import ensure_ist


class QualityIssue(BaseModel):
    """A single data-quality finding."""

    code: str
    message: str
    severity: DataQuality = DataQuality.WARNING
    field: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "QualityIssue":
        if self.severity not in (DataQuality.WARNING, DataQuality.INVALID):
            raise ValueError("issue severity must be WARNING or INVALID")
        return self


class DataQualityReport(BaseModel):
    """Aggregate validation result for one data payload."""

    symbol: str
    collected_at: datetime
    status: DataQuality = DataQuality.VALID
    issues: list[QualityIssue] = Field(default_factory=list)
    checks_run: int = 0

    @model_validator(mode="after")
    def _checks(self) -> "DataQualityReport":
        self.collected_at = ensure_ist(self.collected_at)
        if any(i.severity == DataQuality.INVALID for i in self.issues):
            self.status = DataQuality.INVALID
        elif self.issues:
            self.status = DataQuality.WARNING
        else:
            self.status = DataQuality.VALID
        return self

    @property
    def valid(self) -> bool:
        return self.status == DataQuality.VALID

    @property
    def invalid(self) -> bool:
        return self.status == DataQuality.INVALID

    def add_issue(self, issue: QualityIssue) -> None:
        self.issues.append(issue)
        # Recompute status.
        if issue.severity == DataQuality.INVALID:
            self.status = DataQuality.INVALID
        elif self.status != DataQuality.INVALID:
            self.status = DataQuality.WARNING

    def mark_run(self, count: int = 1) -> None:
        self.checks_run += count