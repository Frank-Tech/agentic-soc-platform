---
name: asp-case-update
description: Update an existing security case
argument-hint: <case_id> [title=<title>] [severity=<severity>] [status=<status>] [description=<description>]
allowed-tools: [ "*" ]
---

Update case {{case_id}} with the following changes:

- Title: {{title}}
- Severity: {{severity}}
- Status: {{status}}
- Description: {{description}}

**Valid values:**

- Severity: Critical, High, Medium, Low, Info
- Status: New, InProgress, Closed, FalsePositive

Use the MCP tool `update_case` with the case ID and any provided update fields.

After successful update, display:

**Case Updated Successfully**

Show before/after comparison for changed fields, then display complete updated case details:

- Case ID
- Title
- Severity
- Status
- Description
- Updated timestamp

Highlight what changed and confirm the update was applied successfully.
