---
name: asp-case-list
description: List security cases with optional filters
argument-hint: [ status=<status> ] [ severity=<severity> ] [ limit=<number> ]
allowed-tools: [ "*" ]
---

List cases with the following filters:

- Status: {{status}}
- Severity: {{severity}}
- Limit: {{limit}}

Use the MCP tool `list_cases` with the provided parameters.

**Valid filter values:**

- Status: New, InProgress, Closed, FalsePositive
- Severity: Critical, High, Medium, Low, Info
- Limit: Any positive integer (default: 10)

Display results in a table format:

| Case ID | Title | Severity | Status | Created |
|---------|-------|----------|--------|---------|
| ...     | ...   | ...      | ...    | ...     |

After the table, provide:

- Total count of cases returned
- Summary of severity distribution
- Any notable patterns or trends

If no filters are provided, list recent cases with default limit of 10.
