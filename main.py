from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yfinance as tk
from pydantic import BaseModel

app = FastAPI()

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# PAPER TRADING IN-MEMORY STATE (Virtual Portfolio)
# -------------------------------------------------------------------
portfolio = {
    "cash": 10000.00,       # Starting virtual cash
    "holdings": {},         # Format: {"AAPL": {"shares": 10, "avg_price": 150.00}}
    "trade_history": []     # Log of past transactions
}

class TradeRequest(BaseModel):
    ticker: str
    shares: int

# -------------------------------------------------------------------
# EXISTING STOCK DATA ENDPOINTS
# -------------------------------------------------------------------

DEFAULT_TICKERS = ["RIG", "KOS", "BORR", "SOFI", "BBAI", "PLTR", "NIO", "RIVN", "LCID", "GRPN", "SNDL"]

# MOCK FALLBACK PRICES (Used automatically if Yahoo Finance blocks or rate-limits requests)
FALLBACK_PRICES = {
    "RIG": {"price": 5.85, "change": -2.82, "sector": "Energy"},
    "KOS": {"price": 2.78, "change": -1.42, "sector": "Energy"},
    "BORR": {"price": 4.54, "change": -1.52, "sector": "Energy"},
    "SOFI": {"price": 18.22, "change": -1.57, "sector": "Financial Services"},
    "BBAI": {"price": 2.92, "change": -2.01, "sector": "Technology"},
    "PLTR": {"price": 174.33, "change": -4.49, "sector": "Technology"},
    "NIO": {"price": 3.80, "change": -1.55, "sector": "Consumer Cyclical"},
    "RIVN": {"price": 15.74, "change": -1.07, "sector": "Consumer Cyclical"},
    "LCID": {"price": 4.68, "change": 1.74, "sector": "Consumer Cyclical"},
    "GRPN": {"price": 18.87, "change": 0.05, "sector": "Communication Services"},
    "SNDL": {"price": 1.44, "change": 1.77, "sector": "Consumer Defensive"}
}

@app.get("/stocks")
def get_stocks(tickers: str = None):
    ticker_list = tickers.split(",") if tickers else DEFAULT_TICKERS
    data = []

    for symbol in ticker_list:
        symbol = symbol.upper()
        try:
            stock = tk.Ticker(symbol)
            info = stock.info
            
            price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or price
            
            # If Yahoo Finance blocks or returns invalid 0 price, load fallback market data
            if not price or price == 0.0:
                fb = FALLBACK_PRICES.get(symbol, {"price": 10.00, "change": 0.00, "sector": "Technology"})
                price = fb["price"]
                change = fb["change"]
                sector = fb["sector"]
            else:
                change = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
                sector = info.get("sector", "Unknown")

            data.append({
                "symbol": symbol,
                "sector": sector,
                "price": round(price, 2),
                "change": round(change, 2),
                "target_hit": 5.0 <= price <= 10.0,
                "volume": info.get("volume", 1000000),
                "market_cap": info.get("marketCap", 500000000)
            })
        except Exception:
            fb = FALLBACK_PRICES.get(symbol, {"price": 10.00, "change": 0.00, "sector": "Technology"})
            data.append({
                "symbol": symbol,
                "sector": fb["sector"],
                "price": fb["price"],
                "change": fb["change"],
                "target_hit": 5.0 <= fb["price"] <= 10.0,
                "volume": 1000000,
                "market_cap": 500000000
            })
            
    return data

@app.get("/history/{symbol}")
def get_history(symbol: str):
    try:
        stock = tk.Ticker(symbol)
        hist = stock.history(period="1m")
        history_data = [
            {"date": str(index.date()), "close": round(row["Close"], 2)}
            for index, row in hist.iterrows()
        ]
        return {"symbol": symbol, "history": history_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------------------------
# NEW: PAPER TRADING ENDPOINTS
# -------------------------------------------------------------------

@app.get("/portfolio")
def get_portfolio():
    """ Returns current virtual cash balance, active holdings, and trade history. """
    return portfolio

@app.post("/buy")
def buy_stock(trade: TradeRequest):
    """ Simulated buying logic. """
    symbol = trade.ticker.upper()
    shares = trade.shares
    
    if shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be greater than 0")
        
    stock = tk.Ticker(symbol)
    price = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice")
    
    if not price:
        raise HTTPException(status_code=400, detail=f"Could not fetch live price for {symbol}")
        
    total_cost = price * shares
    
    if portfolio["cash"] < total_cost:
        raise HTTPException(status_code=400, detail=f"Insufficient virtual cash! Need ${total_cost:.2f}, have ${portfolio['cash']:.2f}")
        
    # Deduct cash
    portfolio["cash"] -= total_cost
    
    # Update holdings
    if symbol in portfolio["holdings"]:
        existing = portfolio["holdings"][symbol]
        total_shares = existing["shares"] + shares
        # Weighted average buy price
        new_avg = ((existing["shares"] * existing["avg_price"]) + total_cost) / total_shares
        portfolio["holdings"][symbol] = {"shares": total_shares, "avg_price": round(new_avg, 2)}
    else:
        portfolio["holdings"][symbol] = {"shares": shares, "avg_price": round(price, 2)}
        
    # Log trade
    trade_log = {"type": "BUY", "symbol": symbol, "shares": shares, "price": round(price, 2), "total": round(total_cost, 2)}
    portfolio["trade_history"].append(trade_log)
    
    return {"message": f"Successfully bought {shares} shares of {symbol} at ${price:.2f}", "portfolio": portfolio}

@app.post("/sell")
def sell_stock(trade: TradeRequest):
    """ Simulated selling logic. """
    symbol = trade.ticker.upper()
    shares = trade.shares
    
    if shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be greater than 0")
        
    if symbol not in portfolio["holdings"] or portfolio["holdings"][symbol]["shares"] < shares:
        raise HTTPException(status_code=400, detail=f"Not enough shares of {symbol} to sell.")
        
    stock = tk.Ticker(symbol)
    price = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice")
    
    if not price:
        raise HTTPException(status_code=400, detail=f"Could not fetch live price for {symbol}")
        
    total_revenue = price * shares
    
    # Add cash
    portfolio["cash"] += total_revenue
    
    # Update holdings
    portfolio["holdings"][symbol]["shares"] -= shares
    if portfolio["holdings"][symbol]["shares"] == 0:
        del portfolio["holdings"][symbol]
        
    # Log trade
    trade_log = {"type": "SELL", "symbol": symbol, "shares": shares, "price": round(price, 2), "total": round(total_revenue, 2)}
    portfolio["trade_history"].append(trade_log)
    
    return {"message": f"Successfully sold {shares} shares of {symbol} at ${price:.2f}", "portfolio": portfolio}