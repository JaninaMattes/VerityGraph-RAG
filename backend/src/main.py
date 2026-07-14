from functools import lru_cache
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI

from src import config

load_dotenv()
app = FastAPI()


@lru_cache
def get_settings():
    return config.Settings()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/info")
async def info(settings: Annotated[config.Settings, Depends(get_settings)]):
    return {
        "app_name": settings.app_name,
    }
