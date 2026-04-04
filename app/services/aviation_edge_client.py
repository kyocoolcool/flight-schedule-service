import logging
from datetime import date

import httpx

from app.config import TAIWAN_AIRPORTS, settings
from app.models.aviation_edge import (
    AviationEdgeFlight,
    AviationEdgeFutureFlight,
)
from app.models.flight import (
    FlightCollectionResult,
    FlightCollectionSummary,
    FlightRecord,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://aviation-edge.com/v2/public"


class AviationEdgeClient:
    """Aviation Edge API 客戶端

    支援即時航班時刻表、未來航班查詢。
    API 文件: https://aviation-edge.com/developers/
    """

    def __init__(self) -> None:
        self.api_key = settings.aviation_edge_api_key
        self.base_url = settings.aviation_edge_base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_timetable(
        self,
        iata_code: str,
        schedule_type: str,
        airline_iata: str | None = None,
        flight_num: str | None = None,
        status: str | None = None,
    ) -> list[AviationEdgeFlight]:
        """查詢即時機場航班時刻表

        Args:
            iata_code: 機場 IATA 代碼
            schedule_type: "departure" 或 "arrival"
            airline_iata: 航空公司 IATA 代碼（篩選用）
            flight_num: 航班號碼（篩選用）
            status: 航班狀態 (landed, scheduled, cancelled, active, etc.)
        """
        params: dict[str, str] = {
            "key": self.api_key,
            "iataCode": iata_code,
            "type": schedule_type,
        }
        if airline_iata:
            params["airline_iata"] = airline_iata
        if flight_num:
            params["flight_num"] = flight_num
        if status:
            params["status"] = status

        client = await self._get_client()
        url = f"{self.base_url}/timetable"
        safe_params = {k: v for k, v in params.items() if k != "key"}
        logger.info("Requesting Aviation Edge timetable: %s params=%s", url, safe_params)
        response = await client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        if isinstance(data, dict) and "error" in data:
            logger.error("Aviation Edge API error: %s", data)
            return []

        return [AviationEdgeFlight.model_validate(item) for item in data]

    async def get_future_flights(
        self,
        iata_code: str,
        schedule_type: str,
        query_date: str,
    ) -> list[AviationEdgeFutureFlight]:
        """查詢未來航班時刻表

        Args:
            iata_code: 機場 IATA 代碼
            schedule_type: "departure" 或 "arrival"
            query_date: 查詢日期 (YYYY-MM-DD)
        """
        params: dict[str, str] = {
            "key": self.api_key,
            "iataCode": iata_code,
            "type": schedule_type,
            "date": query_date,
        }

        client = await self._get_client()
        url = f"{self.base_url}/flightsFuture"
        safe_params = {k: v for k, v in params.items() if k != "key"}
        logger.info("Requesting Aviation Edge future flights: %s params=%s", url, safe_params)
        response = await client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        if isinstance(data, dict) and "error" in data:
            logger.error("Aviation Edge API error: %s", data)
            return []

        return [AviationEdgeFutureFlight.model_validate(item) for item in data]

    async def get_taiwan_departures(
        self,
        airport_code: str,
        query_date: str | None = None,
    ) -> list[FlightRecord]:
        """取得指定台灣機場的出境航班"""
        if query_date and query_date > date.today().isoformat():
            flights = await self.get_future_flights(airport_code, "departure", query_date)
            return [self._future_to_flight_record(f, "departure", airport_code) for f in flights]
        else:
            flights = await self.get_timetable(airport_code, "departure")
            return [self._timetable_to_flight_record(f, "departure", airport_code) for f in flights]

    async def get_taiwan_arrivals(
        self,
        airport_code: str,
        query_date: str | None = None,
    ) -> list[FlightRecord]:
        """取得指定台灣機場的入境航班"""
        if query_date and query_date > date.today().isoformat():
            flights = await self.get_future_flights(airport_code, "arrival", query_date)
            return [self._future_to_flight_record(f, "arrival", airport_code) for f in flights]
        else:
            flights = await self.get_timetable(airport_code, "arrival")
            return [self._timetable_to_flight_record(f, "arrival", airport_code) for f in flights]

    async def collect_all_taiwan_flights(
        self,
        query_date: str | None = None,
        airports: list[str] | None = None,
    ) -> FlightCollectionSummary:
        """收集所有台灣機場的出入境航班"""
        if query_date is None:
            query_date = date.today().isoformat()

        target_airports = airports or list(TAIWAN_AIRPORTS.keys())
        results: list[FlightCollectionResult] = []
        total_departures = 0
        total_arrivals = 0

        for airport_code in target_airports:
            airport_name = TAIWAN_AIRPORTS.get(airport_code, airport_code)

            try:
                departures = await self.get_taiwan_departures(airport_code, query_date)
                total_departures += len(departures)
                results.append(
                    FlightCollectionResult(
                        airport=airport_code,
                        airport_name=airport_name,
                        direction="departure",
                        date=query_date,
                        total_flights=len(departures),
                        flights=departures,
                    )
                )
                logger.info("%s 出境航班 (Aviation Edge): %d 筆", airport_code, len(departures))
            except httpx.HTTPStatusError as e:
                logger.error("查詢 %s 出境航班失敗 (Aviation Edge): %s", airport_code, e)

            try:
                arrivals = await self.get_taiwan_arrivals(airport_code, query_date)
                total_arrivals += len(arrivals)
                results.append(
                    FlightCollectionResult(
                        airport=airport_code,
                        airport_name=airport_name,
                        direction="arrival",
                        date=query_date,
                        total_flights=len(arrivals),
                        flights=arrivals,
                    )
                )
                logger.info("%s 入境航班 (Aviation Edge): %d 筆", airport_code, len(arrivals))
            except httpx.HTTPStatusError as e:
                logger.error("查詢 %s 入境航班失敗 (Aviation Edge): %s", airport_code, e)

        return FlightCollectionSummary(
            total_airports_queried=len(target_airports),
            total_flights_collected=total_departures + total_arrivals,
            departures=total_departures,
            arrivals=total_arrivals,
            date=query_date,
            results=results,
        )

    @staticmethod
    def _timetable_to_flight_record(
        flight: AviationEdgeFlight,
        direction: str,
        taiwan_airport: str,
    ) -> FlightRecord:
        """將 Aviation Edge timetable API 回應轉換為統一格式"""
        return FlightRecord(
            carrier_iata=flight.airline.iata_code if flight.airline else None,
            carrier_icao=flight.airline.icao_code if flight.airline else None,
            carrier_name=flight.airline.name if flight.airline else None,
            flight_number=flight.flight.number if flight.flight else None,
            departure_airport_iata=flight.departure.iata_code if flight.departure else None,
            arrival_airport_iata=flight.arrival.iata_code if flight.arrival else None,
            scheduled_departure=flight.departure.scheduled_time if flight.departure else None,
            scheduled_arrival=flight.arrival.scheduled_time if flight.arrival else None,
            actual_departure=flight.departure.actual_time if flight.departure else None,
            actual_arrival=flight.arrival.actual_time if flight.arrival else None,
            status=flight.status,
            direction=direction,
            taiwan_airport=taiwan_airport,
        )

    @staticmethod
    def _future_to_flight_record(
        flight: AviationEdgeFutureFlight,
        direction: str,
        taiwan_airport: str,
    ) -> FlightRecord:
        """將 Aviation Edge future flights API 回應轉換為統一格式"""
        dep_iata = flight.departure.iata_code if flight.departure else None
        arr_iata = flight.arrival.iata_code if flight.arrival else None

        scheduled_departure = None
        if flight.departure and flight.departure.scheduled_time:
            scheduled_departure = flight.departure.scheduled_time

        scheduled_arrival = None
        if flight.arrival and flight.arrival.scheduled_time:
            scheduled_arrival = flight.arrival.scheduled_time

        return FlightRecord(
            carrier_iata=flight.airline.iata_code if flight.airline else None,
            carrier_icao=flight.airline.icao_code if flight.airline else None,
            carrier_name=flight.airline.name if flight.airline else None,
            flight_number=flight.flight.number if flight.flight else None,
            departure_airport_iata=dep_iata,
            arrival_airport_iata=arr_iata,
            scheduled_departure=scheduled_departure,
            scheduled_arrival=scheduled_arrival,
            status="scheduled",
            aircraft_type=flight.aircraft.iata_code if flight.aircraft else None,
            direction=direction,
            taiwan_airport=taiwan_airport,
        )


# Singleton instance
aviation_edge_client = AviationEdgeClient()
