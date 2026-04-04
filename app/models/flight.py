from datetime import datetime

from pydantic import BaseModel, Field


class AirportInfo(BaseModel):
    """機場資訊"""

    iata: str | None = None
    icao: str | None = None
    terminal: str | None = None
    gate: str | None = None


class CarrierInfo(BaseModel):
    """航空公司資訊"""

    iata: str | None = None
    icao: str | None = None


class FlightDuration(BaseModel):
    """航班時間資訊"""

    scheduled_block_minutes: int | None = Field(None, alias="scheduledBlockMinutes")


class FlightStatusDetail(BaseModel):
    """航班狀態"""

    departure_airport: AirportInfo | None = Field(None, alias="departureAirport")
    arrival_airport: AirportInfo | None = Field(None, alias="arrivalAirport")
    carrier: CarrierInfo | None = None
    flight_number: str | None = Field(None, alias="flightNumber")
    suffix: str | None = None
    service_type: str | None = Field(None, alias="serviceType")
    flight_type: str | None = Field(None, alias="flightType")
    scheduled_departure_date: str | None = Field(None, alias="scheduledDepartureDate")
    scheduled_departure_time: str | None = Field(None, alias="scheduledDepartureTime")
    scheduled_departure_utc: str | None = Field(None, alias="scheduledDepartureUTC")
    scheduled_arrival_date: str | None = Field(None, alias="scheduledArrivalDate")
    scheduled_arrival_time: str | None = Field(None, alias="scheduledArrivalTime")
    scheduled_arrival_utc: str | None = Field(None, alias="scheduledArrivalUTC")
    actual_departure_date: str | None = Field(None, alias="actualDepartureDate")
    actual_departure_time: str | None = Field(None, alias="actualDepartureTime")
    actual_arrival_date: str | None = Field(None, alias="actualArrivalDate")
    actual_arrival_time: str | None = Field(None, alias="actualArrivalTime")
    status: str | None = None
    aircraft_type: str | None = Field(None, alias="aircraftType")
    duration: FlightDuration | None = None

    model_config = {"populate_by_name": True}


class PagingInfo(BaseModel):
    """分頁資訊"""

    limit: int | None = None
    total_count: int | None = Field(None, alias="totalCount")
    total_pages: int | None = Field(None, alias="totalPages")
    next: str | None = None


class OagFlightResponse(BaseModel):
    """OAG API 回應"""

    data: list[FlightStatusDetail] = []
    paging: PagingInfo | None = None


class FlightRecord(BaseModel):
    """整理過的航班紀錄，用於存儲與比較"""

    carrier_iata: str | None = None
    carrier_icao: str | None = None
    carrier_name: str | None = None
    flight_number: str | None = None
    departure_airport_iata: str | None = None
    arrival_airport_iata: str | None = None
    scheduled_departure: str | None = None
    scheduled_arrival: str | None = None
    actual_departure: str | None = None
    actual_arrival: str | None = None
    status: str | None = None
    flight_type: str | None = None
    service_type: str | None = None
    aircraft_type: str | None = None
    direction: str | None = None  # "departure" 出境 or "arrival" 入境
    taiwan_airport: str | None = None  # 台灣的機場 IATA 代碼
    collected_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def flight_id(self) -> str:
        """航班唯一識別碼"""
        return f"{self.carrier_iata or ''}{self.flight_number or ''}-{self.scheduled_departure or ''}"


class FlightCollectionResult(BaseModel):
    """航班資料收集結果"""

    airport: str
    airport_name: str
    direction: str
    date: str
    total_flights: int
    flights: list[FlightRecord]
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class FlightCollectionSummary(BaseModel):
    """航班收集摘要"""

    total_airports_queried: int
    total_flights_collected: int
    departures: int
    arrivals: int
    date: str
    results: list[FlightCollectionResult]
    collected_at: datetime = Field(default_factory=datetime.utcnow)
