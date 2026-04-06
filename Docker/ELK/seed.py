import json
import os
import random
import sys

import httpx

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _REPO_ROOT)

ELK_HOST = os.environ.get("ELK_SEED_HOST", "http://localhost:9200")
ELK_USER = os.environ.get("ELK_SEED_USER", "")
ELK_PASS = os.environ.get("ELK_SEED_PASS", "")
SEED = int(os.environ.get("ELK_SEED_VALUE", "42"))
BASELINE_BATCHES = int(os.environ.get("ELK_SEED_BASELINE_BATCHES", "10"))
BASELINE_BATCH_SIZE = int(os.environ.get("ELK_SEED_BASELINE_BATCH_SIZE", "50"))

random.seed(SEED)

from PLUGINS.Mock.SIEM import settings
from PLUGINS.Mock.SIEM.generator.cloud import CloudGenerator
from PLUGINS.Mock.SIEM.generator.host import HostGenerator
from PLUGINS.Mock.SIEM.generator.network import NetworkGenerator
from PLUGINS.Mock.SIEM.scenarios.cloud import CloudPrivilegeEscalationScenario
from PLUGINS.Mock.SIEM.scenarios.host import RansomwareScenario
from PLUGINS.Mock.SIEM.scenarios.network import BruteForceScenario


def _auth():
    if ELK_USER and ELK_PASS:
        return (ELK_USER, ELK_PASS)
    return None


def recreate_index(client: httpx.Client, index_name: str) -> None:
    client.delete(f"{ELK_HOST}/{index_name}", auth=_auth())
    resp = client.put(
        f"{ELK_HOST}/{index_name}",
        json={"settings": {"number_of_shards": 1, "number_of_replicas": 0}},
        auth=_auth(),
    )
    if resp.status_code >= 400:
        raise Exception(f"Failed to create index {index_name}: {resp.text}")
    print(f"[seed] recreated index: {index_name}")


def bulk_send(client: httpx.Client, index_name: str, docs: list) -> None:
    if not docs:
        return
    payload_lines = []
    for doc in docs:
        payload_lines.append(json.dumps({"index": {"_index": index_name}}))
        payload_lines.append(json.dumps(doc))
    payload = "\n".join(payload_lines) + "\n"
    resp = client.post(
        f"{ELK_HOST}/_bulk",
        content=payload,
        auth=_auth(),
        headers={"Content-Type": "application/x-ndjson"},
    )
    if resp.status_code >= 400:
        raise Exception(f"Bulk send failed: {resp.text}")


def main():
    indices_generators_scenarios = [
        (settings.NET_INDEX, NetworkGenerator, BruteForceScenario),
        (settings.HOST_INDEX, HostGenerator, RansomwareScenario),
        (settings.CLOUD_INDEX, CloudGenerator, CloudPrivilegeEscalationScenario),
    ]

    with httpx.Client(verify=False, timeout=60.0) as client:
        for index_name, GeneratorClass, ScenarioClass in indices_generators_scenarios:
            recreate_index(client, index_name)

            generator = GeneratorClass()
            for _ in range(BASELINE_BATCHES):
                batch = [generator.generate() for _ in range(BASELINE_BATCH_SIZE)]
                bulk_send(client, index_name, batch)

            scenario = ScenarioClass()
            bulk_send(client, index_name, scenario.get_logs())

            print(f"[seed] {index_name}: {BASELINE_BATCHES*BASELINE_BATCH_SIZE} baseline docs + 1 scenario")

        client.post(f"{ELK_HOST}/_refresh", auth=_auth())
        print("[seed] refresh completed")


if __name__ == "__main__":
    main()
