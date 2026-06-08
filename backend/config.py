from pydantic import Field
from pydantic_settings import BaseSettings
import os
from pathlib import Path

# Get the project root directory (parent of backend folder)
PROJECT_ROOT = Path(__file__).parent.parent

class Settings(BaseSettings):
    """Application configuration loaded from environment variables"""
    database_url: str
    
    # AI Provider Configuration
    ai_provider: str = "claude"  # "ollama" or "claude"
    
    # Ollama settings (for local development)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"
    
    # Claude API settings (for production)
    claude_api_key: str = Field("", alias="CLAUDE_API_KEY")
    claude_model: str = Field("claude-4-6-sonnet", alias="CLAUDE_MODEL")
    
    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        populate_by_name = True

settings = Settings()
