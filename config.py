import os

from dotenv import load_dotenv

load_dotenv()

T212_API_KEY: str = os.environ["T212_API_KEY"]
T212_SECRET_KEY: str = os.environ["T212_SECRET_KEY"]
T212_MODE: str = os.getenv("T212_MODE", "demo")
T212_BASE_URL: str = (
    "https://demo.trading212.com/api/v0"
    if T212_MODE == "demo"
    else "https://live.trading212.com/api/v0"
)

TOGETHER_API_KEY: str = os.environ["TOGETHER_API_KEY"]
AI_MODEL: str = os.getenv("AI_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo")

POSITION_FRACTION: float = float(os.getenv("POSITION_FRACTION", "0.95"))
STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "0.10"))

DASHBOARD_TOKEN: str = os.getenv("DASHBOARD_TOKEN", "")
