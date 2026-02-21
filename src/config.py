import os
from dotenv import load_dotenv

load_dotenv()

def get_env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return val

class Settings:
    DD_API_KEY = get_env("DD_API_KEY")
    DD_APP_KEY = get_env("DD_APP_KEY")
    DD_SITE = get_env("DD_SITE", "datadoghq.com")

    BRAINTRUST_API_KEY = get_env("BRAINTRUST_API_KEY")
    BRAINTRUST_PROJECT = get_env("BRAINTRUST_PROJECT", "voiceops")

    ELEVENLABS_API_KEY = get_env("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID = get_env("ELEVENLABS_VOICE_ID")

    LLM_PROVIDER = get_env("LLM_PROVIDER")
    LLM_API_KEY = get_env("LLM_API_KEY")
    LLM_MODEL = get_env("LLM_MODEL")