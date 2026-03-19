import os
import sys
import uuid

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from mcp.server import FastMCP
from Lib.configs import BASE_DIR

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ASP.settings")
    import django

    django.setup()

    # Define UUID file path
    uuid_file_path = os.path.join(BASE_DIR, "Docker", "mcp_uuid")
    # Try to read UUID from file
    try:
        with open(uuid_file_path, 'r') as f:
            uuid_str = f.read().strip()
    except FileNotFoundError:
        # If file doesn't exist, generate new UUID and save it
        uuid_str = str(uuid.uuid1()).replace('-', "")[0:16]
        os.makedirs(os.path.dirname(uuid_file_path), exist_ok=True)
        with open(uuid_file_path, 'w') as f:
            f.write(uuid_str)

    mcp = FastMCP("ASP-MCP")
    host = "0.0.0.0"
    port = 7001
    mcp.settings.sse_path = f"/{uuid_str}/sse"
    mcp.settings.message_path = f"/{uuid_str}/messages"

    mcp.settings.host = host
    mcp.settings.port = port

    # add tools
    from PLUGINS.MCP.llmfunc import (
        attach_artifact_to_alert,
        attach_enrichment_to_target,
        attach_ticket_to_case,
        create_artifact,
        create_enrichment,
        create_ticket,
        execute_playbook,
        get_alert_discussions,
        get_case_discussions,
        list_alerts,
        list_available_playbook_definitions,
        list_artifacts,
        list_cases,
        list_knowledge,
        list_playbook_runs,
        list_tickets,
        update_alert,
        update_case,
        update_knowledge,
        update_ticket,
        siem_adaptive_query,
        siem_explore_schema,
        siem_keyword_search,
        get_current_time,
    )

    mcp.add_tool(attach_artifact_to_alert)
    mcp.add_tool(attach_enrichment_to_target)
    mcp.add_tool(attach_ticket_to_case)
    mcp.add_tool(create_artifact)
    mcp.add_tool(create_enrichment)
    mcp.add_tool(create_ticket)
    mcp.add_tool(execute_playbook)
    mcp.add_tool(get_alert_discussions)
    mcp.add_tool(get_case_discussions)
    mcp.add_tool(list_alerts)
    mcp.add_tool(list_available_playbook_definitions)
    mcp.add_tool(list_artifacts)
    mcp.add_tool(list_cases)
    mcp.add_tool(list_knowledge)
    mcp.add_tool(list_playbook_runs)
    mcp.add_tool(list_tickets)
    mcp.add_tool(update_alert)
    mcp.add_tool(update_case)
    mcp.add_tool(update_knowledge)
    mcp.add_tool(update_ticket)
    mcp.add_tool(siem_adaptive_query)
    mcp.add_tool(siem_explore_schema)
    mcp.add_tool(siem_keyword_search)
    mcp.add_tool(get_current_time)

    print(f"mcp server url: http://your_server_ip:{port}/{uuid_str}/sse")
    mcp.run(transport="sse")
