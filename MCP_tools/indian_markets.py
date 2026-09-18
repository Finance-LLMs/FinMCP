import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from bse import BSE
from mcp.server.fastmcp import FastMCP
from nsepython import (
    nse_eq,
    nse_historical_data,
    nse_live_index,
    nse_marketStatus,
    nse_option_chain_scrapper,
    nsesymbolpurify,
)

mcp = FastMCP("IndianMarkets")

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".bse_cache"))
os.makedirs(CACHE_DIR, exist_ok=True)
bse = BSE(download_folder=CACHE_DIR)


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@mcp.tool()
def get_nse_quote(ticker: str) -> dict:
    """Get real-time NSE quote with safer extraction and error handling."""
    try:
        symbol = nsesymbolpurify(ticker.upper())
        data = nse_eq(symbol)

        price_info = data.get("priceInfo", {})
        security_dp = data.get("securityWiseDP", {})
        intra_day = price_info.get("intraDayHighLow", {})

        return {
            "ticker": symbol,
            "last_price": _safe_float(price_info.get("lastPrice")),
            "open": _safe_float(price_info.get("open")),
            "high": _safe_float(intra_day.get("max")),
            "low": _safe_float(intra_day.get("min")),
            "previous_close": _safe_float(price_info.get("previousClose")),
            "volume": _safe_int(security_dp.get("quantityTraded")),
            "avg_volume": _safe_int(security_dp.get("averageQuantityTraded")),
            "52_week_high": _safe_float(price_info.get("high52")),
            "52_week_low": _safe_float(price_info.get("low52")),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        return {"error": f"NSE quote failed: {str(exc)}"}


@mcp.tool()
def get_nse_indices(index: str = "NIFTY 50") -> dict:
    """Get real-time index values for NSE indices."""
    try:
        payload = nse_live_index(index.replace(" ", "%20"))
        data = payload.get("data", [{}])[0]
        return {
            "index": index.upper(),
            "current": _safe_float(data.get("last")),
            "change": _safe_float(data.get("change")),
            "percent_change": _safe_float(data.get("pChange")),
            "day_high": _safe_float(data.get("dayHigh")),
            "day_low": _safe_float(data.get("dayLow")),
            "52_week_high": _safe_float(data.get("yearHigh")),
            "52_week_low": _safe_float(data.get("yearLow")),
            "constituents": [item.get("symbol") for item in data.get("advance", []) if item.get("symbol")],
        }
    except Exception as exc:
        return {"error": f"NSE index failed: {str(exc)}"}


@mcp.tool()
def get_nse_market_snapshot(indices: Optional[List[str]] = None) -> dict:
    """Return a quick snapshot of key NSE indices in one call."""
    index_list = indices or ["NIFTY 50", "NIFTY BANK", "SENSEX"]
    snapshot: Dict[str, Any] = {}

    for index_name in index_list:
        try:
            result = get_nse_indices(index_name)
            if "error" in result:
                snapshot[index_name] = {"error": result["error"]}
            else:
                snapshot[index_name] = result
        except Exception as exc:
            snapshot[index_name] = {"error": str(exc)}

    return {"indices": snapshot, "timestamp": datetime.now().isoformat()}


@mcp.tool()
def get_bse_quote(scrip_code: int) -> dict:
    """Get real-time BSE quote with robust error handling."""
    try:
        quote = bse.quote(scrip_code)

        current_price = quote.get("currentValue") or quote.get("lastPrice") or quote.get("ltp")
        day_high = quote.get("high") or quote.get("dayHigh")
        day_low = quote.get("low") or quote.get("dayLow")
        volume = quote.get("totalTradedVolume") or quote.get("totalTradeQuantity")

        return {
            "scrip_code": scrip_code,
            "exchange": "BSE",
            "current_price": _safe_float(current_price),
            "day_high": _safe_float(day_high),
            "day_low": _safe_float(day_low),
            "volume": _safe_int(volume),
            "last_update": quote.get("lastUpdateTime"),
            "security_name": quote.get("securityID"),
        }
    except Exception as exc:
        return {
            "error": f"BSE quote failed: {str(exc)}",
            "resolution": "Verify scrip code or check API status",
            "documentation": "https://bseindia.com/api/equityapi/documentation",
        }


@mcp.tool()
def get_bse_corporate_actions(scrip_code: int) -> dict:
    """Get corporate actions (dividends, splits) for BSE-listed stocks."""
    try:
        actions = bse.actions(scripcode=scrip_code)
        return {
            "scrip_code": scrip_code,
            "dividends": [item for item in actions if str(item.get("purpose", "")).lower().startswith("dividend")],
            "splits": [item for item in actions if "split" in str(item.get("purpose", "")).lower()],
        }
    except Exception as exc:
        return {"error": f"BSE corporate actions failed: {str(exc)}"}


@mcp.tool()
def get_indian_stock_info(ticker: str) -> dict:
    """Unified stock info with automatic NSE/BSE detection and fallback."""
    try:
        cleaned = ticker.strip()
        if "." in cleaned:
            symbol = cleaned.split(".")[0]
            return get_nse_quote(symbol)
        if cleaned.isdigit():
            return get_bse_quote(int(cleaned))

        nse_quote = get_nse_quote(cleaned)
        if "error" not in nse_quote:
            return nse_quote

        try:
            return get_bse_quote(int(cleaned))
        except Exception:
            return {"error": f"Stock info failed for {cleaned}"}
    except Exception as exc:
        return {"error": f"Stock info failed: {str(exc)}"}


@mcp.tool()
def get_historical_data(ticker: str, period: str = "1y") -> dict:
    """Get historical data for Indian stocks."""
    try:
        if ticker.strip().isdigit():
            df = bse.get_historical_data(int(ticker), period=period)
        else:
            df = nse_historical_data(ticker, period)

        if df is None:
            return {"error": "No historical data returned"}

        return {
            "ticker": ticker,
            "period": period,
            "data": df.reset_index().to_dict(orient="records"),
        }
    except Exception as exc:
        return {"error": f"Historical data failed: {str(exc)}"}


@mcp.tool()
def get_indian_option_chain(ticker: str) -> dict:
    """Get options chain for NSE F&O stocks."""
    try:
        chain = nse_option_chain_scrapper(ticker)
        return {
            "ticker": ticker,
            "expiry_dates": chain.get("expiryDates", []),
            "call_oi": chain.get("callOI", []),
            "put_oi": chain.get("putOI", []),
        }
    except Exception as exc:
        return {"error": f"Option chain failed: {str(exc)}"}


@mcp.tool()
def get_market_status() -> dict:
    """Get live market status for Indian exchanges."""
    try:
        nse_status = "Open" if nse_marketStatus().get("marketState", [{}])[0].get("marketStatus") == "Open" else "Closed"
        bse_status = bse.market_status().get("isOpen", False)

        return {
            "NSE": nse_status,
            "BSE": "Open" if bse_status else "Closed",
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
        }
    except Exception as exc:
        return {"error": f"Market status check failed: {str(exc)}"}


@mcp.tool()
def get_market_movers(limit: int = 5) -> dict:
    """Get buy/sell sentiment for major Indian indices and constituent breadth."""
    try:
        result: Dict[str, Any] = {}
        for index_name in ["NIFTY 50", "NIFTY BANK", "SENSEX"]:
            payload = nse_live_index(index_name.replace(" ", "%20"))
            data = payload.get("data", [{}])[0]
            advancers = data.get("advance", [])[:limit]
            decliners = data.get("decline", [])[:limit]
            result[index_name] = {
                "current": _safe_float(data.get("last")),
                "change": _safe_float(data.get("change")),
                "percent_change": _safe_float(data.get("pChange")),
                "advancers": len(data.get("advance", [])),
                "decliners": len(data.get("decline", [])),
                "top_gainers": advancers,
                "top_losers": decliners,
            }

        return {"market_movers": result, "timestamp": datetime.now().isoformat()}
    except Exception as exc:
        return {"error": f"Market movers failed: {str(exc)}"}


@mcp.tool()
def get_index_constituents(index: str = "NIFTY 50", limit: Optional[int] = None) -> dict:
    """Fetch component symbols for an NSE index."""
    try:
        payload = nse_live_index(index.replace(" ", "%20"))
        data = payload.get("data", [{}])[0]
        constituents = data.get("advance", []) + data.get("decline", [])
        if limit is not None:
            constituents = constituents[:limit]
        return {
            "index": index.upper(),
            "constituents": constituents,
            "count": len(constituents),
        }
    except Exception as exc:
        return {"error": f"Index constituents failed: {str(exc)}"}


if __name__ == "__main__":
    mcp.run(port=8001)
