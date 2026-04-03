from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    oag_api_key: str = ""
    oag_base_url: str = "https://api.oag.com"

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# 台灣所有機場的 IATA 代碼
TAIWAN_AIRPORTS = {
    "TPE": "桃園國際機場",
    "TSA": "台北松山機場",
    "KHH": "高雄國際機場",
    "RMQ": "台中清泉崗機場",
    "TNN": "台南機場",
    "KNH": "金門機場",
    "MZG": "澎湖馬公機場",
    "HUN": "花蓮機場",
    "TTT": "台東機場",
    "GNI": "綠島機場",
    "KYD": "蘭嶼機場",
    "CMJ": "七美機場",
    "LZN": "馬祖南竿機場",
    "MFK": "馬祖北竿機場",
}

settings = Settings()
