<<<<<<< HEAD
from pydantic import Field
=======
>>>>>>> 39418500c2accf02093099e7501f37cb9c6a6009
from pydantic_settings import BaseSettings
import os
from pathlib import Path

# Get the project root directory (parent of backend folder)
PROJECT_ROOT = Path(__file__).parent.parent

class Settings(BaseSettings):
    """Application configuration loaded from environment variables"""
    database_url: str
    
    # AI Provider Configuration
<<<<<<< HEAD
    ai_provider: str = "claude"  # "ollama" or "claude"
=======
    ai_provider: str = "ollama"  # "ollama" or "claude"
>>>>>>> 39418500c2accf02093099e7501f37cb9c6a6009
    
    # Ollama settings (for local development)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"
    
    # Claude API settings (for production)
<<<<<<< HEAD
    claude_api_key: str = Field("", alias="CLAUDE_API_KEY")
    claude_model: str = Field("claude-4-6-sonnet", alias="CLAUDE_MODEL")
    
    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        populate_by_name = True
=======
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"
    
    class Config:
        env_file = str(PROJECT_ROOT / ".env")
>>>>>>> 39418500c2accf02093099e7501f37cb9c6a6009

settings = Settings()
