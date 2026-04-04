from pydantic import BaseModel, Field


class AEAirlineInfo(BaseModel):
    """Aviation Edge 航空公司資訊"""

    iata_code: str | None = Field(None, alias="iataCode")
    icao_code: str | None = Field(None, alias="icaoCode")
    name: str | None = None

    model_config = {"populate_by_name": True}


class AEAirportDetail(BaseModel):
    """Aviation Edge 機場詳細資訊（時刻表回應用）"""

    iata_code: str | None = Field(None, alias="iataCode")
    icao_code: str | None = Field(None, alias="icaoCode")
    terminal: str | None = None
    gate: str | None = None
    baggage: str | None = None
    delay: str | None = None
    scheduled_time: str | None = Field(None, alias="scheduledTime")
    estimated_time: str | None = Field(None, alias="estimatedTime")
    actual_time: str | None = Field(None, alias="actualTime")
    estimated_runway: str | None = Field(None, alias="estimatedRunway")
    actual_runway: str | None = Field(None, alias="actualRunway")

    model_config = {"populate_by_name": True}


class AEFlightInfo(BaseModel):
    """Aviation Edge 航班資訊"""

    number: str | None = None
    iata_number: str | None = Field(None, alias="iataNumber")
    icao_number: str | None = Field(None, alias="icaoNumber")

    model_config = {"populate_by_name": True}


class AECodeshared(BaseModel):
    """Aviation Edge 共享航班資訊"""

    airline: AEAirlineInfo | None = None
    flight: AEFlightInfo | None = None

    model_config = {"populate_by_name": True}


class AviationEdgeFlight(BaseModel):
    """Aviation Edge 即時時刻表航班"""

    type: str | None = None
    status: str | None = None
    departure: AEAirportDetail | None = None
    arrival: AEAirportDetail | None = None
    airline: AEAirlineInfo | None = None
    flight: AEFlightInfo | None = None
    codeshared: AECodeshared | None = None

    model_config = {"populate_by_name": True}


class AEFutureAirportDetail(BaseModel):
    """Aviation Edge 未來航班機場資訊"""

    iata_code: str | None = Field(None, alias="iataCode")
    icao_code: str | None = Field(None, alias="icaoCode")
    terminal: str | None = None
    gate: str | None = None
    scheduled_time: str | None = Field(None, alias="scheduledTime")

    model_config = {"populate_by_name": True}


class AEAircraftInfo(BaseModel):
    """Aviation Edge 機型資訊"""

    model_code: str | None = Field(None, alias="modelCode")
    model_text: str | None = Field(None, alias="modelText")
    iata_code: str | None = Field(None, alias="iataCode")

    model_config = {"populate_by_name": True}


class AviationEdgeFutureFlight(BaseModel):
    """Aviation Edge 未來航班"""

    type: str | None = None
    departure: AEFutureAirportDetail | None = None
    arrival: AEFutureAirportDetail | None = None
    airline: AEAirlineInfo | None = None
    flight: AEFlightInfo | None = None
    codeshared: AECodeshared | None = None
    aircraft: AEAircraftInfo | None = None

    model_config = {"populate_by_name": True}
