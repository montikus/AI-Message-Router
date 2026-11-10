# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 
from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    ollama_timeout: float = Field(default=180, gt=0)
    ollama_keep_alive: str = "30m"
    smtp_host: str = "mailpit"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_timeout: float = Field(default=10, gt=0)
    mail_from: EmailStr = "router@example.com"
    max_concurrent_requests: int = Field(default=2, ge=1, le=16)
