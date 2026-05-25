"""Market data fetching via yfinance."""
import pandas as pd
import yfinance as yf


def fetch_ohlcv(ticker: str, period: str = "60d", interval: str = "1h") -> pd.DataFrame:
    """
    Download OHLCV candles. Returns a DataFrame with lowercase columns:
    open, high, low, close, volume — indexed by datetime.
    """
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
    return df.dropna()


def current_price(ticker: str) -> float:
    df = fetch_ohlcv(ticker, period="1d", interval="5m")
    return float(df["close"].iloc[-1])


def get_instrument_name(ticker_yf: str) -> str:
    """Return the long name for a yfinance ticker, or the ticker itself if unavailable."""
    try:
        info = yf.Ticker(ticker_yf).info
        return info.get("longName") or info.get("shortName") or ticker_yf
    except Exception:
        return ticker_yf
