from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.config import TAIWAN_AIRPORTS
from app.models.flight import FlightCollectionResult, FlightCollectionSummary, FlightRecord, OagFlightResponse
from app.services.oag_client import oag_client

router = APIRouter(prefix="/api/flights", tags=["flights"])


@router.get("/taiwan/all", response_model=FlightCollectionSummary)
async def collect_all_taiwan_flights(
    query_date: str | None = Query(None, description="查詢日期 (YYYY-MM-DD)，預設為今天", examples=["2026-04-03"]),
    airports: str | None = Query(None, description="指定機場 IATA 代碼，以逗號分隔 (例: TPE,KHH)"),
):
    """收集所有台灣機場的出入境航班資料

    此 API 會查詢所有（或指定的）台灣機場的出境與入境航班，
    適用於資料收集與比較分析。
    """
    airport_list = None
    if airports:
        airport_list = [a.strip().upper() for a in airports.split(",")]
        invalid = [a for a in airport_list if a not in TAIWAN_AIRPORTS]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"無效的機場代碼: {', '.join(invalid)}。有效代碼: {', '.join(TAIWAN_AIRPORTS.keys())}",
            )

    return await oag_client.collect_all_taiwan_flights(
        query_date=query_date,
        airports=airport_list,
    )


@router.get("/taiwan/{airport_code}/departures", response_model=FlightCollectionResult)
async def get_airport_departures(
    airport_code: str,
    query_date: str | None = Query(None, description="查詢日期 (YYYY-MM-DD)", examples=["2026-04-03"]),
):
    """查詢指定台灣機場的出境航班"""
    airport_code = airport_code.upper()
    if airport_code not in TAIWAN_AIRPORTS:
        raise HTTPException(
            status_code=400,
            detail=f"無效的機場代碼: {airport_code}。有效代碼: {', '.join(TAIWAN_AIRPORTS.keys())}",
        )

    if query_date is None:
        query_date = date.today().isoformat()

    flights = await oag_client.get_taiwan_departures(airport_code, query_date)
    return FlightCollectionResult(
        airport=airport_code,
        airport_name=TAIWAN_AIRPORTS[airport_code],
        direction="departure",
        date=query_date,
        total_flights=len(flights),
        flights=flights,
    )


@router.get("/taiwan/{airport_code}/arrivals", response_model=FlightCollectionResult)
async def get_airport_arrivals(
    airport_code: str,
    query_date: str | None = Query(None, description="查詢日期 (YYYY-MM-DD)", examples=["2026-04-03"]),
):
    """查詢指定台灣機場的入境航班"""
    airport_code = airport_code.upper()
    if airport_code not in TAIWAN_AIRPORTS:
        raise HTTPException(
            status_code=400,
            detail=f"無效的機場代碼: {airport_code}。有效代碼: {', '.join(TAIWAN_AIRPORTS.keys())}",
        )

    if query_date is None:
        query_date = date.today().isoformat()

    flights = await oag_client.get_taiwan_arrivals(airport_code, query_date)
    return FlightCollectionResult(
        airport=airport_code,
        airport_name=TAIWAN_AIRPORTS[airport_code],
        direction="arrival",
        date=query_date,
        total_flights=len(flights),
        flights=flights,
    )


@router.get("/search", response_model=OagFlightResponse)
async def search_flights(
    departure_airport: str | None = Query(None, description="出發機場 IATA 代碼"),
    arrival_airport: str | None = Query(None, description="抵達機場 IATA 代碼"),
    departure_date: str | None = Query(None, description="出發日期 (YYYY-MM-DD 或 YYYY-MM-DD/YYYY-MM-DD)"),
    arrival_date: str | None = Query(None, description="抵達日期"),
    carrier: str | None = Query(None, description="航空公司 IATA 代碼"),
    flight_number: str | None = Query(None, description="航班號碼"),
    flight_type: str = Query("scheduled", description="航班類型"),
):
    """通用航班搜尋 - 直接查詢 OAG API"""
    if not any([departure_airport, arrival_airport, carrier, flight_number]):
        raise HTTPException(
            status_code=400,
            detail="至少需要提供一個查詢條件: departure_airport, arrival_airport, carrier, 或 flight_number",
        )

    return await oag_client.get_flights(
        departure_airport=departure_airport,
        arrival_airport=arrival_airport,
        departure_date=departure_date,
        arrival_date=arrival_date,
        carrier=carrier,
        flight_number=flight_number,
        flight_type=flight_type,
    )


@router.get("/airports", response_model=dict[str, str])
async def list_taiwan_airports():
    """列出所有台灣機場"""
    return TAIWAN_AIRPORTS
