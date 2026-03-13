from typing import Annotated, Optional

from PLUGINS.SIRP.nocolymodel import Group, Condition, Operator
from PLUGINS.SIRP.sirpapi import Case
from PLUGINS.SIRP.sirpmodel import CaseModel, Severity, CaseStatus


def get_case(
        case_id: Annotated[str, "Case ID, for example case_000005"]
) -> Annotated[Optional[str], "AI-friendly JSON string of the case, or None if the case does not exist"]:
    """Retrieve a security case by case ID."""
    model = Case.get_by_case_id(case_id)
    if not model:
        return None
    result = model.model_dump_json_for_ai()
    return result


def list_cases(
        status: Annotated[Optional[list[CaseStatus]], "Filter by case status or a list of case statuses"] = None,
        severity: Annotated[Optional[list[Severity]], "Filter by severity level or a list of severity levels"] = None,
        limit: Annotated[int, "Maximum number of results to return"] = 10
) -> Annotated[list[dict], "Security cases matching the filters"]:
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


def create_case(
        title: Annotated[str, "Case title"],
        severity: Annotated[str, "Severity level: Critical, High, Medium, Low, Info"],
        description: Annotated[str, "Case description"] = "",
        status: Annotated[str, "Case status"] = "New"
) -> Annotated[str, "Row ID of the created case"]:
    """Create a new security case."""
    case_model = CaseModel(
        title=title,
        severity=Severity(severity),
        description=description,
        status=CaseStatus(status)
    )
    return Case.create(case_model)


def update_case(
        case_id: Annotated[str, "Case ID to update"],
        title: Annotated[Optional[str], "New title"] = None,
        severity: Annotated[Optional[str], "New severity"] = None,
        status: Annotated[Optional[str], "New status"] = None,
        description: Annotated[Optional[str], "New description"] = None
) -> Annotated[Optional[str], "Row ID of the updated case, or None if the case does not exist"]:
    """Update an existing security case."""
    case = Case.get_by_case_id(case_id)
    if not case:
        return None

    if title:
        case.title = title
    if severity:
        case.severity = Severity(severity)
    if status:
        case.status = CaseStatus(status)
    if description:
        case.description = description

    return Case.update(case)


if __name__ == "__main__":
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ASP.settings")
    import django

    django.setup()
    # result = get_case("case_000005")
    result = list_cases(status=[CaseStatus.IN_PROGRESS])
    print(result)
