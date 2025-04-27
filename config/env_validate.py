from pydantic import BaseModel, Field, ValidationError, field_validator
from dotenv import dotenv_values


class EnvVars(BaseModel):
    DB_PATH: str | None = None
    LOCAL_TIMEZONE: str | None = None

    REFRESH_INTERVAL: float | None = Field(default=None, gt=0)
    SUMMARY_TRIGGER_LEN: int | None = Field(default=None, ge=0)
    POLL_INTERVAL: float | None = Field(default=None, gt=0)
    MAX_SUMMARY_THREADS: int | None = Field(default=None, ge=1)
    SUMMARY_MAX_TOKENS: int | None = Field(default=None, gt=0)
    SUMMARY_TEMPERATURE: float | None = Field(default=None, ge=0.0, le=1.0)

    OPENAI_API_KEY: str  # Required
    OPENAI_API_BASE_URL: str | None = None
    SUMMARY_MODEL: str | None = None
    INSIGHT_MODEL: str | None = None

    SUMMARY_PROMPT: str | None = None
    SUMMARY_FINAL_REMINDER: str | None = None

    @field_validator("OPENAI_API_KEY")
    def api_key_must_not_be_placeholder(v):
        """Ensure OPENAI_API_KEY is set and not left as a placeholder."""
        if not v or "YOUR_API_KEY" in v:
            raise ValueError("OPENAI_API_KEY must be set properly.")
        return v

    @field_validator("OPENAI_API_BASE_URL")
    def validate_api_base_url(v):
        """Ensure OPENAI_API_BASE_URL starts with http:// or https:// if provided."""
        if v is not None and not v.lower().startswith(("http://", "https://")):
            raise ValueError("OPENAI_API_BASE_URL must start with http:// or https://")
        return v


def validate_env(dotenv_path=".env"):
    env = dotenv_values(dotenv_path)

    try:
        EnvVars(**env)
    except ValidationError as e:
        print("❌ Environment validation failed:")
        print(str(e))
        raise SystemExit(1)
