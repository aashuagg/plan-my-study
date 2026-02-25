from pydantic_settings import BaseSettings
import os
from pathlib import Path

# Get the project root directory (parent of backend folder)
PROJECT_ROOT = Path(__file__).parent.parent

class Settings(BaseSettings):
    """Application configuration loaded from environment variables"""
    database_url: str
    
    # AI Provider Configuration
    ai_provider: str = "ollama"  # "ollama" or "claude"
    
    # Ollama settings (for local development)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"
    
    # Claude API settings (for production)
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"
    
    class Config:
        env_file = str(PROJECT_ROOT / ".env")

settings = Settings()
