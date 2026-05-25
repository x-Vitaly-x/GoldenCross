"""
Together.ai LLM analysis of trading signals.

The AI commentary is informational — it is logged alongside every decision
so we can evaluate whether LLM reasoning adds value in Phase 2.
It does NOT override the rule-based signal.
"""
import config
from together import Together

_client = Together(api_key=config.TOGETHER_API_KEY)


def _call_llm(prompt: str, max_tokens: int, temperature: float) -> str:
    try:
        response = _client.chat.completions.create(
            model=config.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"AI analysis unavailable: {e}"


def analyse(ticker: str, signal: str, indicators: dict, recent_closes: list[float]) -> str:
    """Comment on a trading signal given current indicators and recent price action."""
    if not indicators:
        return "Insufficient data for analysis."

    price_str = ", ".join(f"{p:.2f}" for p in recent_closes[-12:])
    prompt = (
        f"You are a concise quantitative analyst. Evaluate this trading signal.\n\n"
        f"Instrument: {ticker}\n"
        f"Signal: {signal}\n"
        f"Price: {indicators['price']}\n"
        f"SMA20: {indicators['sma_fast']} | SMA50: {indicators['sma_slow']}\n"
        f"RSI(14): {indicators['rsi']}\n"
        f"Last 12 hourly closes: {price_str}\n\n"
        f"In 2-3 sentences: Is this signal technically sound? "
        f"Any notable concerns or confirmations? Be factual, no financial advice."
    )
    return _call_llm(prompt, max_tokens=250, temperature=0.2)


def analyse_instrument(ticker_t212: str, name: str, existing_instruments: list[dict]) -> str:
    """Evaluate whether adding a new instrument makes sense given the current portfolio."""
    existing_names = (
        ", ".join(i.get("name", i["ticker_t212"]) for i in existing_instruments) or "none"
    )
    prompt = (
        f"You are a concise portfolio analyst. Evaluate whether adding this instrument makes sense.\n\n"
        f"New instrument: {name} (Trading212 ticker: {ticker_t212})\n"
        f"Currently monitored instruments: {existing_names}\n\n"
        f"In 3-4 sentences: Is this a reasonable portfolio addition? "
        f"Consider asset class, geographic exposure, and correlation with existing holdings. "
        f"Be factual. No financial advice."
    )
    return _call_llm(prompt, max_tokens=300, temperature=0.3)
