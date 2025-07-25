# stocks_server.py
import yfinance as yf
from mcp.server.fastmcp import FastMCP
import numpy as np
from datetime import datetime, timedelta
import logging
import os
# Create an MCP server
mcp = FastMCP("Stocks")

@mcp.tool() #working fine
def get_current_stock_price(ticker: str) -> dict:
    """Get current stock price for a given ticker symbol"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        # Use 'currentPrice' if available, otherwise fall back to 'open' or 'previousClose'
        price = info.get('currentPrice') or info.get('open') or info.get('previousClose')
        return {
            "ticker": ticker.upper(),
            "currency": "USD", 
            "price": price,
            "company_name": info.get('longName', 'N/A')
        }
    except Exception as e:
        return {"error": f"Failed to get price for {ticker}: {str(e)}"}

@mcp.tool() #working fine
def get_historical_stock_splits(ticker: str) -> dict:
    """Get list of historical stock splits for a given ticker symbol"""
    try:
        stock = yf.Ticker(ticker)
        splits = stock.splits
        
        if splits.empty:
            return {
                "ticker": ticker.upper(),
                "total": 0, 
                "history": [],
                "message": "No stock splits found"
            }
        
        history = []
        for timestamp, ratio in splits.to_dict().items():
            history.append({
                "date": timestamp.strftime("%A, %B %d, %Y"),
                "ratio": float(ratio),
            })
        
        return {
            "ticker": ticker.upper(),
            "total": len(history), 
            "history": history
        }
    except Exception as e:
        return {"error": f"Failed to get splits for {ticker}: {str(e)}"}

@mcp.tool() #working fine
def get_stock_info(ticker: str) -> dict:
    """Get basic company information for a given ticker symbol"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "ticker": ticker.upper(),
            "company_name": info.get('longName', 'N/A'),
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "market_cap": info.get('marketCap', 'N/A'),
            "description": info.get('longBusinessSummary', 'N/A')[:200] + "..." if info.get('longBusinessSummary') else 'N/A'
        }
    except Exception as e:
        return {"error": f"Failed to get info for {ticker}: {str(e)}"}

@mcp.tool() #working fine
def get_financials(ticker: str, statement_type: str = "income") -> dict:
    """Get complete financial statements (income, balance sheet, cash flow)"""
    try:
        stock = yf.Ticker(ticker)
        if statement_type == "income":
            data = stock.income_stmt
        elif statement_type == "balance":
            data = stock.balance_sheet
        elif statement_type == "cashflow":
            data = stock.cash_flow
        else:
            return {"error": "Invalid statement type. Use 'income', 'balance', or 'cashflow'"}
        
        return {
            "ticker": ticker.upper(),
            "statement_type": statement_type,
            "periods": data.columns.strftime("%Y-%m-%d").tolist(),
            "metrics": data.index.tolist(),
            "values": data.values.tolist()
        }
    except Exception as e:
        return {"error": f"Failed to get {statement_type} statement: {str(e)}"}

@mcp.tool() #working fine
def get_dividend_analysis(ticker: str) -> dict:
    """Get complete dividend history and yield analysis"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="max")
        dividends = hist['Dividends'].resample('Y').sum()
        
        return {
            "ticker": ticker.upper(),
            "dividend_yield": stock.info.get('dividendYield', 0),
            "payout_ratio": stock.info.get('payoutRatio', 0),
            "annual_dividends": dividends[dividends > 0].to_dict(),
            "next_dividend_date": stock.calendar.get('exDividendDate', 'N/A')
        }
    except Exception as e:
        return {"error": f"Dividend analysis failed: {str(e)}"}

@mcp.tool() #working fine
def get_institutional_holders(ticker: str) -> dict:
    """Get institutional holders and their ownership details"""
    try:
        stock = yf.Ticker(ticker)
        holders = stock.institutional_holders
        return {
            "ticker": ticker.upper(),
            "holders": holders.to_dict(orient='records') if holders is not None else [],
            "total_shares": holders['Shares'].sum() if holders is not None else 0
        }
    except Exception as e:
        return {"error": f"Failed to get institutional holders: {str(e)}"}

@mcp.tool() #working fine
def get_options_chain(ticker: str, expiration: str = None) -> dict:
    """Retrieve complete options chain data"""
    try:
        stock = yf.Ticker(ticker)
        opts = stock.options
        if not expiration:
            expiration = opts[0]
            
        chain = stock.option_chain(expiration)
        return {
            "ticker": ticker.upper(),
            "expiration_date": expiration,
            "calls": chain.calls.to_dict(orient='records'),
            "puts": chain.puts.to_dict(orient='records'),
            "implied_volatility": chain.calls.impliedVolatility.mean()
        }
    except Exception as e:
        return {"error": f"Options chain retrieval failed: {str(e)}"}

@mcp.tool() #working fine, but not sure about the relevance of the news
def get_news_sentiment(ticker: str, days: int = 7) -> dict:
    """Analyze news sentiment with improved error handling and relevance filtering"""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        relevant_news = []
        now = datetime.now()
        
        for item in news:
            # Validate news item structure
            if not isinstance(item, dict):
                continue
                
            # Check relevance to ticker
            related_tickers = item.get('relatedTickers', [])
            if not related_tickers or ticker.upper() not in [rt.upper() for rt in related_tickers]:
                continue

            # Handle missing publish time gracefully
            pub_time = item.get('providerPublishTime')
            if not pub_time:
                logging.warning(f"Missing publish time for news item: {item.get('title')}")
                continue

            try:
                publish_date = datetime.fromtimestamp(pub_time)
                if now - publish_date > timedelta(days=days):
                    continue
            except (TypeError, OSError) as e:
                logging.error(f"Invalid timestamp {pub_time}: {str(e)}")
                continue

            relevant_news.append(item)

        # Sentiment analysis with case-insensitive matching
        positive = 0
        negative = 0
        for item in relevant_news:
            title = item.get('title', '').lower()
            if 'positive' in title or 'bullish' in title or 'buy' in title:
                positive += 1
            elif 'negative' in title or 'bearish' in title or 'sell' in title:
                negative += 1

        return {
            "ticker": ticker.upper(),
            "total_news_items": len(relevant_news),
            "positive_sentiment": positive,
            "negative_sentiment": negative,
            "latest_headlines": [n.get('title') for n in relevant_news[:3] if n.get('title')],
            "data_source": "Yahoo Finance (filtered)",
            "warning": "News API reliability varies - verify critical items"
        }
        
    except Exception as e:
        return {
            "error": f"News analysis failed: {str(e)}",
            "resolution": "Check API status or try again later",
            "documentation": "https://github.com/ranaroussi/yfinance/issues/1956"
        }
    
@mcp.tool() #working fine
def get_valuation_metrics(ticker: str) -> dict:
    """Get advanced valuation metrics"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "ticker": ticker.upper(),
            "pe_ratio": info.get('trailingPE'),
            "forward_pe": info.get('forwardPE'),
            "peg_ratio": info.get('pegRatio'),
            "ev_to_ebitda": info.get('enterpriseToEbitda'),
            "price_to_book": info.get('priceToBook'),
            "enterprise_value": info.get('enterpriseValue')
        }
    except Exception as e:
        return {"error": f"Valuation metrics failed: {str(e)}"}

@mcp.tool() #working fine
def get_sector_comparison(ticker: str) -> dict:
    """Compare company metrics against sector averages with robust DataFrame handling"""
    try:
        stock = yf.Ticker(ticker)
        sector = stock.info.get('sector', 'N/A')
        recommendations = stock.recommendations
        
        # Safe peers extraction
        peers = []
        if recommendations is not None and not recommendations.empty:
            if 'Firm' in recommendations.columns:
                peers = recommendations['Firm'].dropna().unique().tolist()[:5]
            elif recommendations.index.names and 'Firm' in recommendations.index.names:
                peers = recommendations.index.get_level_values('Firm').dropna().unique().tolist()[:5]
            else:
                peers = ["Peer data unavailable"]

        return {
            "ticker": ticker.upper(),
            "sector": sector,
            "sector_pe": stock.info.get('sectorPE', 'N/A'),
            "sector_peg": stock.info.get('sectorPEG', 'N/A'),
            "sector_pb": stock.info.get('sectorPriceToBook', 'N/A'),
            "peers": peers,
            "data_source": "Yahoo Finance API v3.2"
        }
    except Exception as e:
        return {
            "error": f"Sector analysis failed: {str(e)}",
            "resolution": "Verify ticker symbol or check API status",
            "documentation": "https://github.com/ranaroussi/yfinance/wiki/Ticker#recommendations"
        }

@mcp.tool() #working fine
def get_risk_metrics(ticker: str) -> dict:
    """Calculate volatility and risk metrics"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        returns = hist['Close'].pct_change().dropna()
        
        return {
            "ticker": ticker.upper(),
            "beta": stock.info.get('beta', 0),
            "annual_volatility": returns.std() * np.sqrt(252),
            "sharpe_ratio": (returns.mean() / returns.std()) * np.sqrt(252),
            "max_drawdown": (hist['Close'] / hist['Close'].cummax() - 1).min()
        }
    except Exception as e:
        return {"error": f"Risk assessment failed: {str(e)}"}

@mcp.tool() #working fine
def get_earnings_analysis(ticker: str) -> dict:
    """Analyze historical earnings and estimates"""
    try:
        stock = yf.Ticker(ticker)
        earnings = stock.earnings_dates
        return {
            "ticker": ticker.upper(),
            "eps_estimate": stock.info.get('forwardEps'),
            "eps_actual": earnings['Reported EPS'].dropna().tolist()[-4:],
            "surprise_pct": earnings['Surprise(%)'].dropna().tolist()[-4:]
        }
    except Exception as e:
        return {"error": f"Earnings analysis failed: {str(e)}"}

@mcp.tool() #working fine
def get_sec_filings(ticker: str, filing_type: str = '10-K') -> dict:
    """Retrieve SEC filings metadata with improved error handling"""
    try:
        stock = yf.Ticker(ticker)
        filings = stock.sec_filings  # Returns list of dictionaries
        
        if not isinstance(filings, list):
            raise ValueError("Unexpected SEC filings format")
            
        filtered = [
            f for f in filings 
            if f.get('formType', '').upper() == filing_type.upper()
        ]
        
        dates = [f.get('date') for f in filtered if 'date' in f]
        latest_date = max(dates) if dates else 'N/A'
        
        return {
            "ticker": ticker.upper(),
            "filing_type": filing_type,
            "count": len(filtered),
            "latest_filing_date": latest_date,
            "filings": filtered[:5]  # Return first 5 entries
        }
        
    except Exception as e:
        return {"error": f"SEC filings retrieval error: {str(e)}"}

# Add a tool to add summary of the latest message
SUMMARY_FILE = os.path.join(os.path.dirname(__file__), "summary.txt")
def ensure_file():
    if not os.path.exists(SUMMARY_FILE):
        with open(SUMMARY_FILE, "w") as f:
            f.write("")

@mcp.tool()
def add_summary(message: str) -> str:
    """
    Add a summary of the last message to the summary file
    Args:
        message: The message to add to the summary file
    Returns:
        A string indicating that the summary was added successfully
    """
    ensure_file()

    with open(SUMMARY_FILE, "a") as f:
        f.write(message + "\n")
    return "Summary added successfully"

# Add a tool to get the summary of the latest message
@mcp.tool()
def read_summary() -> str:
    """
    Read the summary of the latest message from the summary file
    Returns:
        A string containing the summary of the latest message
    """
    ensure_file()

    with open(SUMMARY_FILE, "r") as f:
        content = f.read()
        if not content:
            return "No summary found"
        return content


if __name__ == "__main__":
    mcp.run()