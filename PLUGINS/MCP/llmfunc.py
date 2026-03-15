from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from PLUGINS.SIEM.models import KeywordSearchInput
from PLUGINS.SIEM.tools import SIEMToolKit
from PLUGINS.SIRP.nocolymodel import Group, Condition, Operator
from PLUGINS.SIRP.sirpapi import Case
from PLUGINS.SIRP.sirpmodel import CaseModel, Severity, CaseStatus, CaseVerdict, Confidence


def get_case(
        case_id: Annotated[str, "Case ID, for example case_000005"]
) -> Annotated[Optional[str], "AI-friendly JSON string of the case, or None if the case does not exist"]:
    """Retrieve a security case by case ID."""
    model = Case.get_by_id(case_id)
    if not model:
        return None
    result = model.model_dump_json_for_ai()
    return result


def list_cases(
        status: Annotated[Optional[list[CaseStatus]], "Filter by case status or a list of case statuses"] = None,
        severity: Annotated[Optional[list[Severity]], "Filter by severity level or a list of severity levels"] = None,
        limit: Annotated[int, "Maximum number of results to return"] = 10
) -> Annotated[list[str], "Security cases matching the filters"]:
    """List security cases with optional filters."""
    conditions = []

    if status:
        conditions.append(Condition(field="status", operator=Operator.IN, value=status))

    if severity:
        conditions.append(Condition(field="severity", operator=Operator.IN, value=severity))

    filter_model = Group(logic="AND", children=conditions) if conditions else Group(logic="AND", children=[])

    models = Case.list(filter_model)
    result = []
    for model in models[:limit]:
        result.append(model.model_dump_json_for_ai())
    return result


def update_case(
        case_id: Annotated[str, "Case ID to update"],
        severity: Annotated[Optional[str], "New severity"] = None,
        status: Annotated[Optional[str], "New status"] = None,
        verdict: Annotated[Optional[str], "New verdict"] = None,
        severity_ai: Annotated[Optional[str], "New AI-assessed severity"] = None,
        confidence_ai: Annotated[Optional[str], "New AI-assessed confidence"] = None,
        comment_ai: Annotated[Optional[
            str], "New AI-comment. Supports Markdown format."] = None,
        summary_ai: Annotated[Optional[
            str], "New AI-summary. Supports Markdown format."] = None
) -> Annotated[Optional[str], "Row ID of the updated case, or None if the case does not exist"]:
    """Update an existing security case_old."""
    case_old = Case.get_by_id(case_id, lazy_load=True)
    if not case_old:
        return None

    case_new = CaseModel()
    case_new.rowid = case_old.rowid
    if severity:
        case_new.severity = Severity(severity)
    if status:
        case_new.status = CaseStatus(status)
    if verdict:
        case_new.verdict = CaseVerdict(verdict)
    if severity_ai:
        case_new.severity_ai = Severity(severity_ai)
    if confidence_ai:
        case_new.confidence_ai = Confidence(confidence_ai)

    if comment_ai:
        case_new.comment_ai = comment_ai
    if summary_ai:
        case_new.summary_ai = summary_ai

    return Case.update(case_new)


def siem_keyword_search(
        keyword: Annotated[str, "Search keyword. Can be IP address, hostname, username, or any string to search across all fields"],
        time_range_start: Annotated[str, "Start time in UTC ISO8601 format. Example: 2026-02-04T06:00:00Z"],
        time_range_end: Annotated[str, "End time in UTC ISO8601 format. Example: 2026-02-04T07:00:00Z"],
        time_field: Annotated[str, "The field to apply time range filter on"] = "@timestamp",
        index_name: Annotated[Optional[str], "Target SIEM index/source name. If None, searches across all indices"] = None
) -> Annotated[list[str], "Keyword search results as AI-friendly JSON strings"]:
    input_data = KeywordSearchInput(
        keyword=keyword,
        time_range_start=time_range_start,
        time_range_end=time_range_end,
        time_field=time_field,
        index_name=index_name
    )
    results = SIEMToolKit.keyword_search(input_data)
    return [item.model_dump_json() for item in results]


def get_current_time(
        time_format: Annotated[
            Optional[str], "Optional datetime format string (e.g. '%Y/%m/%d %H:%M:%S' '%Y-%m-%dT%H:%M:%SZ'). "
                           "If not provided, returns ISO 8601 time with timezone information accurate to seconds"] = None
) -> Annotated[str, "Current system time string with timezone information"]:
    current_time = datetime.now().astimezone()
    if time_format:
        return current_time.strftime(time_format)
    return current_time.isoformat(timespec="seconds")


if __name__ == "__main__":
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ASP.settings")
    import django

    django.setup()
    print(get_current_time())
    time_range_end = datetime.now(timezone.utc)
    time_range_start = time_range_end - timedelta(minutes=10)
    siem_results = siem_keyword_search(
        keyword="227.174.159.18",
        time_range_start=time_range_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        time_range_end=time_range_end.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    print(siem_results)
    cases = list_cases(limit=1)
    print(cases)
    if cases:
        case = Case.list(Group(logic="AND", children=[]), lazy_load=True)[0]
        result = update_case(
            case_id=case.id,
            status=CaseStatus.IN_PROGRESS,
            verdict=CaseVerdict.SUSPICIOUS,
            severity_ai=Severity.HIGH,
            confidence_ai=Confidence.MEDIUM,
            comment_ai="#### AI Comment\n\nAdditional investigation notes.",
            summary_ai="#### AI Summary\n\nUpdated case summary."
        )
    else:
        result = None
    print(result)
