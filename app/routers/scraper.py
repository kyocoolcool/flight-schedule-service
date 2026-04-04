from datetime import datetime

from fastapi import APIRouter, Query

from app.models.flight import FlightCollectionResult, FlightRecord
from app.services.taoyuan_scraper import taoyuan_scraper

router = APIRouter(prefix="/api/scraper", tags=["scraper"])


@router.get("/taoyuan/departures", response_model=FlightCollectionResult)
async def scrape_taoyuan_departures(
    lang: str = Query("en", description="語言 (en/zh-tw)"),
):
    """爬取桃園機場出境航班 (from taoyuan-airport.com)"""
    flights = await taoyuan_scraper.get_departures(lang=lang)
    return FlightCollectionResult(
        airport="TPE",
        airport_name="桃園國際機場",
        direction="departure",
        date=datetime.now().strftime("%Y-%m-%d"),
        total_flights=len(flights),
        flights=flights,
    )


@router.get("/taoyuan/arrivals", response_model=FlightCollectionResult)
async def scrape_taoyuan_arrivals(
    lang: str = Query("en", description="語言 (en/zh-tw)"),
):
    """爬取桃園機場入境航班 (from taoyuan-airport.com)"""
    flights = await taoyuan_scraper.get_arrivals(lang=lang)
    return FlightCollectionResult(
        airport="TPE",
        airport_name="桃園國際機場",
        direction="arrival",
        date=datetime.now().strftime("%Y-%m-%d"),
        total_flights=len(flights),
        flights=flights,
    )


@router.get("/taoyuan/all", response_model=FlightCollectionResult)
async def scrape_taoyuan_all(
    lang: str = Query("en", description="語言 (en/zh-tw)"),
):
    """爬取桃園機場所有出入境航班 (from taoyuan-airport.com)"""
    flights = await taoyuan_scraper.get_all_flights(lang=lang)
    departures = [f for f in flights if f.direction == "departure"]
    arrivals = [f for f in flights if f.direction == "arrival"]
    return FlightCollectionResult(
        airport="TPE",
        airport_name="桃園國際機場",
        direction="all",
        date=datetime.now().strftime("%Y-%m-%d"),
        total_flights=len(flights),
        flights=flights,
    )
