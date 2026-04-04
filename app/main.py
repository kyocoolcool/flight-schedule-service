import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.routers import aviation_edge, flights, scraper
from app.services.aviation_edge_client import aviation_edge_client
from app.services.flight_cache import flight_scheduler
from app.services.oag_client import oag_client
from app.services.taoyuan_scraper import taoyuan_scraper


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=settings.log_level.upper())
    logging.getLogger(__name__).info("Flight Schedule Service starting...")
    await flight_scheduler.start()
    yield
    await flight_scheduler.stop()
    await oag_client.close()
    await aviation_edge_client.close()
    await taoyuan_scraper.close()
    logging.getLogger(__name__).info("Flight Schedule Service stopped.")


app = FastAPI(
    title="Flight Schedule Service",
    description="台灣機場航班表服務 - 支援 OAG API、Aviation Edge API 與桃園機場官網爬蟲三種資料來源",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(flights.router)
app.include_router(aviation_edge.router)
app.include_router(scraper.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "flight-schedule-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)
