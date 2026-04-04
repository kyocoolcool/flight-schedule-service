import asyncio
import logging
from datetime import date, datetime

from app.config import TAIWAN_AIRPORTS
from app.models.flight import FlightCollectionResult

logger = logging.getLogger(__name__)

# 主要機場（排程抓取用）- 國際航班較多的機場
SCHEDULED_AIRPORTS = ["TPE", "TSA", "KHH", "RMQ", "TNN"]

# 快取：key = "airport_code:direction:date", value = FlightCollectionResult
_cache: dict[str, FlightCollectionResult] = {}
_last_update: datetime | None = None


def cache_key(airport_code: str, direction: str, query_date: str) -> str:
    return f"{airport_code}:{direction}:{query_date}"


def get_cached(airport_code: str, direction: str, query_date: str) -> FlightCollectionResult | None:
    """從快取取得航班資料，沒有則回傳 None"""
    key = cache_key(airport_code, direction, query_date)
    return _cache.get(key)


def set_cached(airport_code: str, direction: str, query_date: str, result: FlightCollectionResult) -> None:
    """寫入快取"""
    key = cache_key(airport_code, direction, query_date)
    _cache[key] = result


def get_last_update() -> datetime | None:
    return _last_update


def get_cache_stats() -> dict:
    return {
        "cached_entries": len(_cache),
        "last_update": _last_update.isoformat() if _last_update else None,
        "cached_keys": list(_cache.keys()),
    }


async def refresh_cache() -> dict:
    """抓取主要機場的即時航班資料並寫入快取"""
    from app.services.aviation_edge_client import aviation_edge_client

    global _last_update

    today = date.today().isoformat()
    total_flights = 0
    errors = 0

    for airport_code in SCHEDULED_AIRPORTS:
        airport_name = TAIWAN_AIRPORTS.get(airport_code, airport_code)

        for direction in ("departure", "arrival"):
            try:
                if direction == "departure":
                    flights = await aviation_edge_client.get_taiwan_departures(airport_code, today)
                else:
                    flights = await aviation_edge_client.get_taiwan_arrivals(airport_code, today)

                result = FlightCollectionResult(
                    airport=airport_code,
                    airport_name=airport_name,
                    direction=direction,
                    date=today,
                    total_flights=len(flights),
                    flights=flights,
                )
                set_cached(airport_code, direction, today, result)
                total_flights += len(flights)
                logger.info(
                    "快取更新: %s %s %d 筆航班",
                    airport_code,
                    direction,
                    len(flights),
                )
            except Exception as e:
                errors += 1
                logger.error("快取更新失敗: %s %s - %s", airport_code, direction, e)

    _last_update = datetime.now()
    logger.info(
        "快取更新完成: %d 筆航班, %d 個錯誤, %d 個快取項目",
        total_flights,
        errors,
        len(_cache),
    )

    return {
        "total_flights": total_flights,
        "errors": errors,
        "cached_entries": len(_cache),
        "updated_at": _last_update.isoformat(),
    }


class FlightScheduler:
    """定時排程器，每 30 分鐘抓取航班資料"""

    def __init__(self, interval_minutes: int = 30) -> None:
        self.interval = interval_minutes * 60
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """啟動排程"""
        logger.info("航班排程器啟動，每 %d 分鐘更新一次", self.interval // 60)
        # 啟動時立即抓一次
        await refresh_cache()
        # 開始定時任務
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval)
            try:
                await refresh_cache()
            except Exception as e:
                logger.error("排程更新失敗: %s", e)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("航班排程器已停止")


# Singleton
flight_scheduler = FlightScheduler(interval_minutes=30)
