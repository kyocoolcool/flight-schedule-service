import logging
from datetime import date

import httpx

from app.config import TAIWAN_AIRPORTS, settings
from app.models.flight import (
    FlightCollectionResult,
    FlightCollectionSummary,
    FlightRecord,
    FlightStatusDetail,
    OagFlightResponse,
)

logger = logging.getLogger(__name__)

FLIGHT_INSTANCES_PATH = "/flight-instances/"


class OagClient:
    """OAG Flight Info API v2 客戶端"""

    def __init__(self) -> None:
        self.base_url = settings.oag_base_url.rstrip("/")
        self.api_key = settings.oag_api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Ocp-Apim-Subscription-Key": self.api_key},
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_flights(
        self,
        departure_airport: str | None = None,
        arrival_airport: str | None = None,
        departure_date: str | None = None,
        arrival_date: str | None = None,
        carrier: str | None = None,
        flight_number: str | None = None,
        flight_type: str = "scheduled",
        code_type: str = "IATA",
    ) -> OagFlightResponse:
        """查詢航班資訊

        Args:
            departure_airport: 出發機場代碼
            arrival_airport: 抵達機場代碼
            departure_date: 出發日期 (YYYY-MM-DD) 或日期範圍 (YYYY-MM-DD/YYYY-MM-DD)
            arrival_date: 抵達日期
            carrier: 航空公司代碼
            flight_number: 航班號碼
            flight_type: 航班類型 (scheduled, charter, etc.)
            code_type: 代碼類型 (IATA, ICAO, FAA)
        """
        params: dict[str, str] = {"version": "v2"}

        if departure_airport:
            params["DepartureAirport"] = departure_airport
        if arrival_airport:
            params["ArrivalAirport"] = arrival_airport
        if departure_date:
            params["DepartureDateTime"] = departure_date
        if arrival_date:
            params["ArrivalDateTime"] = arrival_date
        if carrier:
            params["Carrier"] = carrier
        if flight_number:
            params["FlightNumber"] = flight_number
        if flight_type:
            params["FlightType"] = flight_type
        if departure_airport or arrival_airport or carrier:
            params["CodeType"] = code_type

        all_flights: list[FlightStatusDetail] = []
        paging = None

        client = await self._get_client()
        url = FLIGHT_INSTANCES_PATH

        while True:
            logger.info("Requesting OAG API: %s params=%s", url, params)
            response = await client.get(url, params=params)
            response.raise_for_status()

            page_data = OagFlightResponse.model_validate(response.json())
            all_flights.extend(page_data.data)
            paging = page_data.paging

            if paging and paging.next:
                # 使用 next cursor URL 取得下一頁
                url = paging.next
                params = {}  # next URL 已包含所有參數
            else:
                break

        return OagFlightResponse(data=all_flights, paging=paging)

    async def get_taiwan_departures(
        self,
        airport_code: str,
        query_date: str,
    ) -> list[FlightRecord]:
        """取得指定台灣機場的出境航班"""
        response = await self.get_flights(
            departure_airport=airport_code,
            departure_date=query_date,
        )
        return [
            self._to_flight_record(flight, direction="departure", taiwan_airport=airport_code)
            for flight in response.data
        ]

    async def get_taiwan_arrivals(
        self,
        airport_code: str,
        query_date: str,
    ) -> list[FlightRecord]:
        """取得指定台灣機場的入境航班"""
        response = await self.get_flights(
            arrival_airport=airport_code,
            arrival_date=query_date,
        )
        return [
            self._to_flight_record(flight, direction="arrival", taiwan_airport=airport_code)
            for flight in response.data
        ]

    async def collect_all_taiwan_flights(
        self,
        query_date: str | None = None,
        airports: list[str] | None = None,
    ) -> FlightCollectionSummary:
        """收集所有台灣機場的出入境航班

        Args:
            query_date: 查詢日期 (YYYY-MM-DD)，預設為今天
            airports: 指定機場 IATA 代碼列表，預設為所有台灣機場
        """
        if query_date is None:
            query_date = date.today().isoformat()

        target_airports = airports or list(TAIWAN_AIRPORTS.keys())
        results: list[FlightCollectionResult] = []
        total_departures = 0
        total_arrivals = 0

        for airport_code in target_airports:
            airport_name = TAIWAN_AIRPORTS.get(airport_code, airport_code)

            # 出境航班
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
                logger.info("%s 出境航班: %d 筆", airport_code, len(departures))
            except httpx.HTTPStatusError as e:
                logger.error("查詢 %s 出境航班失敗: %s", airport_code, e)

            # 入境航班
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
                logger.info("%s 入境航班: %d 筆", airport_code, len(arrivals))
            except httpx.HTTPStatusError as e:
                logger.error("查詢 %s 入境航班失敗: %s", airport_code, e)

        return FlightCollectionSummary(
            total_airports_queried=len(target_airports),
            total_flights_collected=total_departures + total_arrivals,
            departures=total_departures,
            arrivals=total_arrivals,
            date=query_date,
            results=results,
        )

    @staticmethod
    def _to_flight_record(
        flight: FlightStatusDetail,
        direction: str,
        taiwan_airport: str,
    ) -> FlightRecord:
        """將 OAG API 回應轉換為統一格式的航班紀錄"""
        dep_iata = flight.departure_airport.iata if flight.departure_airport else None
        arr_iata = flight.arrival_airport.iata if flight.arrival_airport else None
        carrier_iata = flight.carrier.iata if flight.carrier else None
        carrier_icao = flight.carrier.icao if flight.carrier else None

        scheduled_departure = None
        if flight.scheduled_departure_date and flight.scheduled_departure_time:
            scheduled_departure = f"{flight.scheduled_departure_date}T{flight.scheduled_departure_time}"
        elif flight.scheduled_departure_date:
            scheduled_departure = flight.scheduled_departure_date

        scheduled_arrival = None
        if flight.scheduled_arrival_date and flight.scheduled_arrival_time:
            scheduled_arrival = f"{flight.scheduled_arrival_date}T{flight.scheduled_arrival_time}"
        elif flight.scheduled_arrival_date:
            scheduled_arrival = flight.scheduled_arrival_date

        actual_departure = None
        if flight.actual_departure_date and flight.actual_departure_time:
            actual_departure = f"{flight.actual_departure_date}T{flight.actual_departure_time}"

        actual_arrival = None
        if flight.actual_arrival_date and flight.actual_arrival_time:
            actual_arrival = f"{flight.actual_arrival_date}T{flight.actual_arrival_time}"

        return FlightRecord(
            carrier_iata=carrier_iata,
            carrier_icao=carrier_icao,
            flight_number=flight.flight_number,
            departure_airport_iata=dep_iata,
            arrival_airport_iata=arr_iata,
            scheduled_departure=scheduled_departure,
            scheduled_arrival=scheduled_arrival,
            actual_departure=actual_departure,
            actual_arrival=actual_arrival,
            status=flight.status,
            flight_type=flight.flight_type,
            service_type=flight.service_type,
            aircraft_type=flight.aircraft_type,
            direction=direction,
            taiwan_airport=taiwan_airport,
        )


# Singleton instance
oag_client = OagClient()
