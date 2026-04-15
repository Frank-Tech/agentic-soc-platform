import os
import re

import httpx
import urllib3
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from Lib.log import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from PLUGINS.LLM.CONFIG import LLM_CONFIGS

try:
    from babelfish_adapter.core.context import babelfish_context as _babelfish_context
except Exception:
    _babelfish_context = None


class LLMAPI(object):
    """
    A general-purpose LLM API client.
    It automatically reads the configuration from CONFIG.py and initializes the corresponding backend.
    Supports dynamic selection of model configurations through tags.
    It throws exceptions directly when it encounters an error.

    When running under the babelfish adapter, every call to ``get_model`` MUST
    pass an explicit ``session_id``. There is no implicit default — the
    previous ContextVar-based inheritance was removed to make collisions
    between concurrent subflow invocations impossible (every role is now
    responsible for minting its own UUID4 and passing it at the LLM call site).
    """

    def __init__(self, temperature: float = 0.0):
        """
        Initializes the LLM API client.
        Loads the configuration list from LLM_CONFIGS in CONFIG.py.
        """
        if not LLM_CONFIGS or not isinstance(LLM_CONFIGS, list):
            raise ValueError("LLM_CONFIGS in CONFIG.py is missing, empty, or not a list.")

        self.configs = LLM_CONFIGS
        self.default_config = self.configs[0]
        self.temperature = temperature
        self.alive = False

    def get_model(
        self,
        tag: str | list[str] | None = None,
        *,
        session_id: str | None = None,
        **kwargs,
    ) -> ChatOpenAI | ChatOllama:
        """
        Gets and returns the corresponding LangChain ChatModel instance based on the tag.

        Args:
            tag (str | list[str], optional):
                - str: Find the first configuration that contains this tag.
                - list[str]: Find the first configuration that contains all of these tags.
                - None: Use the first default configuration in the list.
            session_id: REQUIRED when running under the babelfish adapter. The
                UUID4 that will be sent as ``X-Session-ID`` and used as the
                LangGraph ``thread_id``. Each flow role (parent flow, every
                subflow) is responsible for minting its own fresh UUID4 and
                passing it here — there is no implicit default from ContextVar
                state. Pass ``None`` only when outside the adapter runtime
                (tests, standalone scripts, native CLI usage).
            **kwargs: Allows overriding model parameters at call time (e.g., temperature, model).

        Raises:
            ValueError: If no configuration matching the specified tag (or list of tags) is found.
            ValueError: If the client_type in the configuration is not supported.
            RuntimeError: If called inside a babelfish adapter context without
                an explicit ``session_id``.

        Returns:
            ChatOpenAI | ChatOllama: LangChain's chat model instance.
        """
        selected_config = None

        if tag is None:
            selected_config = self.default_config
        else:
            for config in self.configs:
                config_tags = set(config.get("tags", []))

                # If tag is a list, check if all required tags exist
                if isinstance(tag, list):
                    required_tags = set(tag)
                    if required_tags.issubset(config_tags):
                        selected_config = config
                        break
                # If tag is a string, check if the tag exists
                elif isinstance(tag, str):
                    if tag in config_tags:
                        selected_config = config
                        break

        if selected_config is None:
            raise ValueError(f"No LLM configuration found matching tag(s): '{tag}'")

        logger.debug(f"Using LLM configuration, base_url: {selected_config.get("base_url")} model: {selected_config.get("model")}")
        # Prepare model parameters
        params = {
            "temperature": self.temperature,
            "model": selected_config.get("model"),
        }
        # Update kwargs to allow overriding default values at runtime
        params.update(kwargs)

        client_type = selected_config.get("type")

        ctx = _babelfish_context.get() if _babelfish_context is not None else None
        if ctx is not None:
            if session_id is None:
                raise RuntimeError(
                    "LLMAPI.get_model() called inside a babelfish adapter context "
                    "without an explicit session_id. Every flow role (parent flow, "
                    "every subflow) must mint its own UUID4 and pass it explicitly "
                    "to prevent X-Session-ID collisions between concurrent "
                    "invocations. See babelfish_adapter/core/context.py."
                )
            # ─────────────────────────────────────────────────────────────
            # A-design model precedence (lexus-test integration).
            #
            # BEFORE (bug):
            #   params["model"] = os.environ.get("ASP_ADAPTER_MODEL", "gpt-4o")
            #
            # That re-read an env var at call time. ``bootstrap.py`` also
            # read the same env var — but at IMPORT time, freezing it into
            # ``LLM_CONFIGS``. When the two readers saw different
            # environments (e.g. one baseline task without the context
            # variable set, one babelfish task with it), the same process
            # resolved two different model names. That's exactly what
            # happened in suite_run 325: baseline ran on gpt-4o-2024-08-06
            # and nexus ran on gpt-4o, and gpt-4o's json_schema output
            # drift caused the analyst subgraph to never trigger.
            #
            # NOW (fix):
            #   1. If lexus-test pinned a model via
            #      ``babelfish_context["model_override"]`` — use it.
            #   2. Otherwise fall back to ``selected_config.get("model")``,
            #      which is what ``LLM_CONFIGS`` resolved at bootstrap time
            #      (the adapter's pre-existing source). Standalone adapter
            #      usage (no context override) keeps working unchanged.
            # Both branches now read from a single source per invocation,
            # so baseline and babelfish in the same process always agree.
            # ─────────────────────────────────────────────────────────────
            model_override = ctx.get("model_override")
            params["model"] = model_override or selected_config.get("model")
            params["api_key"] = os.environ["OPENAI_API_KEY"]
            params["http_client"] = None
            if ctx.get("mode") == "babelfish":
                params["base_url"] = os.environ["OPENAI_BASE_URL"]
                params["default_headers"] = {
                    "X-Session-ID": session_id,
                    "X-Flow-ID": ctx["flow_id"],
                    "X-Api-Key": os.environ["NEXUS_API_KEY"],
                    "X-Auto-Approve": "true",
                }
            else:
                params["base_url"] = "https://api.openai.com/v1"
            return ChatOpenAI(**params)

        if client_type == 'openai':
            params.update({
                "base_url": selected_config.get("base_url"),
                "api_key": selected_config.get("api_key"),
                "http_client": httpx.Client(proxy=selected_config.get("proxy")) if selected_config.get("proxy") else None,
            })
            return ChatOpenAI(**params)

        elif client_type == 'ollama':
            params.update({
                "base_url": selected_config.get("base_url"),
            })
            # Ollama doesn't use api_key or http_client in the same way
            return ChatOllama(**params)
        else:
            raise ValueError(f"Unsupported client_type: {client_type}")

    def alive_check(self):
        for config in self.configs:
            params = {
                "temperature": self.temperature,
                "model": config.get("model"),
            }
            client_type = config.get("type")
            if client_type == 'openai':
                params.update({
                    "base_url": config.get("base_url"),
                    "api_key": config.get("api_key"),
                    "http_client": httpx.Client(proxy=config.get("proxy")) if config.get("proxy") else None,
                })
                model = ChatOpenAI(**params)
                if self.is_alive(model):
                    print(f"{config} is alive.")
                else:
                    print(f"{config} is not alive.")

            elif client_type == 'ollama':
                params.update({
                    "base_url": config.get("base_url"),
                })
                model = ChatOllama(**params)
                if self.is_alive(model):
                    print(f"{config} is alive.")
                else:
                    print(f"{config} is not alive.")
            else:
                print(f"{config} error")

    def is_alive(self, model: ChatOpenAI | ChatOllama) -> bool:
        """
        Tests basic connectivity with the default model.
        Returns True on success, otherwise throws an exception directly (e.g., ConnectionError, ValueError).
        """
        parser = StrOutputParser()
        chain = model | parser
        messages = [
            ("system", "When you receive 'ping', you must reply with 'pong'."),
            ("human", "ping"),
        ]

        # Any network or API errors will be thrown here naturally as exceptions
        ai_msg = chain.invoke(messages)

        if "pong" not in ai_msg.lower():
            # Even if the connection is successful, but the response does not meet expectations, it is considered a failure
            self.alive = False
            raise ValueError(f"Model liveness check failed. Expected 'pong', got: {ai_msg}")

        self.alive = True
        return True

    def is_support_function_calling(self, tag: str = None) -> bool:
        """
        Tests whether the specified (or default) model supports function calling (Tool Calling) capabilities.
        Returns True on success, otherwise throws an exception directly.
        """

        def test_func(x: str) -> str:
            """A test function that returns the input string."""
            return x

        model = self.get_model(tag=tag)
        model_with_tools = model.bind_tools([test_func])
        test_messages = [
            ("system", "When user says test, call test_func with 'hello' as argument."),
            ("human", "test"),
        ]

        response = model_with_tools.invoke(test_messages)

        if not response.tool_calls:
            raise ValueError("Model responded but did not use the requested tool.")

        return True

    @staticmethod
    def extract_think(message: AIMessage) -> AIMessage:
        """
        Checks if a <think>...</think> tag exists at the beginning of the AIMessage content.
        Temporary solution for a Langchain Bug
        If it exists, it will:
        1. Extract the content within the <think> tag.
        2. Store the extracted content in message.additional_kwargs['reasoning_content'].
        3. Remove the <think>...</think> tag block from message.content.
        4. Return a new, modified AIMessage object.

        If it does not exist, the original message object is returned as is.

        Args:
            message: The LangChain AIMessage object to be processed.

        Returns:
            A processed AIMessage object, or the original object if there is no match.
        """
        # Ensure content is a string type
        if not isinstance(message.content, str):
            return message

        # Regular expression to match the <think> tag at the beginning and capture its content.
        # The re.DOTALL flag allows '.' to match any character, including newlines.
        # `^`      - matches the beginning of the string
        # `<think>`- matches the literal <think>
        # `(.*?)`  - non-greedily captures all characters until the next pattern
        # `</think>`- matches the literal </think>
        # `\s*`    - matches any whitespace characters (including newlines) after the think tag
        pattern = r"^<think>(.*?)</think>\s*"

        match = re.match(pattern, message.content, re.DOTALL)

        if match:
            # Extract the content of capture group 1, which is the text inside the <think> tag
            reasoning_content = match.group(1).strip()

            # Remove the entire matched <think>...</think> part from the original content
            new_content = message.content[match.end():]

            # Create a copy of additional_kwargs for modification
            # This is to avoid directly modifying the original dictionary that may be referenced elsewhere
            updated_kwargs = message.additional_kwargs.copy()
            updated_kwargs['reasoning_content'] = reasoning_content

            # Return a new AIMessage instance because LangChain message objects are immutable
            message.additional_kwargs = updated_kwargs
            message.content = new_content
            return message
        else:
            # If there is no match, return the original message
            return message


if __name__ == "__main__":
    LLMAPI().alive_check()
