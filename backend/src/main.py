from dotenv import load_dotenv
from fastapi import FastAPI

from src.api.routers import documents, health
from src.dependencies import get_settings
from src.utils.logger import get_logger, setup_logging

# Initialization before FastAPI constructed
setup_logging(log_level="INFO")
logger = get_logger("api-backend.main")

load_dotenv()
settings = get_settings()
app = FastAPI(title=settings.app_name)


app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])
app.include_router(documents.router, prefix=settings.api_prefix, tags=["upload"])