import os
from typing import List, Dict

from Lib.configs import DATA_DIR


_SUBFLOW_DEFS = [
    {"name": "agent_siem", "prompt_path": os.path.join(DATA_DIR, "Agent_SIEM", "system_prompt.md"), "trigger": True},
    {"name": "agent_threat_intelligence", "prompt_path": os.path.join(DATA_DIR, "Agent_Threat_Intelligence", "system_prompt.md")},
]


def list_subflows() -> List[Dict[str, str]]:
    result = []
    for sf in _SUBFLOW_DEFS:
        with open(sf["prompt_path"], "r", encoding="utf-8") as f:
            content = f.read()
        entry = {"name": sf["name"], "system_message": content}
        if sf.get("trigger"):
            entry["trigger"] = True
        result.append(entry)
    return result
