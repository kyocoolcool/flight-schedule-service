import logging
import re
from datetime import date

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.models.flight import FlightRecord

logger = logging.getLogger(__name__)

BASE_URL = "https://www.taoyuan-airport.com"

DEPART_URL = f"{BASE_URL}/flight_depart"
ARRIVAL_URL = f"{BASE_URL}/flight_arrival"


class TaoyuanAirportScraper:
    """桃園機場航班資料爬蟲

    使用 Playwright (non-headless) 透過真實瀏覽器爬取，以繞過 Cloudflare 防護。
    網站使用 Angular 渲染，航班資料以 <li> 列表呈現。
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None

    async def _ensure_browser(self):
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
        return self._browser

    async def _new_page(self):
        browser = await self._ensure_browser()
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        await page.add_init_script(
            'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        )
        return page

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def get_departures(self, lang: str = "en") -> list[FlightRecord]:
        """爬取出境航班"""
        url = f"{DEPART_URL}?lang={lang}&time=all"
        return await self._scrape_flights(url, direction="departure")

    async def get_arrivals(self, lang: str = "en") -> list[FlightRecord]:
        """爬取入境航班"""
        url = f"{ARRIVAL_URL}?lang={lang}&time=all"
        return await self._scrape_flights(url, direction="arrival")

    async def get_all_flights(self, lang: str = "en") -> list[FlightRecord]:
        """爬取所有出入境航班"""
        departures = await self.get_departures(lang)
        arrivals = await self.get_arrivals(lang)
        return departures + arrivals

    async def _scrape_flights(
        self,
        url: str,
        direction: str,
    ) -> list[FlightRecord]:
        """使用 Playwright 爬取航班頁面並解析資料"""
        page = await self._new_page()

        try:
            logger.info("Scraping %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # 等待 Cloudflare challenge 完成 + Angular 渲染航班資料
            try:
                await page.wait_for_selector(
                    ".scheduled_time",
                    timeout=30000,
                )
            except Exception:
                logger.warning("scheduled_time not found, waiting extra time")
                await page.wait_for_timeout(15000)

            html = await page.content()
            return self._parse_flight_html(html, direction)
        finally:
            await page.close()

    def _parse_flight_html(self, html: str, direction: str) -> list[FlightRecord]:
        """解析航班 HTML 頁面

        桃園機場網站使用 Angular 渲染，航班以 <li> 列表呈現。
        每個 <li> 包含多個 <div>，結構為：
        - div[0]: 時間 (.scheduled_time, .actual_time)
        - div[1]: 目的地/出發地 (.phone_fix)
        - div[2]: 航空公司 (.airline_title)
        - div[3]: 航班號碼
        - div[4]: 航廈 (.terminal)
        - div[5]: 登機門
        - div[6]: 報到櫃檯
        - div[7]: 狀態 (.state)
        """
        soup = BeautifulSoup(html, "lxml")
        flights: list[FlightRecord] = []

        # 找所有包含 scheduled_time 的 <li>（即航班項目）
        flight_items = [li for li in soup.find_all("li") if li.select_one(".scheduled_time")]

        today = date.today().isoformat()

        for item in flight_items:
            scheduled_time = self._get_text(item, ".scheduled_time")
            actual_time = self._get_text(item, ".actual_time")
            status = self._get_text(item, ".state")
            terminal = self._get_text(item, ".terminal")
            # 清理 terminal 文字（去掉 "航廈" 前綴）
            terminal = terminal.replace("航廈", "").replace("Terminal", "").strip()

            # 目的地/出發地
            dest_div = item.select_one(".phone_fix")
            location = ""
            if dest_div:
                ps = [p.get_text(strip=True) for p in dest_div.select("p") if p.get_text(strip=True)]
                location = ps[0] if ps else ""

            # 航空公司
            airline_div = item.select_one(".airline_title")
            airlines = []
            if airline_div:
                airlines = [p.get_text(strip=True) for p in airline_div.select("p") if p.get_text(strip=True)]

            # 航班號碼（airline_title 後面的 div）
            flight_numbers = []
            if airline_div:
                flight_div = airline_div.find_next_sibling("div")
                if flight_div and "airline_title" not in (flight_div.get("class") or []):
                    flight_numbers = [p.get_text(strip=True) for p in flight_div.select("p") if p.get_text(strip=True)]

            # 登機門
            gate = ""
            terminal_el = item.select_one(".terminal")
            if terminal_el:
                gate_div = terminal_el.find_next_sibling("div")
                if gate_div:
                    gate_p = gate_div.select_one("p")
                    gate = gate_p.get_text(strip=True) if gate_p else ""

            if not flight_numbers:
                continue

            # 主航班號碼（第一個）
            primary_flight = flight_numbers[0]
            carrier, flight_num = self._parse_flight_number(primary_flight)

            if direction == "departure":
                flights.append(
                    FlightRecord(
                        carrier_iata=carrier,
                        flight_number=flight_num,
                        departure_airport_iata="TPE",
                        arrival_airport_iata=location,
                        scheduled_departure=f"{today}T{scheduled_time}" if scheduled_time else None,
                        actual_departure=f"{today}T{actual_time}" if actual_time else None,
                        status=status,
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
                        departure_airport_iata=location,
                        arrival_airport_iata="TPE",
                        scheduled_arrival=f"{today}T{scheduled_time}" if scheduled_time else None,
                        actual_arrival=f"{today}T{actual_time}" if actual_time else None,
                        status=status,
                        direction=direction,
                        taiwan_airport="TPE",
                        flight_type="scheduled",
                    )
                )

        logger.info("Parsed %d %s flights", len(flights), direction)
        return flights

    @staticmethod
    def _get_text(element, selector: str) -> str:
        el = element.select_one(selector)
        return el.get_text(strip=True) if el else ""

    @staticmethod
    def _parse_flight_number(text: str) -> tuple[str | None, str | None]:
        """解析航班號碼文字，提取航空公司代碼和航班號"""
        text = text.strip()
        match = re.search(r"([A-Z0-9]{2})\s*(\d{1,4}[A-Z]?)", text)
        if match:
            return match.group(1), match.group(2)
        return None, text if text else None


# Singleton
taoyuan_scraper = TaoyuanAirportScraper()
