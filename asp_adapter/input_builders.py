import uuid
from typing import List

from PLUGINS.SIRP.sirpmodel import (
    AlertModel,
    CaseModel,
    CaseStatus,
    CasePriority,
    ProductCategory,
    Severity,
    ImpactLevel,
    Confidence,
)


_SEVERITY_TO_PRIORITY = {
    Severity.INFORMATIONAL: CasePriority.LOW,
    Severity.LOW: CasePriority.LOW,
    Severity.MEDIUM: CasePriority.MEDIUM,
    Severity.HIGH: CasePriority.HIGH,
    Severity.CRITICAL: CasePriority.CRITICAL,
}


def _priority_from_severity(sev) -> CasePriority:
    return _SEVERITY_TO_PRIORITY.get(sev, CasePriority.MEDIUM)


def build_case_from_alert(alert: AlertModel) -> CaseModel:
    rowid = str(uuid.uuid4())
    category = alert.product_category if alert.product_category is not None else ProductCategory.OTHERS

    case = CaseModel(
        rowid=rowid,
        title=f"Case: {alert.title}",
        severity=alert.severity if alert.severity is not None else Severity.MEDIUM,
        impact=alert.impact if alert.impact is not None else ImpactLevel.MEDIUM,
        priority=_priority_from_severity(alert.severity),
        confidence=alert.confidence if alert.confidence is not None else Confidence.MEDIUM,
        description=alert.desc or alert.title,
        category=category,
        tags=list(alert.labels) if alert.labels else [],
        status=CaseStatus.IN_PROGRESS,
        comment="Case synthesized from alert for babelfish testing.",
        correlation_uid=alert.correlation_uid,
        summary="",
        workbook="",
        comment_ai="",
        summary_ai="",
        attack_stage_ai=None,
        threat_hunting_report_ai="",
        tickets=[],
        enrichments=list(alert.enrichments) if alert.enrichments else [],
        alerts=[alert],
    )
    return case
