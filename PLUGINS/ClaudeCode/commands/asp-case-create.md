---
name: asp-case-create
description: Create a new security case
argument-hint: title=<title> severity=<severity> [description=<description>] [status=<status>]
allowed-tools: [ "*" ]
---

Create a new security case with:

- Title: {{title}}
- Severity: {{severity}}
- Description: {{description}}
- Status: {{status}} (default: New)

**Valid values:**

- Severity: Critical, High, Medium, Low, Info
- Status: New, InProgress, Closed, FalsePositive

Use the MCP tool `create_case` with the provided parameters.

After successful creation, display:

**Case Created Successfully**

- Case ID: [assigned ID]
- Rowid: [database rowid]
- Title: [title]
- Severity: [severity]
- Status: [status]
- Description: [description]
- Created: [timestamp]

Provide a confirmation message and suggest next steps (e.g., adding alerts, artifacts, or starting investigation).
