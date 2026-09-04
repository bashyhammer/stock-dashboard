from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import math

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WATCHLIST = {
    "Energy": ["RIG", "KOS", "BORR"],
    "Technology": ["SOFI", "BBAI", "PLTR"],
    "EV & Auto": ["NIO", "RIVN", "LCID"],
    "Consumer": ["GRPN", "SNDL"]
}

def format_number(num):
    """Helper function to format large numbers (e.g., 1.5B, 450M)"""
    if not num or math.isnan(num):
        return "N/A"
    if num >= 1e9:
        return f"${num / 1e9:.2f}B"
    if num >= 1e6:
        return f"${num / 1e6:.2f}M"
    return f"${num:,.0f}"

def fetch_single_stock(symbol: str, sector: str = "Custom Search"):
    """Helper function to process a single stock symbol"""
    stock = yf.Ticker(symbol.upper())
    history = stock.history(period="2d")
    
    if history.empty or len(history) < 2:
        return None

    prev_close = history['Close'].iloc[-2]
    curr_price = history['Close'].iloc[-1]
    
    if math.isnan(curr_price) or math.isnan(prev_close):
        return None

    pct_change = ((curr_price - prev_close) / prev_close) * 100
    if math.isnan(pct_change):
        pct_change = 0.0

    curr_price_float = float(curr_price)
    target_hit = 5.00 <= curr_price_float <= 10.00
    
    volume = history['Volume'].iloc[-1] if 'Volume' in history else 0
    market_cap = stock.info.get('marketCap', None)
    
    # Try to grab official sector name if available
    info_sector = stock.info.get('sector', sector)

    return {
        "symbol": symbol.upper(),
        "sector": info_sector,
        "price": round(curr_price_float, 2),
        "change": round(float(pct_change), 2),
        "under_limit": bool(curr_price_float <= 10.00),
        "target_hit": bool(target_hit),
        "volume": f"{int(volume):,}" if volume and not math.isnan(volume) else "N/A",
        "market_cap": format_number(market_cap)
    }

@app.get("/")
def home():
    return {"message": "Stock Tracker API is active. Go to /api/stocks"}

@app.get("/api/stocks")
def get_stock_data():
    results = []
    for sector, tickers in WATCHLIST.items():
        for symbol in tickers:
            try:
                data = fetch_single_stock(symbol, sector)
                if data:
                    results.append(data)
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
                continue
    return {"status": "success", "data": results}

@app.get("/api/stock/{symbol}")
def get_single_stock(symbol: str):
    """Endpoint for on-demand stock search"""
    try:
        data = fetch_single_stock(symbol)
        if not data:
            return {"status": "error", "message": f"Symbol '{symbol}' not found or insufficient data."}
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/history/{symbol}")
def get_stock_history(symbol: str):
    """Endpoint to fetch 30-day price history for modal trend chart"""
    try:
        stock = yf.Ticker(symbol.upper())
        history = stock.history(period="1mo")
        
        if history.empty:
            return {"status": "error", "message": "No history found"}

        dates = history.index.strftime('%Y-%m-%d').tolist()
        prices = [round(p, 2) for p in history['Close'].tolist()]

        return {
            "status": "success",
            "symbol": symbol.upper(),
            "dates": dates,
            "prices": prices
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8501, reload=True)
