import os
from typing import List, Dict

from Lib.configs import DATA_DIR


def _read_prompt(subdir: str, filename: str = "system_prompt.md") -> str:
    path = os.path.join(DATA_DIR, subdir, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


_FLOW_GROUPS = [
    {
        "entry_id": "l3_with_tools",
        "flow": {"name": "agent_siem", "prompt_dir": "Agent_SIEM"},
        "subflows": [],
    },
    {
        "entry_id": "threat_hunting",
        "flow": {"name": "agent_siem", "prompt_dir": "Agent_SIEM"},
        "subflows": [
            {"name": "agent_threat_intelligence", "prompt_dir": "Agent_Threat_Intelligence"},
        ],
    },
]


def list_flow_groups() -> List[Dict]:
    result = []
    for group in _FLOW_GROUPS:
        flow_def = group["flow"]
        entry = {
            "entry_id": group["entry_id"],
            "flow": {
                "name": flow_def["name"],
                "system_message": _read_prompt(flow_def["prompt_dir"]),
            },
            "subflows": [
                {
                    "name": sf["name"],
                    "system_message": _read_prompt(sf["prompt_dir"]),
                }
                for sf in group["subflows"]
            ],
        }
        result.append(entry)
    return result
