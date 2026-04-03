import logging
import re
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

from app.models.flight import FlightRecord

logger = logging.getLogger(__name__)

BASE_URL = "https://www.taoyuan-airport.com"

# 桃園機場航班頁面 URL
DEPART_URL = f"{BASE_URL}/flight_depart"
ARRIVAL_URL = f"{BASE_URL}/flight_arrival"

# 常見 User-Agent
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


class TaoyuanAirportScraper:
    """桃園機場航班資料爬蟲

    從 taoyuan-airport.com 爬取即時出入境航班資料。
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=HEADERS,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_departures(self, lang: str = "en") -> list[FlightRecord]:
        """爬取出境航班"""
        params = {"lang": lang, "time": "all"}
        return await self._scrape_flights(DEPART_URL, params, direction="departure")

    async def get_arrivals(self, lang: str = "en") -> list[FlightRecord]:
        """爬取入境航班"""
        params = {"lang": lang, "time": "all"}
        return await self._scrape_flights(ARRIVAL_URL, params, direction="arrival")

    async def get_all_flights(self, lang: str = "en") -> list[FlightRecord]:
        """爬取所有出入境航班"""
        departures = await self.get_departures(lang)
        arrivals = await self.get_arrivals(lang)
        return departures + arrivals

    async def _scrape_flights(
        self,
        url: str,
        params: dict,
        direction: str,
    ) -> list[FlightRecord]:
        """爬取航班頁面並解析資料"""
        client = await self._get_client()

        logger.info("Scraping %s with params=%s", url, params)
        response = await client.get(url, params=params)
        response.raise_for_status()

        html = response.text
        return self._parse_flight_html(html, direction)

    def _parse_flight_html(self, html: str, direction: str) -> list[FlightRecord]:
        """解析航班 HTML 頁面

        桃園機場的航班頁面包含航班表格，每行包含：
        - 預計時間 (Scheduled)
        - 實際時間 (Actual)
        - 航班號碼 (Flight No.)
        - 航空公司 (Airline)
        - 目的地/出發地 (Destination/Origin)
        - 航廈 (Terminal)
        - 登機門 (Gate)
        - 狀態 (Status)
        """
        soup = BeautifulSoup(html, "lxml")
        flights: list[FlightRecord] = []

        # 嘗試多種表格選擇器，因為網站結構可能更新
        tables = soup.select("table.flight-table, table.table, .flight-list table, #flight-list table")
        if not tables:
            # 備用：找所有包含航班資料的表格
            tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # 嘗試從表頭判斷欄位位置
            header_row = rows[0]
            headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]

            col_map = self._detect_columns(headers, direction)
            if not col_map:
                continue

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue

                flight = self._parse_row(cells, col_map, direction)
                if flight and flight.flight_number:
                    flights.append(flight)

        # 如果表格方式無效，嘗試從 div-based 結構解析
        if not flights:
            flights = self._parse_div_layout(soup, direction)

        logger.info("Parsed %d %s flights", len(flights), direction)
        return flights

    def _detect_columns(self, headers: list[str], direction: str) -> dict[str, int] | None:
        """根據表頭偵測欄位位置"""
        col_map: dict[str, int] = {}

        for i, h in enumerate(headers):
            h_lower = h.lower()
            if any(k in h_lower for k in ["scheduled", "預計", "表定", "排程"]):
                col_map["scheduled_time"] = i
            elif any(k in h_lower for k in ["actual", "實際", "異動"]):
                col_map["actual_time"] = i
            elif any(k in h_lower for k in ["flight", "航班", "班次", "班機"]):
                col_map["flight_no"] = i
            elif any(k in h_lower for k in ["airline", "航空"]):
                col_map["airline"] = i
            elif any(k in h_lower for k in ["destination", "目的", "抵達", "到達"]):
                col_map["destination"] = i
            elif any(k in h_lower for k in ["origin", "出發", "起飛地", "來自"]):
                col_map["origin"] = i
            elif any(k in h_lower for k in ["terminal", "航廈"]):
                col_map["terminal"] = i
            elif any(k in h_lower for k in ["gate", "登機門", "閘口"]):
                col_map["gate"] = i
            elif any(k in h_lower for k in ["status", "狀態", "備註"]):
                col_map["status"] = i

        # 至少要有航班號碼才有意義
        if "flight_no" not in col_map:
            return None
        return col_map

    def _parse_row(
        self,
        cells: list,
        col_map: dict[str, int],
        direction: str,
    ) -> FlightRecord | None:
        """解析一行航班資料"""

        def get_cell(key: str) -> str:
            idx = col_map.get(key)
            if idx is not None and idx < len(cells):
                return cells[idx].get_text(strip=True)
            return ""

        flight_no_text = get_cell("flight_no")
        if not flight_no_text:
            return None

        # 解析航班號碼：通常格式為 "CI 123" 或 "CI123" 或 "中華航空 CI 123"
        carrier, flight_num = self._parse_flight_number(flight_no_text)

        scheduled_time = get_cell("scheduled_time")
        actual_time = get_cell("actual_time")
        status = get_cell("status")
        airline = get_cell("airline")

        today = date.today().isoformat()

        if direction == "departure":
            dep_airport = "TPE"
            arr_airport = get_cell("destination")
            scheduled_dep = f"{today}T{scheduled_time}" if scheduled_time else None
            scheduled_arr = None
            actual_dep = f"{today}T{actual_time}" if actual_time else None
            actual_arr = None
        else:
            dep_airport = get_cell("origin")
            arr_airport = "TPE"
            scheduled_dep = None
            scheduled_arr = f"{today}T{scheduled_time}" if scheduled_time else None
            actual_dep = None
            actual_arr = f"{today}T{actual_time}" if actual_time else None

        return FlightRecord(
            carrier_iata=carrier,
            flight_number=flight_num,
            departure_airport_iata=dep_airport,
            arrival_airport_iata=arr_airport,
            scheduled_departure=scheduled_dep,
            scheduled_arrival=scheduled_arr,
            actual_departure=actual_dep,
            actual_arrival=actual_arr,
            status=status,
            flight_type="scheduled",
            direction=direction,
            taiwan_airport="TPE",
        )

    def _parse_div_layout(self, soup: BeautifulSoup, direction: str) -> list[FlightRecord]:
        """解析 div-based 航班佈局 (部分機場網站使用 div 而非 table)"""
        flights: list[FlightRecord] = []

        # 嘗試找航班卡片/列表項目
        flight_items = soup.select(
            ".flight-item, .flight-row, .flight-info, "
            "[class*='flight'], [class*='Flight'], "
            ".list-item, .data-row"
        )

        for item in flight_items:
            text = item.get_text(" ", strip=True)
            # 嘗試用正則表達式提取航班資訊
            flight_match = re.search(r"([A-Z]{2})\s*(\d{1,4})", text)
            if not flight_match:
                continue

            carrier = flight_match.group(1)
            flight_num = flight_match.group(2)

            # 嘗試提取時間 (HH:MM 格式)
            times = re.findall(r"(\d{2}:\d{2})", text)
            scheduled_time = times[0] if times else None
            actual_time = times[1] if len(times) > 1 else None

            today = date.today().isoformat()

            if direction == "departure":
                flights.append(
                    FlightRecord(
                        carrier_iata=carrier,
                        flight_number=flight_num,
                        departure_airport_iata="TPE",
                        scheduled_departure=f"{today}T{scheduled_time}" if scheduled_time else None,
                        actual_departure=f"{today}T{actual_time}" if actual_time else None,
                        direction=direction,
                        taiwan_airport="TPE",
                        flight_type="scheduled",
                    )
                )
            else:
                flights.append(
                    FlightRecord(
                        carrier_iata=carrier,
                        flight_number=flight_num,
                        arrival_airport_iata="TPE",
                        scheduled_arrival=f"{today}T{scheduled_time}" if scheduled_time else None,
                        actual_arrival=f"{today}T{actual_time}" if actual_time else None,
                        direction=direction,
                        taiwan_airport="TPE",
                        flight_type="scheduled",
                    )
                )

        return flights

    @staticmethod
    def _parse_flight_number(text: str) -> tuple[str | None, str | None]:
        """解析航班號碼文字，提取航空公司代碼和航班號

        支援格式:
        - "CI 123"
        - "CI123"
        - "BR 891"
        - "JX 123"
        """
        text = text.strip()
        match = re.search(r"([A-Z]{2})\s*(\d{1,4}[A-Z]?)", text)
        if match:
            return match.group(1), match.group(2)
        return None, text if text else None


# Singleton
taoyuan_scraper = TaoyuanAirportScraper()
