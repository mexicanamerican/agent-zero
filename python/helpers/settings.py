import asyncio
import json
import os
import re
import subprocess
from typing import Any, Literal, TypedDict

import models
from python.helpers import runtime, whisper, defer
from . import files, dotenv


class Settings(TypedDict):
    chat_model_provider: str
    chat_model_name: str
    chat_model_temperature: float
    chat_model_kwargs: dict[str, str]
    chat_model_ctx_length: int
    chat_model_ctx_history: float
    chat_model_rl_requests: int
    chat_model_rl_input: int
    chat_model_rl_output: int

    util_model_provider: str
    util_model_name: str
    util_model_temperature: float
    util_model_kwargs: dict[str, str]
    util_model_ctx_length: int
    util_model_ctx_input: float
    util_model_rl_requests: int
    util_model_rl_input: int
    util_model_rl_output: int

    embed_model_provider: str
    embed_model_name: str
    embed_model_kwargs: dict[str, str]
    embed_model_rl_requests: int
    embed_model_rl_input: int

    browser_model_provider: str
    browser_model_name: str
    browser_model_vision: bool
    browser_model_temperature: float
    browser_model_kwargs: dict[str, str]

    agent_prompts_subdir: str
    agent_memory_subdir: str
    agent_knowledge_subdir: str

    api_keys: dict[str, str]

    auth_login: str
    auth_password: str
    root_password: str

    rfc_auto_docker: bool
    rfc_url: str
    rfc_password: str
    rfc_port_http: int
    rfc_port_ssh: int

    stt_model_size: str
    stt_language: str
    stt_silence_threshold: float
    stt_silence_duration: int
    stt_waiting_timeout: int


class PartialSettings(Settings, total=False):
    pass


class FieldOption(TypedDict):
    value: str
    label: str


class SettingsField(TypedDict, total=False):
    id: str
    title: str
    description: str
    type: Literal["text", "number", "select", "range", "textarea", "password", "switch"]
    value: Any
    min: float
    max: float
    step: float
    options: list[FieldOption]


class SettingsSection(TypedDict, total=False):
    id: str
    title: str
    description: str
    fields: list[SettingsField]


class SettingsOutput(TypedDict):
    sections: list[SettingsSection]


PASSWORD_PLACEHOLDER = "****PSWD****"

SETTINGS_FILE = files.get_abs_path("tmp/settings.json")
_settings: Settings | None = None


def convert_out(settings: Settings) -> SettingsOutput:
    from models import ModelProvider

    # main model section
    chat_model_fields: list[SettingsField] = []
    chat_model_fields.append(
        {
            "id": "chat_model_provider",
            "title": "Chat model provider",
            "description": "Select provider for main chat model used by Agent Zero",
            "type": "select",
            "value": settings["chat_model_provider"],
            "options": [{"value": p.name, "label": p.value} for p in ModelProvider],
        }
    )
    chat_model_fields.append(
        {
            "id": "chat_model_name",
            "title": "Chat model name",
            "description": "Exact name of model from selected provider",
            "type": "text",
            "value": settings["chat_model_name"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_temperature",
            "title": "Chat model temperature",
            "description": "Determines the randomness of generated responses. 0 is deterministic, 1 is random",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.01,
            "value": settings["chat_model_temperature"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_ctx_length",
            "title": "Chat model context length",
            "description": "Maximum number of tokens in the context window for LLM. System prompt, chat history, RAG and response all count towards this limit.",
            "type": "number",
            "value": settings["chat_model_ctx_length"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_ctx_history",
            "title": "Context window space for chat history",
            "description": "Portion of context window dedicated to chat history visible to the agent. Chat history will automatically be optimized to fit. Smaller size will result in shorter and more summarized history. The remaining space will be used for system prompt, RAG and response.",
            "type": "range",
            "min": 0.01,
            "max": 1,
            "step": 0.01,
            "value": settings["chat_model_ctx_history"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_rl_requests",
            "title": "Requests per minute limit",
            "description": "Limits the number of requests per minute to the chat model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["chat_model_rl_requests"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_rl_input",
            "title": "Input tokens per minute limit",
            "description": "Limits the number of input tokens per minute to the chat model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["chat_model_rl_input"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_rl_output",
            "title": "Output tokens per minute limit",
            "description": "Limits the number of output tokens per minute to the chat model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["chat_model_rl_output"],
        }
    )

    chat_model_fields.append(
        {
            "id": "chat_model_kwargs",
            "title": "Chat model additional parameters",
            "description": "Any other parameters supported by the model. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["chat_model_kwargs"]),
        }
    )

    chat_model_section: SettingsSection = {
        "id": "chat_model",
        "title": "Chat Model",
        "description": "Selection and settings for main chat model used by Agent Zero",
        "fields": chat_model_fields,
    }

    # main model section
    util_model_fields: list[SettingsField] = []
    util_model_fields.append(
        {
            "id": "util_model_provider",
            "title": "Utility model provider",
            "description": "Select provider for utility model used by the framework",
            "type": "select",
            "value": settings["util_model_provider"],
            "options": [{"value": p.name, "label": p.value} for p in ModelProvider],
        }
    )
    util_model_fields.append(
        {
            "id": "util_model_name",
            "title": "Utility model name",
            "description": "Exact name of model from selected provider",
            "type": "text",
            "value": settings["util_model_name"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_temperature",
            "title": "Utility model temperature",
            "description": "Determines the randomness of generated responses. 0 is deterministic, 1 is random",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.01,
            "value": settings["util_model_temperature"],
        }
    )

    # util_model_fields.append(
    #     {
    #         "id": "util_model_ctx_length",
    #         "title": "Utility model context length",
    #         "description": "Maximum number of tokens in the context window for LLM. System prompt, message and response all count towards this limit.",
    #         "type": "number",
    #         "value": settings["util_model_ctx_length"],
    #     }
    # )
    # util_model_fields.append(
    #     {
    #         "id": "util_model_ctx_input",
    #         "title": "Context window space for input tokens",
    #         "description": "Portion of context window dedicated to input tokens. The remaining space can be filled with response.",
    #         "type": "range",
    #         "min": 0.01,
    #         "max": 1,
    #         "step": 0.01,
    #         "value": settings["util_model_ctx_input"],
    #     }
    # )

    util_model_fields.append(
        {
            "id": "util_model_rl_requests",
            "title": "Requests per minute limit",
            "description": "Limits the number of requests per minute to the utility model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["util_model_rl_requests"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_rl_input",
            "title": "Input tokens per minute limit",
            "description": "Limits the number of input tokens per minute to the utility model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["util_model_rl_input"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_rl_output",
            "title": "Output tokens per minute limit",
            "description": "Limits the number of output tokens per minute to the utility model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["util_model_rl_output"],
        }
    )

    util_model_fields.append(
        {
            "id": "util_model_kwargs",
            "title": "Utility model additional parameters",
            "description": "Any other parameters supported by the model. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["util_model_kwargs"]),
        }
    )

    util_model_section: SettingsSection = {
        "id": "util_model",
        "title": "Utility model",
        "description": "Smaller, cheaper, faster model for handling utility tasks like organizing memory, preparing prompts, summarizing.",
        "fields": util_model_fields,
    }

    # embedding model section
    embed_model_fields: list[SettingsField] = []
    embed_model_fields.append(
        {
            "id": "embed_model_provider",
            "title": "Embedding model provider",
            "description": "Select provider for embedding model used by the framework",
            "type": "select",
            "value": settings["embed_model_provider"],
            "options": [{"value": p.name, "label": p.value} for p in ModelProvider],
        }
    )
    embed_model_fields.append(
        {
            "id": "embed_model_name",
            "title": "Embedding model name",
            "description": "Exact name of model from selected provider",
            "type": "text",
            "value": settings["embed_model_name"],
        }
    )

    embed_model_fields.append(
        {
            "id": "embed_model_rl_requests",
            "title": "Requests per minute limit",
            "description": "Limits the number of requests per minute to the embedding model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["embed_model_rl_requests"],
        }
    )

    embed_model_fields.append(
        {
            "id": "embed_model_rl_input",
            "title": "Input tokens per minute limit",
            "description": "Limits the number of input tokens per minute to the embedding model. Waits if the limit is exceeded. Set to 0 to disable rate limiting.",
            "type": "number",
            "value": settings["embed_model_rl_input"],
        }
    )

    embed_model_fields.append(
        {
            "id": "embed_model_kwargs",
            "title": "Embedding model additional parameters",
            "description": "Any other parameters supported by the model. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["embed_model_kwargs"]),
        }
    )

    embed_model_section: SettingsSection = {
        "id": "embed_model",
        "title": "Embedding Model",
        "description": "Settings for the embedding model used by Agent Zero.",
        "fields": embed_model_fields,
    }

    # embedding model section
    browser_model_fields: list[SettingsField] = []
    browser_model_fields.append(
        {
            "id": "browser_model_provider",
            "title": "Web Browser model provider",
            "description": "Select provider for web browser model used by <a href='https://github.com/browser-use/browser-use' target='_blank'>browser-use</a> framework",
            "type": "select",
            "value": settings["browser_model_provider"],
            "options": [{"value": p.name, "label": p.value} for p in ModelProvider],
        }
    )
    browser_model_fields.append(
        {
            "id": "browser_model_name",
            "title": "Web Browser model name",
            "description": "Exact name of model from selected provider",
            "type": "text",
            "value": settings["browser_model_name"],
        }
    )

    browser_model_fields.append(
        {
            "id": "browser_model_vision",
            "title": "Use Vision",
            "description": "Models capable of Vision can use it to analyze web pages from screenshots. Increases quality but also token usage.",
            "type": "switch",
            "value": settings["browser_model_vision"],
        }
    )

    browser_model_fields.append(
        {
            "id": "browser_model_temperature",
            "title": "Web Browser model temperature",
            "description": "Determines the randomness of generated responses. 0 is deterministic, 1 is random",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.01,
            "value": settings["browser_model_temperature"],
        }
    )

    browser_model_fields.append(
        {
            "id": "browser_model_kwargs",
            "title": "Web Browser model additional parameters",
            "description": "Any other parameters supported by the model. Format is KEY=VALUE on individual lines, just like .env file.",
            "type": "textarea",
            "value": _dict_to_env(settings["browser_model_kwargs"]),
        }
    )

    browser_model_section: SettingsSection = {
        "id": "browser_model",
        "title": "Web Browser Model",
        "description": "Settings for the web browser model. Agent Zero uses <a href='https://github.com/browser-use/browser-use' target='_blank'>browser-use</a> agentic framework to handle web interactions.",
        "fields": browser_model_fields,
    }

    # # Memory settings section
    # memory_fields: list[SettingsField] = []
    # memory_fields.append(
    #     {
    #         "id": "memory_settings",
    #         "title": "Memory Settings",
    #         "description": "<settings for memory>",
    #         "type": "text",
    #         "value": "",
    #     }
    # )

    # memory_section: SettingsSection = {
    #     "id": "memory",
    #     "title": "Memory Settings",
    #     "description": "<settings for memory management here>",
    #     "fields": memory_fields,
    # }

    # basic auth section
    auth_fields: list[SettingsField] = []

    auth_fields.append(
        {
            "id": "auth_login",
            "title": "UI Login",
            "description": "Set user name for web UI",
            "type": "text",
            "value": dotenv.get_dotenv_value(dotenv.KEY_AUTH_LOGIN) or "",
        }
    )

    auth_fields.append(
        {
            "id": "auth_password",
            "title": "UI Password",
            "description": "Set user password for web UI",
            "type": "password",
            "value": (
                PASSWORD_PLACEHOLDER
                if dotenv.get_dotenv_value(dotenv.KEY_AUTH_PASSWORD)
                else ""
            ),
        }
    )

    if runtime.is_dockerized():
        auth_fields.append(
            {
                "id": "root_password",
                "title": "root Password",
                "description": "Change linux root password in docker container. This password can be used for SSH access. Original password was randomly generated during setup.",
                "type": "password",
                "value": "",
            }
        )

    auth_section: SettingsSection = {
        "id": "auth",
        "title": "Authentication",
        "description": "Settings for authentication to use Agent Zero Web UI.",
        "fields": auth_fields,
    }

    # api keys model section
    api_keys_fields: list[SettingsField] = []
    api_keys_fields.append(_get_api_key_field(settings, "openai", "OpenAI API Key"))
    api_keys_fields.append(
        _get_api_key_field(settings, "anthropic", "Anthropic API Key")
    )
    api_keys_fields.append(_get_api_key_field(settings, "groq", "Groq API Key"))
    api_keys_fields.append(_get_api_key_field(settings, "google", "Google API Key"))
    api_keys_fields.append(
        _get_api_key_field(settings, "deepseek", "DeepSeek API Key")
    )
    api_keys_fields.append(
        _get_api_key_field(settings, "openrouter", "OpenRouter API Key")
    )
    api_keys_fields.append(
        _get_api_key_field(settings, "sambanova", "Sambanova API Key")
    )
    api_keys_fields.append(
        _get_api_key_field(settings, "mistralai", "MistralAI API Key")
    )
    api_keys_fields.append(
        _get_api_key_field(settings, "huggingface", "HuggingFace API Key")
    )

    api_keys_section: SettingsSection = {
        "id": "api_keys",
        "title": "API Keys",
        "description": "API keys for model providers and services used by Agent Zero.",
        "fields": api_keys_fields,
    }

    # Agent config section
    agent_fields: list[SettingsField] = []

    agent_fields.append(
        {
            "id": "agent_prompts_subdir",
            "title": "Prompts Subdirectory",
            "description": "Subdirectory of /prompts folder to use for agent prompts. Used to adjust agent behaviour.",
            "type": "select",
            "value": settings["agent_prompts_subdir"],
            "options": [
                {"value": subdir, "label": subdir}
                for subdir in files.get_subdirectories("prompts")
            ],
        }
    )

    agent_fields.append(
        {
            "id": "agent_memory_subdir",
            "title": "Memory Subdirectory",
            "description": "Subdirectory of /memory folder to use for agent memory storage. Used to separate memory storage between different instances.",
            "type": "select",
            "value": settings["agent_memory_subdir"],
            "options": [
                {"value": subdir, "label": subdir}
                for subdir in files.get_subdirectories("memory", exclude="embeddings")
            ],
        }
    )

    agent_fields.append(
        {
            "id": "agent_knowledge_subdir",
            "title": "Knowledge subdirectory",
            "description": "Subdirectory of /knowledge folder to use for agent knowledge import. 'default' subfolder is always imported and contains framework knowledge.",
            "type": "select",
            "value": settings["agent_knowledge_subdir"],
            "options": [
                {"value": subdir, "label": subdir}
                for subdir in files.get_subdirectories("knowledge", exclude="default")
            ],
        }
    )

    agent_section: SettingsSection = {
        "id": "agent",
        "title": "Agent Config",
        "description": "Agent parameters.",
        "fields": agent_fields,
    }

    dev_fields: list[SettingsField] = []

    if runtime.is_development():
        # dev_fields.append(
        #     {
        #         "id": "rfc_auto_docker",
        #         "title": "RFC Auto Docker Management",
        #         "description": "Automatically create dockerized instance of A0 for RFCs using this instance's code base and, settings and .env.",
        #         "type": "text",
        #         "value": settings["rfc_auto_docker"],
        #     }
        # )

        dev_fields.append(
            {
                "id": "rfc_url",
                "title": "RFC Destination URL",
                "description": "URL of dockerized A0 instance for remote function calls. Do not specify port here.",
                "type": "text",
                "value": settings["rfc_url"],
            }
        )

    dev_fields.append(
        {
            "id": "rfc_password",
            "title": "RFC Password",
            "description": "Password for remote function calls. Passwords must match on both instances. RFCs can not be used with empty password.",
            "type": "password",
            "value": (
                PASSWORD_PLACEHOLDER
                if dotenv.get_dotenv_value(dotenv.KEY_RFC_PASSWORD)
                else ""
            ),
        }
    )

    if runtime.is_development():
        dev_fields.append(
            {
                "id": "rfc_port_http",
                "title": "RFC HTTP port",
                "description": "HTTP port for dockerized instance of A0.",
                "type": "text",
                "value": settings["rfc_port_http"],
            }
        )

        dev_fields.append(
            {
                "id": "rfc_port_ssh",
                "title": "RFC SSH port",
                "description": "SSH port for dockerized instance of A0.",
                "type": "text",
                "value": settings["rfc_port_ssh"],
            }
        )

    dev_section: SettingsSection = {
        "id": "dev",
        "title": "Development",
        "description": "Parameters for A0 framework development. RFCs (remote function calls) are used to call functions on another A0 instance. You can develop and debug A0 natively on your local system while redirecting some functions to A0 instance in docker. This is crucial for development as A0 needs to run in standardized environment to support all features.",
        "fields": dev_fields,
    }

    # Speech to text section
    stt_fields: list[SettingsField] = []

    stt_fields.append(
        {
            "id": "stt_model_size",
            "title": "Model Size",
            "description": "Select the speech recognition model size",
            "type": "select",
            "value": settings["stt_model_size"],
            "options": [
                {"value": "tiny", "label": "Tiny (39M, English)"},
                {"value": "base", "label": "Base (74M, English)"},
                {"value": "small", "label": "Small (244M, English)"},
                {"value": "medium", "label": "Medium (769M, English)"},
                {"value": "large", "label": "Large (1.5B, Multilingual)"},
                {"value": "turbo", "label": "Turbo (Multilingual)"},
            ],
        }
    )

    stt_fields.append(
        {
            "id": "stt_language",
            "title": "Language Code",
            "description": "Language code (e.g. en, fr, it)",
            "type": "text",
            "value": settings["stt_language"],
        }
    )

    stt_fields.append(
        {
            "id": "stt_silence_threshold",
            "title": "Silence threshold",
            "description": "Silence detection threshold. Lower values are more sensitive.",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.01,
            "value": settings["stt_silence_threshold"],
        }
    )

    stt_fields.append(
        {
            "id": "stt_silence_duration",
            "title": "Silence duration (ms)",
            "description": "Duration of silence before the server considers speaking to have ended.",
            "type": "text",
            "value": settings["stt_silence_duration"],
        }
    )

    stt_fields.append(
        {
            "id": "stt_waiting_timeout",
            "title": "Waiting timeout (ms)",
            "description": "Duration before the server closes the microphone.",
            "type": "text",
            "value": settings["stt_waiting_timeout"],
        }
    )

    stt_section: SettingsSection = {
        "id": "stt",
        "title": "Speech to Text",
        "description": "Voice transcription preferences and server turn detection settings.",
        "fields": stt_fields,
    }

    # Add the section to the result
    result: SettingsOutput = {
        "sections": [
            agent_section,
            chat_model_section,
            util_model_section,
            embed_model_section,
            browser_model_section,
            # memory_section,
            stt_section,
            api_keys_section,
            auth_section,
            dev_section,
        ]
    }
    return result


def _get_api_key_field(settings: Settings, provider: str, title: str) -> SettingsField:
    key = settings["api_keys"].get(provider, models.get_api_key(provider))
    return {
        "id": f"api_key_{provider}",
        "title": title,
        "type": "password",
        "value": (PASSWORD_PLACEHOLDER if key and key != "None" else ""),
    }


def convert_in(settings: dict) -> Settings:
    current = get_settings()
    for section in settings["sections"]:
        if "fields" in section:
            for field in section["fields"]:
                if field["value"] != PASSWORD_PLACEHOLDER:
                    if field["id"].endswith("_kwargs"):
                        current[field["id"]] = _env_to_dict(field["value"])
                    elif field["id"].startswith("api_key_"):
                        current["api_keys"][field["id"]] = field["value"]
                    else:
                        current[field["id"]] = field["value"]
    return current


def get_settings() -> Settings:
    global _settings
    if not _settings:
        _settings = _read_settings_file()
    if not _settings:
        _settings = get_default_settings()
    norm = normalize_settings(_settings)
    return norm


def set_settings(settings: Settings):
    global _settings
    _settings = normalize_settings(settings)
    _write_settings_file(_settings)
    _apply_settings()


def normalize_settings(settings: Settings) -> Settings:
    copy = settings.copy()
    default = get_default_settings()
    for key, value in default.items():
        if key not in copy:
            copy[key] = value
        else:
            try:
                copy[key] = type(value)(copy[key])  # type: ignore
            except (ValueError, TypeError):
                copy[key] = value  # make default instead
    return copy


# def get_chat_model(settings: Settings | None = None) -> BaseChatModel:
#     if not settings:
#         settings = get_settings()
#     return get_model(
#         type=ModelType.CHAT,
#         provider=ModelProvider[settings["chat_model_provider"]],
#         name=settings["chat_model_name"],
#         temperature=settings["chat_model_temperature"],
#         **settings["chat_model_kwargs"],
#     )


# def get_utility_model(settings: Settings | None = None) -> BaseChatModel:
#     if not settings:
#         settings = get_settings()
#     return get_model(
#         type=ModelType.CHAT,
#         provider=ModelProvider[settings["util_model_provider"]],
#         name=settings["util_model_name"],
#         temperature=settings["util_model_temperature"],
#         **settings["util_model_kwargs"],
#     )


# def get_embedding_model(settings: Settings | None = None) -> Embeddings:
#     if not settings:
#         settings = get_settings()
#     return get_model(
#         type=ModelType.EMBEDDING,
#         provider=ModelProvider[settings["embed_model_provider"]],
#         name=settings["embed_model_name"],
#         **settings["embed_model_kwargs"],
#     )


def _read_settings_file() -> Settings | None:
    if os.path.exists(SETTINGS_FILE):
        content = files.read_file(SETTINGS_FILE)
        parsed = json.loads(content)
        return normalize_settings(parsed)


def _write_settings_file(settings: Settings):
    _write_sensitive_settings(settings)
    _remove_sensitive_settings(settings)

    # write settings
    content = json.dumps(settings, indent=4)
    files.write_file(SETTINGS_FILE, content)


def _remove_sensitive_settings(settings: Settings):
    settings["api_keys"] = {}
    settings["auth_login"] = ""
    settings["auth_password"] = ""
    settings["rfc_password"] = ""
    settings["root_password"] = ""


def _write_sensitive_settings(settings: Settings):
    for key, val in settings["api_keys"].items():
        dotenv.save_dotenv_value(key.upper(), val)

    dotenv.save_dotenv_value(dotenv.KEY_AUTH_LOGIN, settings["auth_login"])
    if settings["auth_password"]:
        dotenv.save_dotenv_value(dotenv.KEY_AUTH_PASSWORD, settings["auth_password"])
    if settings["rfc_password"]:
        dotenv.save_dotenv_value(dotenv.KEY_RFC_PASSWORD, settings["rfc_password"])

    if settings["root_password"]:
        dotenv.save_dotenv_value(dotenv.KEY_ROOT_PASSWORD, settings["root_password"])
    if settings["root_password"]:
        set_root_password(settings["root_password"])


def get_default_settings() -> Settings:
    from models import ModelProvider

    return Settings(
        chat_model_provider=ModelProvider.OPENAI.name,
        chat_model_name="gpt-4o",
        chat_model_temperature=0.0,
        chat_model_kwargs={},
        chat_model_ctx_length=120000,
        chat_model_ctx_history=0.7,
        chat_model_rl_requests=0,
        chat_model_rl_input=0,
        chat_model_rl_output=0,
        util_model_provider=ModelProvider.OPENAI.name,
        util_model_name="gpt-4o-mini",
        util_model_temperature=0.0,
        util_model_ctx_length=120000,
        util_model_ctx_input=0.7,
        util_model_kwargs={},
        util_model_rl_requests=60,
        util_model_rl_input=0,
        util_model_rl_output=0,
        embed_model_provider=ModelProvider.OPENAI.name,
        embed_model_name="text-embedding-3-small",
        embed_model_kwargs={},
        embed_model_rl_requests=0,
        embed_model_rl_input=0,
        browser_model_provider=ModelProvider.OPENAI.name,
        browser_model_name="gpt-4o",
        browser_model_vision=False,
        browser_model_temperature=0.0,
        browser_model_kwargs={},
        api_keys={},
        auth_login="",
        auth_password="",
        root_password="",
        agent_prompts_subdir="default",
        agent_memory_subdir="default",
        agent_knowledge_subdir="custom",
        rfc_auto_docker=True,
        rfc_url="localhost",
        rfc_password="",
        rfc_port_http=55080,
        rfc_port_ssh=55022,
        stt_model_size="base",
        stt_language="en",
        stt_silence_threshold=0.3,
        stt_silence_duration=1000,
        stt_waiting_timeout=2000,
    )


def _apply_settings():
    global _settings
    if _settings:
        from agent import AgentContext
        from initialize import initialize

        for ctx in AgentContext._contexts.values():
            ctx.config = initialize()  # reinitialize context config with new settings
            # apply config to agents
            agent = ctx.agent0
            while agent:
                agent.config = ctx.config
                agent = agent.get_data(agent.DATA_NAME_SUBORDINATE)

        # reload whisper model if necessary
        task = defer.DeferredTask().start_task(whisper.preload, _settings["stt_model_size"]) #TODO overkill, replace with background task


def _env_to_dict(data: str):
    env_dict = {}
    line_pattern = re.compile(r"\s*([^#][^=]*)\s*=\s*(.*)")
    for line in data.splitlines():
        match = line_pattern.match(line)
        if match:
            key, value = match.groups()
            # Remove optional surrounding quotes (single or double)
            value = value.strip().strip('"').strip("'")
            env_dict[key.strip()] = value
    return env_dict


def _dict_to_env(data_dict):
    lines = []
    for key, value in data_dict.items():
        if "\n" in value:
            value = f"'{value}'"
        elif " " in value or value == "" or any(c in value for c in "\"'"):
            value = f'"{value}"'
        lines.append(f"{key}={value}")
    return "\n".join(lines)


def set_root_password(password: str):
    if not runtime.is_dockerized():
        raise Exception("root password can only be set in dockerized environments")
    subprocess.run(f"echo 'root:{password}' | chpasswd", shell=True, check=True)
    dotenv.save_dotenv_value(dotenv.KEY_ROOT_PASSWORD, password)


def get_runtime_config(set: Settings):
    if runtime.is_dockerized():
        return {
            "code_exec_ssh_addr": "localhost",
            "code_exec_ssh_port": 22,
            "code_exec_http_port": 80,
            "code_exec_ssh_user": "root",
        }
    else:
        host = set["rfc_url"]
        if "//" in host:
            host = host.split("//")[1]
        if ":" in host:
            host, port = host.split(":")
        if host.endswith("/"):
            host = host[:-1]
        return {
            "code_exec_ssh_addr": host,
            "code_exec_ssh_port": set["rfc_port_ssh"],
            "code_exec_http_port": set["rfc_port_http"],
            "code_exec_ssh_user": "root",
        }