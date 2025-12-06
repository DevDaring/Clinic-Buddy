"""
Application configuration and environment variables management.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv("secrets/.env")

# Set Google Application Credentials environment variable for Speech & TTS
credentials_env = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if credentials_env:
    credentials_path = credentials_env
    # Convert to absolute path if relative
    if not os.path.isabs(credentials_path):
        base_dir = Path(__file__).resolve().parent.parent
        credentials_path = str(base_dir / credentials_path)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application Settings
    APP_NAME: str = "Clinic-Buddy"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_PORT: int = 8000
    APP_HOST: str = "0.0.0.0"
    
    # Google Cloud Settings
    GOOGLE_PROJECT_ID: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    VERTEX_AI_LOCATION: str = "us-central1"
    GOOGLE_API_KEY: Optional[str] = None
    
    # Model Configuration (from .env)
    LOCAL_MODEL: Optional[int] = None  # 1 = use local model, 0 = use API
    HUGGINGFACE_MODEL_URL: Optional[str] = None  # HuggingFace model URL from .env
    HF_TOKEN: Optional[str] = None  # HuggingFace token for gated models
    GEMINI_API_KEY: Optional[str] = None  # Gemini API key (kept for backward compatibility)
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"  # Gemini model (kept for backward compatibility)
    
    # AWS Bedrock Configuration (Claude Sonnet 4.5)
    AWS_USER_NAME: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_SONNET_45: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    
    # Model Parameters
    MODEL_PATH: str = "./models/gemma"
    GPU_MEMORY_FRACTION: float = 0.8
    MAX_BATCH_SIZE: int = 32
    MODEL_MAX_LENGTH: int = 2048
    TEMPERATURE: float = 0.7
    TOP_P: float = 0.9
    
    # API Keys
    LANGCHAIN_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Database Configuration
    DATA_DIR: str = "./data"
    TRIALS_CSV: str = "./data/trials.csv"
    DRUGS_CSV: str = "./data/drugs.csv"
    PATIENTS_CSV: str = "./data/patients.csv"
    OUTCOMES_CSV: str = "./data/outcomes.csv"
    SIMULATION_RESULTS_CSV: str = "./data/simulation_results.csv"
    CHAT_HISTORY_CSV: str = "./data/chat_history.csv"
    
    # Simulation Parameters
    DEFAULT_PATIENT_COUNT: int = 100
    DEFAULT_TRIAL_DURATION: int = 365  # days
    DEFAULT_DROPOUT_RATE: float = 0.15
    SUCCESS_THRESHOLD: float = 0.7
    
    # Agent Configuration
    AGENT_TIMEOUT: int = 120  # seconds
    MAX_AGENT_ITERATIONS: int = 5
    AGENT_VERBOSE: bool = True
    
    # CORS Settings
    CORS_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]
    
    # Cache Settings
    ENABLE_CACHE: bool = True
    CACHE_TTL: int = 3600  # seconds
    
    class Config:
        env_file = "secrets/.env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Directory setup
def setup_directories():
    """Create necessary directories if they don't exist."""
    settings = get_settings()
    
    directories = [
        settings.DATA_DIR,
        settings.MODEL_PATH,
        "./static/css",
        "./static/js",
        "./static/images",
        "./templates",
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


# Constants
TRIAL_PHASES = ["Phase I", "Phase II", "Phase III", "Phase IV"]
TRIAL_STATUSES = ["Planning", "Active", "Completed", "Terminated", "Suspended"]
ADVERSE_EVENT_SEVERITIES = ["Mild", "Moderate", "Severe", "Life-threatening"]
THERAPEUTIC_AREAS = [
    "Oncology",
    "Cardiology",
    "Neurology",
    "Infectious Disease",
    "Immunology",
    "Endocrinology",
    "Gastroenterology",
    "Respiratory"
]
