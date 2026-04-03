# Flight Schedule Service

台灣機場航班表服務，支援兩種資料來源：

1. **桃園機場官網爬蟲** - 直接從 [taoyuan-airport.com](https://www.taoyuan-airport.com/) 爬取即時航班資料（無需 API Key）
2. **OAG Flight Info API v2** - 透過 [OAG](https://developers.oag.com/) 收集所有台灣機場的航班資料

## 功能

- **桃園機場爬蟲**: 即時爬取桃園機場出入境航班，無需申請 API Key
- 收集所有台灣機場（TPE、TSA、KHH、RMQ 等 14 個機場）的出入境航班（OAG）
- 依機場查詢出境 / 入境航班
- 通用航班搜尋（依航空公司、航班號、日期等條件）
- 自動分頁處理，取得完整航班清單
- 統一格式輸出（FlightRecord），方便不同資料來源比較

## 快速開始

### 1. 安裝

```bash
pip install -e .
```

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env，填入你的 OAG API Key
```

### 3. 啟動服務

```bash
uvicorn app.main:app --reload
```

服務啟動後，開啟 http://localhost:8000/docs 查看 Swagger API 文件。

## API Endpoints

| Method | Path | 說明 |
|--------|------|------|
| GET | `/health` | 健康檢查 |
| GET | `/api/flights/airports` | 列出所有台灣機場 |
| GET | `/api/flights/taiwan/all` | 收集所有台灣機場出入境航班 |
| GET | `/api/flights/taiwan/{airport_code}/departures` | 查詢指定機場出境航班 |
| GET | `/api/flights/taiwan/{airport_code}/arrivals` | 查詢指定機場入境航班 |
| GET | `/api/flights/search` | 通用航班搜尋 |
| GET | `/api/scraper/taoyuan/departures` | 爬取桃園機場出境航班 |
| GET | `/api/scraper/taoyuan/arrivals` | 爬取桃園機場入境航班 |
| GET | `/api/scraper/taoyuan/all` | 爬取桃園機場所有航班 |

### 範例

```bash
# 收集所有台灣機場的今日航班
curl http://localhost:8000/api/flights/taiwan/all

# 只查詢桃園和高雄機場
curl "http://localhost:8000/api/flights/taiwan/all?airports=TPE,KHH"

# 查詢特定日期
curl "http://localhost:8000/api/flights/taiwan/all?query_date=2026-04-03"

# 桃園機場出境航班
curl http://localhost:8000/api/flights/taiwan/TPE/departures

# 通用搜尋 (OAG)
curl "http://localhost:8000/api/flights/search?departure_airport=TPE&departure_date=2026-04-03"

# === 桃園機場爬蟲 (無需 API Key) ===

# 爬取桃園機場出境航班
curl http://localhost:8000/api/scraper/taoyuan/departures

# 爬取桃園機場入境航班
curl http://localhost:8000/api/scraper/taoyuan/arrivals

# 爬取所有航班
curl http://localhost:8000/api/scraper/taoyuan/all
```

## 技術架構

- **Python 3.11+**
- **FastAPI** - Web 框架
- **httpx** - 非同步 HTTP 客戶端
- **Pydantic v2** - 資料驗證與序列化
- **BeautifulSoup4** - HTML 解析（桃園機場爬蟲）
- **OAG Flight Info API v2** - 航班資料來源（需 API Key）
