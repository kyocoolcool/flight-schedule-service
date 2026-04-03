import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import flights
from app.services.oag_client import oag_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=settings.log_level.upper())
    logging.getLogger(__name__).info("Flight Schedule Service starting...")
    yield
    await oag_client.close()
    logging.getLogger(__name__).info("Flight Schedule Service stopped.")


app = FastAPI(
    title="Flight Schedule Service",
    description="台灣機場航班表服務 - 透過 OAG Flight Info API v2 收集台灣出入境航班資料",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(flights.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "flight-schedule-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)
