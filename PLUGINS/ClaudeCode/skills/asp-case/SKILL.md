---
name: asp-case
description: Comprehensive security case management - query, list, and update cases, Use when users need to manage cases on the ASP platform.
compatibility: connect to asp mcp server
metadata:
  author: Funnywolf
  version: 0.1.0
  mcp-server: asp
  category: cyber security
  tags: [ case-management, SOC ]
  documentation: https://asp.viperrtp.com/
---

# ASP Case

This skill provides complete case management capabilities for the Agentic SOC Platform.

## Available Operations

Ask the user which operation they want to perform:

1. **Get case details** - Query detailed information about a specific case by ID
2. **List cases** - Browse cases with optional filters (status, severity, limit)
3. **Update a case** - Modify existing case fields including severity, status, verdict, and AI analysis

## Operation Details

### 1 Get Case Details

**Required parameters:**

- `case_id` - The case identifier

**Process:**

1. Use MCP tool `get_case` with the case ID
2. Parse the returned JSON string
3. If result is `None`, state that the case was not found

**Output format:**

**Case Overview**

- Case ID
- Title
- Severity
- Status
- Description
- Confidence
- Priority
- Category
- Verdict
- Correlation UID
- Created/Updated timestamps

**Associated Alerts**

- Total count
- For each key alert: title, severity, status, source UID, correlation UID, first seen time, last seen time

**Associated Artifacts for each alert**

- Total count
- For each key artifact: name, value, type, role, reputation score

**Timeline**

- Created time
- Acknowledged time
- Closed time
- Start/end time if available

### 2. List Cases

**Optional parameters:**

- `status` - Filter by status (supports multiple values: New, In Progress, On Hold, Resolved, Closed)
- `severity` - Filter by severity (supports multiple values: Informational, Low, Medium, High, Critical, Fatal, Unknown,
  Other)
- `limit` - Maximum number of results (default: 10)

**Process:**

1. Parse filter parameters (status and severity support comma-separated lists)
2. Use MCP tool `list_cases` with provided filters
3. Parse each returned JSON string
4. Display results in table format

**Output format:**

| Case ID | Title | Severity | Status | Verdict | Priority | Confidence | Category | Correlation UID | Created | Updated |
|---------|-------|----------|--------|---------|----------|------------|----------|-----------------|---------|---------|
| ...     | ...   | ...      | ...    | ...     | ...      | ...        | ...      | ...             | ...     | ...     |

Total: [count] cases

### 3. Update Case

**Required parameters:**

- `case_id` - The case identifier to update

**Optional update fields:**

- `severity` - Informational, Low, Medium, High, Critical, Fatal, Unknown, Other
- `status` - New, In Progress, On Hold, Resolved, Closed
- `verdict` - Unknown, False Positive, True Positive, Disregard, Suspicious, Benign, Test, Insufficient Data, Security
  Risk, Managed Externally, Duplicate, Other
- `severity_ai` - AI-assessed severity
- `confidence_ai` - Unknown, Low, Medium, High, Other
- `attack_stage_ai` - MITRE ATT&CK tactics
- `comment_ai` - Markdown content (use #### as top-level heading)
- `summary_ai` - Markdown content (use #### as top-level heading)

**Process:**

1. Collect case ID and fields to update
2. Use MCP tool `update_case` with case ID and update fields
3. If result is `None`, state that the case was not found
4. Display updated fields confirmation

**Output format:**

**Case Updated Successfully**

Fields updated: [list of changed fields]

- Rowid
- Case ID
- Severity
- Status
- Verdict
- AI Severity
- AI Confidence
- Comment AI content
- Summary AI content

If full details are needed, suggest calling get_case after the update.

## Usage Flow

1. Ask user which operation they want to perform
2. Collect required parameters for the chosen operation
3. Execute the appropriate MCP tool
4. Format and present the results according to the operation's output specification
5. Handle errors gracefully (e.g., case not found, invalid parameters)
