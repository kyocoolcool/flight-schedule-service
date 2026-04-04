"""Aviation Edge API 整合測試

測試項目：
1. 模型驗證 - 確認 Pydantic 模型能正確解析 API 回應格式
2. 客戶端邏輯 - 確認 FlightRecord 轉換正確
3. API 連線測試 - 實際呼叫 Aviation Edge API（需要有效 API key）
"""

import asyncio
import json
import os

import pytest

from app.models.aviation_edge import (
    AEAircraftInfo,
    AEAirlineInfo,
    AEAirportDetail,
    AEFlightInfo,
    AEFutureAirportDetail,
    AviationEdgeFlight,
    AviationEdgeFutureFlight,
)
from app.services.aviation_edge_client import AviationEdgeClient


# ============================================================
# 1. 模型解析測試 - 使用 Aviation Edge 官方文件的範例格式
# ============================================================

SAMPLE_TIMETABLE_RESPONSE = {
    "airline": {"iataCode": "UA", "icaoCode": "UAL", "name": "United Airlines"},
    "arrival": {
        "actualRunway": None,
        "actualTime": None,
        "baggage": "7",
        "delay": None,
        "estimatedRunway": None,
        "estimatedTime": "2026-04-04T10:02:00.000",
        "gate": "107",
        "iataCode": "EWR",
        "icaoCode": "KEWR",
        "scheduledTime": "2026-04-04T10:21:00.000",
        "terminal": "C",
    },
    "departure": {
        "actualRunway": "2026-04-04T06:12:00.000",
        "actualTime": "2026-04-04T06:12:00.000",
        "baggage": None,
        "delay": "13",
        "estimatedRunway": "2026-04-04T06:12:00.000",
        "estimatedTime": "2026-04-04T06:10:00.000",
        "gate": "34",
        "iataCode": "IAH",
        "icaoCode": "KIAH",
        "scheduledTime": "2026-04-04T06:00:00.000",
        "terminal": "C",
    },
    "flight": {"iataNumber": "UA1268", "icaoNumber": "UAL1268", "number": "1268"},
    "status": "active",
    "type": "departure",
    "codeshared": None,
}

SAMPLE_FUTURE_RESPONSE = {
    "weekday": "5",
    "departure": {
        "iataCode": "TPE",
        "icaoCode": "RCTP",
        "terminal": "2",
        "gate": None,
        "scheduledTime": "08:30",
    },
    "arrival": {
        "iataCode": "NRT",
        "icaoCode": "RJAA",
        "terminal": "1",
        "gate": None,
        "scheduledTime": "12:40",
    },
    "airline": {"iataCode": "BR", "icaoCode": "EVA", "name": "EVA Air"},
    "flight": {"iataNumber": "BR198", "icaoNumber": "EVA198", "number": "198"},
    "codeshared": None,
    "aircraft": {"modelCode": "77W", "modelText": "Boeing 777-300ER", "iataCode": "77W"},
    "type": "departure",
}


class TestModelParsing:
    """測試 Pydantic 模型是否能正確解析 Aviation Edge 回應"""

    def test_parse_timetable_flight(self):
        flight = AviationEdgeFlight.model_validate(SAMPLE_TIMETABLE_RESPONSE)

        assert flight.status == "active"
        assert flight.type == "departure"
        assert flight.airline.iata_code == "UA"
        assert flight.airline.icao_code == "UAL"
        assert flight.airline.name == "United Airlines"
        assert flight.departure.iata_code == "IAH"
        assert flight.departure.gate == "34"
        assert flight.departure.terminal == "C"
        assert flight.departure.delay == "13"
        assert flight.departure.actual_time == "2026-04-04T06:12:00.000"
        assert flight.departure.scheduled_time == "2026-04-04T06:00:00.000"
        assert flight.arrival.iata_code == "EWR"
        assert flight.arrival.baggage == "7"
        assert flight.arrival.scheduled_time == "2026-04-04T10:21:00.000"
        assert flight.flight.number == "1268"
        assert flight.flight.iata_number == "UA1268"
        assert flight.codeshared is None
        print("  ✓ 即時時刻表模型解析正確")

    def test_parse_future_flight(self):
        flight = AviationEdgeFutureFlight.model_validate(SAMPLE_FUTURE_RESPONSE)

        assert flight.type == "departure"
        assert flight.airline.iata_code == "BR"
        assert flight.airline.name == "EVA Air"
        assert flight.departure.iata_code == "TPE"
        assert flight.departure.terminal == "2"
        assert flight.departure.scheduled_time == "08:30"
        assert flight.arrival.iata_code == "NRT"
        assert flight.arrival.scheduled_time == "12:40"
        assert flight.flight.number == "198"
        assert flight.aircraft.iata_code == "77W"
        assert flight.aircraft.model_text == "Boeing 777-300ER"
        print("  ✓ 未來航班模型解析正確")

    def test_parse_minimal_flight(self):
        """測試最小欄位的航班（某些欄位可能為 null）"""
        minimal = {
            "airline": {"iataCode": "CI"},
            "departure": {"iataCode": "TPE", "scheduledTime": "2026-04-04T14:00:00.000"},
            "arrival": {"iataCode": "KIX", "scheduledTime": "2026-04-04T17:30:00.000"},
            "flight": {"number": "152"},
            "status": "scheduled",
            "type": "departure",
        }
        flight = AviationEdgeFlight.model_validate(minimal)
        assert flight.airline.iata_code == "CI"
        assert flight.departure.iata_code == "TPE"
        assert flight.arrival.iata_code == "KIX"
        assert flight.flight.number == "152"
        assert flight.codeshared is None
        print("  ✓ 最小欄位航班解析正確")


# ============================================================
# 2. FlightRecord 轉換測試
# ============================================================


class TestFlightRecordConversion:
    """測試 Aviation Edge 資料轉換為統一 FlightRecord"""

    def test_timetable_to_flight_record(self):
        flight = AviationEdgeFlight.model_validate(SAMPLE_TIMETABLE_RESPONSE)
        record = AviationEdgeClient._timetable_to_flight_record(flight, "departure", "IAH")

        assert record.carrier_iata == "UA"
        assert record.carrier_icao == "UAL"
        assert record.flight_number == "1268"
        assert record.departure_airport_iata == "IAH"
        assert record.arrival_airport_iata == "EWR"
        assert record.scheduled_departure == "2026-04-04T06:00:00.000"
        assert record.scheduled_arrival == "2026-04-04T10:21:00.000"
        assert record.actual_departure == "2026-04-04T06:12:00.000"
        assert record.actual_arrival is None
        assert record.status == "active"
        assert record.direction == "departure"
        assert record.taiwan_airport == "IAH"
        print("  ✓ 即時航班 → FlightRecord 轉換正確")

    def test_future_to_flight_record(self):
        flight = AviationEdgeFutureFlight.model_validate(SAMPLE_FUTURE_RESPONSE)
        record = AviationEdgeClient._future_to_flight_record(flight, "departure", "TPE")

        assert record.carrier_iata == "BR"
        assert record.carrier_icao == "EVA"
        assert record.flight_number == "198"
        assert record.departure_airport_iata == "TPE"
        assert record.arrival_airport_iata == "NRT"
        assert record.scheduled_departure == "08:30"
        assert record.scheduled_arrival == "12:40"
        assert record.status == "scheduled"
        assert record.aircraft_type == "77W"
        assert record.direction == "departure"
        assert record.taiwan_airport == "TPE"
        print("  ✓ 未來航班 → FlightRecord 轉換正確")

    def test_flight_id_generation(self):
        flight = AviationEdgeFlight.model_validate(SAMPLE_TIMETABLE_RESPONSE)
        record = AviationEdgeClient._timetable_to_flight_record(flight, "departure", "IAH")
        assert record.flight_id == "UA1268-2026-04-04T06:00:00.000"
        print("  ✓ FlightRecord.flight_id 生成正確")


# ============================================================
# 3. API 連線測試（需要有效 API key）
# ============================================================


class TestAPIConnection:
    """實際呼叫 Aviation Edge API 測試

    需要設定環境變數 AVIATION_EDGE_API_KEY 才能執行。
    """

    @pytest.fixture
    def client(self):
        return AviationEdgeClient()

    @pytest.mark.asyncio
    async def test_timetable_tpe_departures(self, client):
        """測試查詢桃園機場即時出境航班"""
        try:
            flights = await client.get_timetable("TPE", "departure")
            print(f"\n  TPE 即時出境航班: {len(flights)} 筆")
            if flights:
                f = flights[0]
                print(f"  範例: {f.airline.iata_code if f.airline else '?'}"
                      f"{f.flight.number if f.flight else '?'} → "
                      f"{f.arrival.iata_code if f.arrival else '?'} "
                      f"({f.status})")
            assert isinstance(flights, list)
            print("  ✓ 桃園出境航班查詢成功")
        except Exception as e:
            if "401" in str(e) or "403" in str(e) or not client.api_key:
                pytest.skip(f"API key 無效或未設定: {e}")
            raise
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_timetable_tpe_arrivals(self, client):
        """測試查詢桃園機場即時入境航班"""
        try:
            flights = await client.get_timetable("TPE", "arrival")
            print(f"\n  TPE 即時入境航班: {len(flights)} 筆")
            if flights:
                f = flights[0]
                print(f"  範例: {f.airline.iata_code if f.airline else '?'}"
                      f"{f.flight.number if f.flight else '?'} ← "
                      f"{f.departure.iata_code if f.departure else '?'} "
                      f"({f.status})")
            assert isinstance(flights, list)
            print("  ✓ 桃園入境航班查詢成功")
        except Exception as e:
            if "401" in str(e) or "403" in str(e) or not client.api_key:
                pytest.skip(f"API key 無效或未設定: {e}")
            raise
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_timetable_with_airline_filter(self, client):
        """測試航空公司篩選"""
        try:
            flights = await client.get_timetable("TPE", "departure", airline_iata="BR")
            print(f"\n  TPE 長榮出境航班: {len(flights)} 筆")
            for f in flights[:3]:
                print(f"  - {f.flight.iata_number if f.flight else '?'} → "
                      f"{f.arrival.iata_code if f.arrival else '?'}")
            assert isinstance(flights, list)
            print("  ✓ 航空公司篩選查詢成功")
        except Exception as e:
            if "401" in str(e) or "403" in str(e) or not client.api_key:
                pytest.skip(f"API key 無效或未設定: {e}")
            raise
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_taiwan_departures_unified(self, client):
        """測試統一格式的台灣出境航班"""
        try:
            records = await client.get_taiwan_departures("TPE")
            print(f"\n  TPE 統一格式出境: {len(records)} 筆")
            if records:
                r = records[0]
                print(f"  範例: {r.carrier_iata}{r.flight_number} "
                      f"{r.departure_airport_iata}→{r.arrival_airport_iata} "
                      f"[{r.status}]")
            assert isinstance(records, list)
            if records:
                assert records[0].taiwan_airport == "TPE"
                assert records[0].direction == "departure"
            print("  ✓ 統一格式出境航班正確")
        except Exception as e:
            if "401" in str(e) or "403" in str(e) or not client.api_key:
                pytest.skip(f"API key 無效或未設定: {e}")
            raise
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_future_flights(self, client):
        """測試未來航班查詢"""
        try:
            from datetime import date, timedelta
            future_date = (date.today() + timedelta(days=3)).isoformat()
            flights = await client.get_future_flights("TPE", "departure", future_date)
            print(f"\n  TPE {future_date} 未來出境: {len(flights)} 筆")
            if flights:
                f = flights[0]
                print(f"  範例: {f.airline.iata_code if f.airline else '?'}"
                      f"{f.flight.number if f.flight else '?'} → "
                      f"{f.arrival.iata_code if f.arrival else '?'}"
                      f" (機型: {f.aircraft.iata_code if f.aircraft else 'N/A'})")
            assert isinstance(flights, list)
            print("  ✓ 未來航班查詢成功")
        except Exception as e:
            if "401" in str(e) or "403" in str(e) or not client.api_key:
                pytest.skip(f"API key 無效或未設定: {e}")
            raise
        finally:
            await client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
