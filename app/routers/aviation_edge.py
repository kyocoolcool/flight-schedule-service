from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.config import TAIWAN_AIRPORTS
from app.models.flight import FlightCollectionResult, FlightCollectionSummary
from app.services.aviation_edge_client import aviation_edge_client

router = APIRouter(prefix="/api/aviation-edge", tags=["aviation-edge"])


@router.get("/taiwan/all", response_model=FlightCollectionSummary)
async def collect_all_taiwan_flights(
    query_date: str | None = Query(None, description="查詢日期 (YYYY-MM-DD)，預設為今天"),
    airports: str | None = Query(None, description="指定機場 IATA 代碼，以逗號分隔 (例: TPE,KHH)"),
):
    """透過 Aviation Edge API 收集所有台灣機場的出入境航班資料"""
    airport_list = None
    if airports:
        airport_list = [a.strip().upper() for a in airports.split(",")]
        invalid = [a for a in airport_list if a not in TAIWAN_AIRPORTS]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"無效的機場代碼: {', '.join(invalid)}。有效代碼: {', '.join(TAIWAN_AIRPORTS.keys())}",
            )

    return await aviation_edge_client.collect_all_taiwan_flights(
        query_date=query_date,
        airports=airport_list,
    )


@router.get("/taiwan/{airport_code}/departures", response_model=FlightCollectionResult)
async def get_airport_departures(
    airport_code: str,
    query_date: str | None = Query(None, description="查詢日期 (YYYY-MM-DD)"),
):
    """透過 Aviation Edge API 查詢指定台灣機場的出境航班"""
    airport_code = airport_code.upper()
    if airport_code not in TAIWAN_AIRPORTS:
        raise HTTPException(
            status_code=400,
            detail=f"無效的機場代碼: {airport_code}。有效代碼: {', '.join(TAIWAN_AIRPORTS.keys())}",
        )

    if query_date is None:
        query_date = date.today().isoformat()

    flights = await aviation_edge_client.get_taiwan_departures(airport_code, query_date)
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
    query_date: str | None = Query(None, description="查詢日期 (YYYY-MM-DD)"),
):
    """透過 Aviation Edge API 查詢指定台灣機場的入境航班"""
    airport_code = airport_code.upper()
    if airport_code not in TAIWAN_AIRPORTS:
        raise HTTPException(
            status_code=400,
            detail=f"無效的機場代碼: {airport_code}。有效代碼: {', '.join(TAIWAN_AIRPORTS.keys())}",
        )

    if query_date is None:
        query_date = date.today().isoformat()

    flights = await aviation_edge_client.get_taiwan_arrivals(airport_code, query_date)
    return FlightCollectionResult(
        airport=airport_code,
        airport_name=TAIWAN_AIRPORTS[airport_code],
        direction="arrival",
        date=query_date,
        total_flights=len(flights),
        flights=flights,
    )


@router.get("/timetable", response_model=list)
async def search_timetable(
    iata_code: str = Query(..., description="機場 IATA 代碼"),
    schedule_type: str = Query(..., description="查詢類型: departure 或 arrival"),
    airline_iata: str | None = Query(None, description="航空公司 IATA 代碼（篩選用）"),
    flight_num: str | None = Query(None, description="航班號碼（篩選用）"),
    status: str | None = Query(None, description="航班狀態 (landed, scheduled, cancelled, active, etc.)"),
):
    """直接查詢 Aviation Edge 即時時刻表"""
    if schedule_type not in ("departure", "arrival"):
        raise HTTPException(status_code=400, detail="schedule_type 必須是 'departure' 或 'arrival'")

    flights = await aviation_edge_client.get_timetable(
        iata_code=iata_code,
        schedule_type=schedule_type,
        airline_iata=airline_iata,
        flight_num=flight_num,
        status=status,
    )
    return [f.model_dump(by_alias=True) for f in flights]
