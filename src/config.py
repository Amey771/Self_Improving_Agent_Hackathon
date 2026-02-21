import os
from dotenv import load_dotenv

load_dotenv()

def get_env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return val

def get_env_float(name: str, default: float) -> float:
    val = get_env(name)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default

def get_env_bool(name: str, default: bool) -> bool:
    val = get_env(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}

def get_env_int(name: str, default: int) -> int:
    val = get_env(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default

class Settings:
    DD_API_KEY = get_env("DD_API_KEY")
    DD_APP_KEY = get_env("DD_APP_KEY")
    DD_SITE = get_env("DD_SITE", "datadoghq.com")

    BRAINTRUST_API_KEY = get_env("BRAINTRUST_API_KEY")
    BRAINTRUST_PROJECT = get_env("BRAINTRUST_PROJECT", "voiceops")
    BRAINTRUST_API_URL = get_env("BRAINTRUST_API_URL")

    ELEVENLABS_API_KEY = get_env("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID = get_env("ELEVENLABS_VOICE_ID")
    ELEVENLABS_MODEL_ID = get_env("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    ELEVENLABS_STABILITY = get_env_float("ELEVENLABS_STABILITY", 0.35)
    ELEVENLABS_SIMILARITY_BOOST = get_env_float("ELEVENLABS_SIMILARITY_BOOST", 0.85)
    ELEVENLABS_STYLE = get_env_float("ELEVENLABS_STYLE", 0.2)
    ELEVENLABS_USE_SPEAKER_BOOST = get_env_bool("ELEVENLABS_USE_SPEAKER_BOOST", True)
    REMEDIATION_VALIDATION_CMD = get_env("REMEDIATION_VALIDATION_CMD", "python -m compileall app src")
    AI_MAX_FIX_ATTEMPTS = get_env_int("AI_MAX_FIX_ATTEMPTS", 3)

    LLM_PROVIDER = get_env("LLM_PROVIDER")
    LLM_API_KEY = get_env("LLM_API_KEY")
    LLM_MODEL = get_env("LLM_MODEL")
