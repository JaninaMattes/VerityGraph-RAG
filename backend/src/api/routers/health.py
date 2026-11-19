"""Info, liveness and readiness endpoints.

- /health/live: the process runs (restart the container if this fails).
- /health/ready: the database and the object storage answer (send no traffic if not).
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from src.api.dependencies import ReadinessProbe, get_readiness_probes, get_settings
from src.libs.core.config import Settings
from src.libs.core.logger import get_logger
from src.libs.schemas.health import (
    AppHealthResponse,
    LivenessResponse,
    ReadinessResponse,
)

logger = get_logger(__name__)

SettingsDep = Annotated[Settings, Depends(get_settings)]
ProbesDep = Annotated[dict[str, ReadinessProbe], Depends(get_readiness_probes)]

# A probe that is slower than this counts as failed, so the endpoint stays fast.
PROBE_TIMEOUT_SECONDS = 2.0

router = APIRouter()


@router.get("/info", status_code=status.HTTP_200_OK)
async def info(settings: SettingsDep) -> AppHealthResponse:
    """Return the configured application name."""
    return AppHealthResponse(app_name=settings.app_name)


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def live() -> LivenessResponse:
    """Return 200 while the process can serve requests. It checks no dependency."""
    return LivenessResponse()


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def ready(probes: ProbesDep, response: Response) -> ReadinessResponse:
    """Run every readiness probe. Return 200 if all pass, otherwise 503.

    The body names each probe with 'ok' or 'failed'. Failures are logged as warnings.
    """
    results = await asyncio.gather(
        *(_passes(name, probe) for name, probe in probes.items())
    )
    checks = {
        name: "ok" if passed else "failed"
        for name, passed in zip(probes, results, strict=True)
    }
    if all(results):
        return ReadinessResponse(status="ready", checks=checks)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="not_ready", checks=checks)


async def _passes(name: str, probe: ReadinessProbe) -> bool:
    """Return True if `probe` finishes without an error within the timeout."""
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
            await probe()
    except Exception as exc:  # noqa: BLE001 - any failure means "not ready"; logged
        logger.warning("readiness probe failed", probe=name, error=repr(exc))
        return False
    return True
