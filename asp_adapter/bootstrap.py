import json
import os
import sys
import types
from typing import Annotated, Literal

os.environ.setdefault("ASP_SKIP_SIRP", "1")


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


_stub_django_cache()
_stub_embeddings_qdrant()
_patch_alienvault_otx()
_apply_langfuse_env()
