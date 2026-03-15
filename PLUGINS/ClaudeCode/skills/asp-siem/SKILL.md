---
name: asp-siem
description: SIEM search and investigation operations for the Agentic SOC Platform, currently focused on keyword-based search across ELK and Splunk backends.
compatibility: connect to asp mcp server
metadata:
  author: Funnywolf
  version: 0.1.0
  mcp-server: asp
  category: cyber security
  tags: [ siem, search, soc ]
  documentation: https://asp.viperrtp.com/
---

# ASP SIEM

This skill provides SIEM search and investigation capabilities for the Agentic SOC Platform.

## Available Operations

Ask the user which operation they want to perform:

1. **Keyword search** - Search logs by IP, hostname, username, hash, or any arbitrary keyword across one or more SIEM
   indices

This skill currently focuses on `siem_keyword_search`. More SIEM operations can be added later using the same structure.

## Operation Details

### 1. Keyword Search

**Required parameters:**

- `keyword` - Search keyword. Can be an IP address, hostname, username, email, hash, process name, domain, or any string
- `time_range_start` - Start time in UTC ISO8601 format, for example `2026-02-04T06:00:00Z`
- `time_range_end` - End time in UTC ISO8601 format, for example `2026-02-04T07:00:00Z`

**Optional parameters:**

- `time_field` - Time field used for the range filter. Default is `@timestamp`. Common alternatives include
  `event.created` and `_time`
- `index_name` - Target SIEM index/source name. If omitted, search across all available indices and backends. If
  provided, search only that specific index

**Process:**

1. Collect the keyword and time range from the user
2. If the user knows the target data source, collect `index_name`; otherwise leave it empty for cross-index search
3. If the target source uses a non-default time field, collect `time_field`; otherwise use `@timestamp`
4. Use MCP tool `siem_keyword_search` with the collected parameters
5. Parse each returned JSON string
6. If the result list is empty, state that no matching logs were found in the specified time range
7. Present results grouped by backend and index when multiple results are returned

**Behavior notes:**

- If `index_name` is not provided, the tool searches across available ELK and Splunk indices
- The tool returns adaptive results based on hit volume:
    - `full` - complete matching records for smaller result sets
    - `sample` - statistics plus representative sample records for medium result sets
    - `summary` - statistics only for large result sets
- Time values must be UTC and end with `Z`

**Output format:**

**Search Overview**

- Keyword
- Time range start/end
- Time field
- Searched index or `all indices`
- Total result groups

**Per Result Group**

- Backend
- Index distribution
- Status
- Total hits
- Message

**Statistics**

- For each field statistic: field name and top values with counts

**Sample Records**

- Show representative records when `records` is not empty
- Prefer highlighting timestamp, source index, host, user, IP, process, event/action, and other directly relevant fields
  when present

**Suggested rendering:**

| Backend | Status | Total Hits | Index Distribution | Message |
|---------|--------|------------|--------------------|---------|
| ...     | ...    | ...        | ...                | ...     |

Then provide statistics and sample records under each result group.

## Usage Flow

1. Ask user which SIEM operation they want to perform
2. Collect required parameters for the chosen operation
3. Execute the appropriate MCP tool
4. Format and present the results according to the operation's output specification
5. Handle errors gracefully, such as invalid UTC time format, unsupported index, backend connection issues, or no
   matching logs
