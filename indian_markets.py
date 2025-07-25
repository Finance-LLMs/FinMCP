# indian_markets.py
from mcp.server.fastmcp import FastMCP
from nsepython import *
from bse import BSE
import pandas as pd
from datetime import datetime

mcp = FastMCP("IndianMarkets")

# Initialize BSE client with caching
bse = BSE(download_folder='/Users/abhay/IIIT-Delhi/MIDAS/MCP/MCP_tools/bse_cache')

from nsepython import nse_eq

@mcp.tool()
def get_nse_quote(ticker: str) -> dict:
    """Get real-time NSE quote with improved error handling"""
    try:
        symbol = nsesymbolpurify(ticker.upper())
        data = nse_eq(symbol)
        
        return {
            "ticker": symbol,
            "last_price": data.get('priceInfo', {}).get('lastPrice'),
            "open": data.get('priceInfo', {}).get('open'),
            "high": data.get('priceInfo', {}).get('intraDayHighLow', {}).get('max'),
            "low": data.get('priceInfo', {}).get('intraDayHighLow', {}).get('min'),
            "volume": data.get('securityWiseDP', {}).get('quantityTraded'),
            "52_week_high": data.get('priceInfo', {}).get('high52'),
            "52_week_low": data.get('priceInfo', {}).get('low52'),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": f"NSE quote failed: {str(e)}"}

@mcp.tool()  
def get_nse_indices(index: str = "NIFTY 50") -> dict:
    """Get real-time index values for NSE indices"""
    try:
        data = nse_live_index(index.replace(" ", "%20"))
        return {
            "index": index.upper(),
            "current": data['data'][0]['last'],
            "change": data['data'][0]['change'],
            "52_week_high": data['data'][0]['yearHigh'],
            "constituents": [item['symbol'] for item in data['data'][0]['advance']]
        }
    except Exception as e:
        return {"error": f"NSE index failed: {str(e)}"}

@mcp.tool()
def get_bse_quote(scrip_code: int) -> dict:
    """Get real-time BSE quote with robust error handling"""
    try:
        quote = bse.quote(scrip_code)
        
        # Safely extract values with multiple fallback keys
        current_price = quote.get('currentValue') or quote.get('lastPrice') or quote.get('ltp')
        day_high = quote.get('high') or quote.get('dayHigh')
        day_low = quote.get('low') or quote.get('dayLow')
        volume = quote.get('totalTradedVolume') or quote.get('totalTradeQuantity')
        
        return {
            "scrip_code": scrip_code,
            "exchange": "BSE",
            "current_price": float(current_price) if current_price else None,
            "day_high": float(day_high) if day_high else None,
            "day_low": float(day_low) if day_low else None,
            "volume": int(volume) if volume else None,
            "last_update": quote.get('lastUpdateTime'),
            "security_name": quote.get('securityID')
        }
    except Exception as e:
        return {
            "error": f"BSE quote failed: {str(e)}",
            "resolution": "Verify scrip code or check API status",
            "documentation": "https://bseindia.com/api/equityapi/documentation"
        }

@mcp.tool()
def get_bse_corporate_actions(scrip_code: int) -> dict:
    """Get corporate actions (dividends, splits) for BSE-listed stocks"""
    try:
        actions = bse.actions(scripcode=scrip_code)
        return {
            "scrip_code": scrip_code,
            "dividends": [a for a in actions if a['purpose'].startswith('Dividend')],
            "splits": [a for a in actions if 'Split' in a['purpose']]
        }
    except Exception as e:
        return {"error": f"BSE corporate actions failed: {str(e)}"}

@mcp.tool()
def get_indian_stock_info(ticker: str) -> dict:
    """Unified stock info with multi-exchange support"""
    try:
        if '.' in ticker:  # NSE format
            symbol = ticker.split('.')[0]
            return get_nse_quote(symbol)
        elif ticker.isdigit():  # BSE code
            return get_bse_quote(int(ticker))
        else:
            # Attempt auto-detection
            try:
                return get_nse_quote(ticker)
            except:
                return get_bse_quote(ticker)
    except Exception as e:
        return {"error": f"Stock info failed: {str(e)}"}

@mcp.tool()
def get_historical_data(ticker: str, period: str = "1y") -> dict:
    """Get historical data for Indian stocks"""
    try:
        if ticker.isdigit():
            df = bse.get_historical_data(int(ticker), period=period)
        else:
            df = nse_historical_data(ticker, period)
            
        return {
            "ticker": ticker,
            "data": df.reset_index().to_dict(orient='records')
        }
    except Exception as e:
        return {"error": f"Historical data failed: {str(e)}"}

@mcp.tool()
def get_indian_option_chain(ticker: str) -> dict:
    """Get options chain for NSE F&O stocks"""
    try:
        chain = nse_option_chain_scrapper(ticker)
        return {
            "ticker": ticker,
            "expiry_dates": chain['expiryDates'],
            "call_oi": chain['callOI'],
            "put_oi": chain['putOI']
        }
    except Exception as e:
        return {"error": f"Option chain failed: {str(e)}"}

@mcp.tool()
def get_market_status() -> dict:
    """Get live market status for Indian exchanges"""
    try:
        nse_status = "Open" if nse_marketStatus()['marketState'][0]['marketStatus'] == "Open" else "Closed"
        bse_status = bse.market_status().get('isOpen', 'Closed')
        
        return {
            "NSE": nse_status,
            "BSE": "Open" if bse_status else "Closed",
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        }
    except Exception as e:
        return {"error": f"Market status check failed: {str(e)}"}


if __name__ == "__main__":
    mcp.run(port=8001)
    quote = bse.quote(scrip_code)
    print(f"BSE raw response for {scrip_code}: {quote}")