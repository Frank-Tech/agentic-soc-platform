# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT BOOTSTRAP — agentic-soc-platform
# ═══════════════════════════════════════════════════════════════════════════════
#
# This file is ASP-SPECIFIC. It stubs out external dependencies so the adapter
# can run without real infrastructure (nocoly/SIRP, Qdrant, Redis, etc.).
#
# Each project writes their own bootstrap to handle their specific dependencies.
# If your project has no external deps to stub, this file can be empty.
#
# WHAT THIS FILE DOES:
#   1. Stubs Django cache (ASP uses it for lightweight caching)
#   2. Injects stub CONFIG modules (so PLUGIN imports don't crash)
#   3. Stubs the embeddings/Qdrant singleton (no vector DB needed for testing)
#   4. Patches SIRP (nocoly) to return mock data from the adapter's registry
#   5. Patches AlienVaultOTX to return safe stub results
#   6. Maps Langfuse env vars to the format the SDK expects
#
# EXECUTION: This module runs at import time (triggered by babelfish_adapter/__init__.py).
#            All patching happens BEFORE any playbook/agent code is imported.
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import sys
import types
from typing import Annotated

os.environ.setdefault("ASP_SKIP_SIRP", "1")


# ── 1. Django Cache Stub ─────────────────────────────────────────────────────
# ASP's Lib/xcache.py imports django.core.cache. We inject a minimal in-memory
# cache so the import succeeds without a real Django installation.

def _stub_django_cache() -> None:
    if "django" in sys.modules:
        return

    django_mod = types.ModuleType("django")
    django_core = types.ModuleType("django.core")
    django_cache = types.ModuleType("django.core.cache")

    class _StubCache:
        def __init__(self):
            self._d = {}

        def get(self, key, default=None):
            return self._d.get(key, default)

        def set(self, key, value, timeout=None):
            self._d[key] = value

        def delete(self, key):
            self._d.pop(key, None)

        def clear(self):
            self._d.clear()

    django_cache.cache = _StubCache()
    sys.modules["django"] = django_mod
    sys.modules["django.core"] = django_core
    sys.modules["django.core.cache"] = django_cache


# ── 2. CONFIG Module Stubs ───────────────────────────────────────────────────
# Each PLUGIN imports its CONFIG.py at module level. Instead of committing stub
# CONFIG.py files, we inject them into sys.modules before any PLUGIN is imported.
# This keeps the repo clean — developers create their own CONFIG.py from
# CONFIG.example.py for real usage.

def _stub_config_modules() -> None:
    configs = {
        "PLUGINS.LLM.CONFIG": {
            "LLM_CONFIGS": [
                {
                    "type": "openai",
                    "api_key": "sk-adapter-dummy",
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-4o",
                    "proxy": None,
                    "tags": ["cheap", "fast", "powerful", "function_calling", "structured_output"],
                }
            ],
        },
        "PLUGINS.SIRP.CONFIG": {
            "SIRP_URL": "http://localhost:0",
            "SIRP_APPKEY": "adapter-stub",
            "SIRP_SIGN": "adapter-stub",
            "SIRP_NOTICE_WEBHOOK": "http://localhost:0/stub",
        },
        "PLUGINS.SIEM.CONFIG": {
            "ELK_HOST": "http://localhost:9200",
            "ELK_USER": "",
            "ELK_PASS": "",
            "SPLUNK_HOST": "localhost",
            "SPLUNK_PORT": 8089,
            "SPLUNK_USER": "",
            "SPLUNK_PASS": "",
        },
        "PLUGINS.ELK.CONFIG": {
            "ELK_HOST": "http://localhost:9200",
            "ELK_USER": "",
            "ELK_PASS": "",
            "ACTION_INDEX_NAME": "siem-alert",
            "POLL_INTERVAL_MINUTES": 5,
        },
        "PLUGINS.Qdrant.CONFIG": {
            "QDRANT_URL": "http://localhost:6333",
            "QDRANT_API_KEY": "",
        },
        "PLUGINS.Embeddings.CONFIG": {
            "EMBEDDINGS_TYPE": "ollama",
            "EMBEDDINGS_API_KEY": "stub",
            "EMBEDDINGS_BASE_URL": "http://localhost:0",
            "EMBEDDINGS_MODEL": "stub",
            "EMBEDDINGS_PROXY": "",
            "EMBEDDINGS_SIZE": 1024,
        },
        "PLUGINS.AlienVaultOTX.CONFIG": {
            "HTTP_PROXY": None,
            "API_KEY": "",
        },
        "PLUGINS.Splunk.CONFIG": {
            "SPLUNK_HOST": "localhost",
            "SPLUNK_PORT": 8089,
            "SPLUNK_USER": "",
            "SPLUNK_PASS": "",
        },
        "PLUGINS.Redis.CONFIG": {
            "REDIS_URL": "redis://localhost:6379/",
            "REDIS_STREAM_MAX_LENGTH": 10000,
            "REDIS_MAX_CONNECTIONS": 10,
        },
    }

    for module_name, attrs in configs.items():
        if module_name in sys.modules:
            continue
        mod = types.ModuleType(module_name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        sys.modules[module_name] = mod


# ── 3. Embeddings/Qdrant Stub ────────────────────────────────────────────────
# PLUGINS/SIRP/sirpapi.py imports embeddings_qdrant at module level. We inject
# a stub module so no real Qdrant connection is needed.

def _stub_embeddings_qdrant() -> None:
    mod = types.ModuleType("PLUGINS.Embeddings.embeddings_qdrant")
    mod.SIRP_KNOWLEDGE_COLLECTION = "SIRP_KNOWLEDGE_COLLECTION"

    class _StubEmbeddingsAPI:
        def search_documents_with_rerank(self, *args, **kwargs):
            return []

        def search_documents(self, *args, **kwargs):
            return []

        def add_documents(self, *args, **kwargs):
            return None

        def delete_documents(self, *args, **kwargs):
            return None

    mod.embedding_api_singleton_qdrant = _StubEmbeddingsAPI()
    mod.EmbeddingsAPI = _StubEmbeddingsAPI
    sys.modules["PLUGINS.Embeddings.embeddings_qdrant"] = mod


# ── 4. SIRP (nocoly) Patch ───────────────────────────────────────────────────
# nocoly is a commercial low-code platform used as the SIRP backend. It can't
# be dockerized, so we monkey-patch BaseWorksheetEntity to return mock data
# from the adapter's registry, and Notice.send to no-op.

def _patch_sirp() -> None:
    from babelfish_adapter.core.adapter import lookup as _adapter_lookup
    from PLUGINS.SIRP.sirpbase import BaseWorksheetEntity

    @classmethod
    def _noop_get(cls, rowid, include_system_fields=True, lazy_load=False):
        entity = _adapter_lookup(rowid)
        if entity is None:
            return cls.MODEL_CLASS(rowid=rowid)
        return entity

    @classmethod
    def _noop_list(cls, filter_model, include_system_fields=True, lazy_load=False):
        return []

    @classmethod
    def _noop_list_by_rowids(cls, rowids, include_system_fields=True, lazy_load=False):
        return rowids if rowids else []

    @classmethod
    def _noop_create(cls, model):
        if getattr(model, "rowid", None) is None:
            import uuid as _uuid
            model.rowid = str(_uuid.uuid4())
        return model.rowid

    @classmethod
    def _noop_update(cls, model):
        return getattr(model, "rowid", None)

    @classmethod
    def _noop_update_or_create(cls, model):
        if getattr(model, "rowid", None) is None:
            import uuid as _uuid
            model.rowid = str(_uuid.uuid4())
        return model.rowid

    @classmethod
    def _noop_update_by_filter(cls, filter_model, model, include_system_fields=True):
        return {}

    @classmethod
    def _noop_batch_update_or_create(cls, model_list):
        if model_list is None:
            return None
        out = []
        for m in model_list:
            if isinstance(m, str):
                out.append(m)
            else:
                out.append(cls.update_or_create(m))
        return out

    BaseWorksheetEntity.get = _noop_get
    BaseWorksheetEntity.list = _noop_list
    BaseWorksheetEntity.list_by_rowids = _noop_list_by_rowids
    BaseWorksheetEntity.create = _noop_create
    BaseWorksheetEntity.update = _noop_update
    BaseWorksheetEntity.update_or_create = _noop_update_or_create
    BaseWorksheetEntity.update_by_filter = _noop_update_by_filter
    BaseWorksheetEntity.batch_update_or_create = _noop_batch_update_or_create

    from PLUGINS.SIRP.sirpapi import Notice

    @staticmethod
    def _noop_send(user, title, body=None):
        return True

    Notice.send = _noop_send


# ── 5. AlienVaultOTX Patch ───────────────────────────────────────────────────
# Stub OTX API calls to return safe "not malicious" results. Avoids hitting
# the real OTX API during testing.

def _patch_alienvault_otx() -> None:
    from PLUGINS.AlienVaultOTX.alienvaultotx import AlienVaultOTX

    _stub_result = {
        "malicious": False,
        "reputation_score": 0,
        "pulse_info": {"count": 0, "pulses": []},
        "note": "AlienVaultOTX stubbed in adapter",
    }

    @classmethod
    def _query_ip(
        cls,
        ip: Annotated[str, "IPv4 address to query"],
    ) -> Annotated[dict, "Threat intelligence result"]:
        """Query AlienVaultOTX for IP reputation."""
        return {**_stub_result, "indicator": ip, "indicator_type": "ip"}

    @classmethod
    def _query_url(
        cls,
        url: Annotated[str, "URL to query"],
    ) -> Annotated[dict, "Threat intelligence result"]:
        """Query AlienVaultOTX for URL reputation."""
        return {**_stub_result, "indicator": url, "indicator_type": "url"}

    @classmethod
    def _query_file(
        cls,
        file_hash: Annotated[str, "File hash (MD5/SHA1/SHA256) to query"],
    ) -> Annotated[dict, "Threat intelligence result"]:
        """Query AlienVaultOTX for file hash reputation."""
        return {**_stub_result, "indicator": file_hash, "indicator_type": "file"}

    AlienVaultOTX.query_ip = _query_ip
    AlienVaultOTX.query_url = _query_url
    AlienVaultOTX.query_file = _query_file


# ── 6. Langfuse Env Mapping ──────────────────────────────────────────────────
# Map CLIENT_LANGFUSE_* env vars (used by lexus-test) to LANGFUSE_* (used by
# the Langfuse SDK). This allows the adapter to use the same credentials.

def _apply_langfuse_env() -> None:
    os.environ.setdefault(
        "LANGFUSE_PUBLIC_KEY", os.environ.get("CLIENT_LANGFUSE_PUBLIC_KEY", "")
    )
    os.environ.setdefault(
        "LANGFUSE_SECRET_KEY", os.environ.get("CLIENT_LANGFUSE_SECRET_KEY", "")
    )
    os.environ.setdefault(
        "LANGFUSE_HOST", os.environ.get("CLIENT_LANGFUSE_HOST", "")
    )


# ── Execute all stubs/patches ────────────────────────────────────────────────
# Order matters: CONFIG stubs must be injected before importing any PLUGIN
# that reads its CONFIG at module level.

_stub_django_cache()
_stub_config_modules()
_stub_embeddings_qdrant()
_patch_sirp()
_patch_alienvault_otx()
_apply_langfuse_env()
