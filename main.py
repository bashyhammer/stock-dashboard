import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yfinance as tk
from pydantic import BaseModel

# -------------------------------------------------------------------
# IN-MEMORY STATE (Virtual Portfolio & AI Logs)
# -------------------------------------------------------------------
portfolio = {
    "cash": 10000.00,
    "holdings": {},         # Format: {"RIG": {"shares": 10, "avg_price": 5.85}}
    "trade_history": []     # Log of all transactions
}

ai_settings = {
    "active": True,               # Toggle AI on/off
    "buy_dip_threshold": -1.5,    # Buy if daily change <= -1.5%
    "sell_profit_threshold": 2.0, # Sell if gain >= +2.0%
    "trade_amount": 10            # Shares per trade
}

DEFAULT_TICKERS = ["RIG", "KOS", "BORR", "SOFI", "BBAI", "PLTR", "NIO", "RIVN", "LCID", "GRPN", "SNDL"]

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

# -------------------------------------------------------------------
# HELPER FUNCTIONS & AI TRADING ENGINE
# -------------------------------------------------------------------

def fetch_stock_data_internal(symbol: str):
    """ Internal helper to fetch stock details cleanly. """
    symbol = symbol.upper()
    try:
        stock = tk.Ticker(symbol)
        info = stock.info
        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or price
        
        if not price or price == 0.0:
            fb = FALLBACK_PRICES.get(symbol, {"price": 10.00, "change": 0.00, "sector": "Technology"})
            return {"symbol": symbol, "price": fb["price"], "change": fb["change"], "sector": fb["sector"]}
        
        change = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
        return {"symbol": symbol, "price": round(price, 2), "change": round(change, 2), "sector": info.get("sector", "Unknown")}
    except Exception:
        fb = FALLBACK_PRICES.get(symbol, {"price": 10.00, "change": 0.00, "sector": "Technology"})
        return {"symbol": symbol, "price": fb["price"], "change": fb["change"], "sector": fb["sector"]}


async def run_ai_trading_cycle():
    """ Background loop running every 30 seconds to make AI trading decisions. """
    while True:
        await asyncio.sleep(30)
        if not ai_settings["active"]:
            continue

        for symbol in DEFAULT_TICKERS:
            data = fetch_stock_data_internal(symbol)
            price = data["price"]
            change = data["change"]
            shares_to_trade = ai_settings["trade_amount"]

            # --- BUY LOGIC (Dip Buyer) ---
            if change <= ai_settings["buy_dip_threshold"]:
                total_cost = price * shares_to_trade
                if portfolio["cash"] >= total_cost:
                    portfolio["cash"] -= total_cost
                    if symbol in portfolio["holdings"]:
                        existing = portfolio["holdings"][symbol]
                        tot_shares = existing["shares"] + shares_to_trade
                        avg_p = ((existing["shares"] * existing["avg_price"]) + total_cost) / tot_shares
                        portfolio["holdings"][symbol] = {"shares": tot_shares, "avg_price": round(avg_p, 2)}
                    else:
                        portfolio["holdings"][symbol] = {"shares": shares_to_trade, "avg_price": round(price, 2)}

                    portfolio["trade_history"].append({
                        "type": "AI BUY",
                        "symbol": symbol,
                        "shares": shares_to_trade,
                        "price": price,
                        "reason": f"Price dipped {change}%"
                    })

            # --- SELL LOGIC (Profit Taker) ---
            elif symbol in portfolio["holdings"]:
                holding = portfolio["holdings"][symbol]
                avg_buy_price = holding["avg_price"]
                profit_percent = ((price - avg_buy_price) / avg_buy_price) * 100 if avg_buy_price else 0.0

                if profit_percent >= ai_settings["sell_profit_threshold"]:
                    sell_shares = min(shares_to_trade, holding["shares"])
                    total_revenue = price * sell_shares
                    portfolio["cash"] += total_revenue
                    portfolio["holdings"][symbol]["shares"] -= sell_shares

                    if portfolio["holdings"][symbol]["shares"] == 0:
                        del portfolio["holdings"][symbol]

                    portfolio["trade_history"].append({
                        "type": "AI SELL",
                        "symbol": symbol,
                        "shares": sell_shares,
                        "price": price,
                        "reason": f"Took profit (+{profit_percent:.2f}%)"
                    })


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background AI engine on app boot
    asyncio.create_task(run_ai_trading_cycle())
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TradeRequest(BaseModel):
    ticker: str
    shares: int

# -------------------------------------------------------------------
# ENDPOINTS
# -------------------------------------------------------------------

@app.get("/stocks")
def get_stocks(tickers: str = None):
    ticker_list = tickers.split(",") if tickers else DEFAULT_TICKERS
    data = []
    for symbol in ticker_list:
        st = fetch_stock_data_internal(symbol)
        data.append({
            "symbol": st["symbol"],
            "sector": st["sector"],
            "price": st["price"],
            "change": st["change"],
            "target_hit": 5.0 <= st["price"] <= 10.0,
            "volume": 1000000,
            "market_cap": 500000000
        })
    return data

@app.get("/portfolio")
def get_portfolio():
    return portfolio

@app.get("/ai-status")
def get_ai_status():
    return {"settings": ai_settings, "recent_trades": portfolio["trade_history"][-10:]}

@app.post("/buy")
def buy_stock(trade: TradeRequest):
    symbol = trade.ticker.upper()
    shares = trade.shares
    data = fetch_stock_data_internal(symbol)
    price = data["price"]
    total_cost = price * shares

    if portfolio["cash"] < total_cost:
        raise HTTPException(status_code=400, detail="Insufficient virtual cash!")

    portfolio["cash"] -= total_cost
    if symbol in portfolio["holdings"]:
        existing = portfolio["holdings"][symbol]
        tot_shares = existing["shares"] + shares
        avg_p = ((existing["shares"] * existing["avg_price"]) + total_cost) / tot_shares
        portfolio["holdings"][symbol] = {"shares": tot_shares, "avg_price": round(avg_p, 2)}
    else:
        portfolio["holdings"][symbol] = {"shares": shares, "avg_price": round(price, 2)}

    portfolio["trade_history"].append({"type": "MANUAL BUY", "symbol": symbol, "shares": shares, "price": price, "reason": "User manual trigger"})
    return {"message": f"Bought {shares} shares of {symbol} at ${price:.2f}", "portfolio": portfolio}

@app.post("/sell")
def sell_stock(trade: TradeRequest):
    symbol = trade.ticker.upper()
    shares = trade.shares
    if symbol not in portfolio["holdings"] or portfolio["holdings"][symbol]["shares"] < shares:
        raise HTTPException(status_code=400, detail="Not enough shares to sell.")

    data = fetch_stock_data_internal(symbol)
    price = data["price"]
    total_revenue = price * shares

    portfolio["cash"] += total_revenue
    portfolio["holdings"][symbol]["shares"] -= shares
    if portfolio["holdings"][symbol]["shares"] == 0:
        del portfolio["holdings"][symbol]

    portfolio["trade_history"].append({"type": "MANUAL SELL", "symbol": symbol, "shares": shares, "price": price, "reason": "User manual trigger"})
    return {"message": f"Sold {shares} shares of {symbol} at ${price:.2f}", "portfolio": portfolio}