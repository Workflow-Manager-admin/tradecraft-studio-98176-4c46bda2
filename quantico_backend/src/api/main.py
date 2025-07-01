from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
import sqlite3
import secrets
import datetime
import os


# --- Swagger Metadata ---
app = FastAPI(
    title="Quantico Backend API",
    description=(
        "API backend for Quantico financial app with user authentication, "
        "strategy management, backtesting, trading, and AI endpoints."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "Authentication and OAuth"},
        {"name": "user", "description": "User account management"},
        {"name": "strategy", "description": "Strategy CRUD operations"},
        {"name": "backtest", "description": "Historical data and backtesting"},
        {"name": "trading", "description": "Paper trading endpoints"},
        {"name": "portfolio", "description": "Portfolio tracker"},
        {"name": "ai", "description": "AI assistant functions"},
        {"name": "theme", "description": "User theme preferences"},
        {"name": "integration", "description": "TradingView/Recharts integration endpoints"},
        {"name": "health", "description": "Health and status checks"},
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("QUANTICO_DB_FILE", "quantico.db")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db()
    cur = conn.cursor()
    # Users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT,
        google_id TEXT,
        full_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        theme_pref TEXT DEFAULT 'light'
    );
    """)
    # Auth tokens (demo - not full production ready)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS auth_tokens (
        user_id INTEGER,
        token TEXT,
        expires_at TIMESTAMP
    );
    """)
    # Strategies
    cur.execute("""
    CREATE TABLE IF NOT EXISTS strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        name TEXT,
        description TEXT,
        config_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # Portfolio
    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        asset TEXT,
        quantity REAL,
        cost_basis REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # Trades (paper trading)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        strategy_id INTEGER REFERENCES strategies(id),
        asset TEXT,
        side TEXT,
        qty REAL,
        price REAL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # AI assistant logs (optional)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ai_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        request TEXT,
        response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


create_tables()


# --- Models and Schemas ---
class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str
    full_name: Optional[str] = None


class UserRead(UserBase):
    id: int
    full_name: Optional[str] = None
    theme_pref: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StrategyBase(BaseModel):
    name: str
    description: Optional[str] = ""
    config_json: dict


class StrategyCreate(StrategyBase):
    pass


class StrategyUpdate(StrategyBase):
    pass


class StrategyRead(StrategyBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PortfolioEntry(BaseModel):
    asset: str
    quantity: float
    cost_basis: float
    id: Optional[int] = None


class PaperTrade(BaseModel):
    id: Optional[int]
    asset: str
    side: str
    qty: float
    price: float
    timestamp: datetime.datetime
    strategy_id: Optional[int] = None


class AIRequest(BaseModel):
    prompt: str


class AIResponse(BaseModel):
    result: str


class ThemePreference(BaseModel):
    theme: str = Field(..., description="Theme, either 'light' or 'dark'.")


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return user


def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user_id: int, expires_minutes=120) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.now() + datetime.timedelta(
        minutes=expires_minutes
    )
    conn = get_db()
    conn.execute(
        "INSERT INTO auth_tokens (user_id, token, expires_at) VALUES (?,?,?)",
        (user_id, token, expires_at),
    )
    conn.commit()
    conn.close()
    return token


def get_current_user(token: str = Depends(oauth2_scheme)) -> sqlite3.Row:
    conn = get_db()
    data = conn.execute(
        "SELECT users.* FROM users "
        "JOIN auth_tokens ON users.id = auth_tokens.user_id "
        "WHERE auth_tokens.token = ? "
        "AND auth_tokens.expires_at > ?",
        (token, datetime.datetime.now())
    ).fetchone()
    conn.close()
    if not data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return data


# PUBLIC_INTERFACE
@app.get("/", tags=["integration"])
def landing_page():
    """
    Get application overview and landing message.
    Returns a greeting for Quantico.
    """
    return {"message": "Welcome to Quantico! Full-stack fintech platform API is up."}


# --- HEALTH ENDPOINTS ---

# PUBLIC_INTERFACE
@app.get(
    "/health/db",
    tags=["health"],
    summary="Check database connectivity",
    description=(
        "Performs a simple SELECT 1 query to verify SQLite DB connection. "
        "Returns JSON with status ok or error and detail."
    ),
    response_model=dict,
    responses={
        200: {
            "description": "Database healthy",
            "content": {"application/json": {}},
        },
        503: {
            "description": "Database error",
            "content": {"application/json": {}},
        },
    },
)
def health_db_check():
    """
    Health check for SQLite database connection.

    Returns:
        200: {"status": "ok"} if DB is reachable and SELECT works.
        503: {"status": "error", "detail": <exception>} if any DB error occurs.
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "detail": str(e),
            },
        )


# --- AUTHENTICATION ENDPOINTS ---
# PUBLIC_INTERFACE
@app.post("/auth/register", response_model=UserRead, tags=["auth"], summary="Register with email/password")
def register(user: UserCreate):
    """
    Register new user with email and password.
    """
    if get_user_by_email(user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(user.password)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (email, hashed_password, full_name) VALUES (?,?,?)",
        (user.email, hashed, user.full_name)
    )
    conn.commit()
    user_id = cur.lastrowid
    user_row = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return UserRead(
        id=user_row["id"],
        email=user_row["email"],
        full_name=user_row["full_name"],
        theme_pref=user_row["theme_pref"]
    )


# PUBLIC_INTERFACE
@app.post("/auth/token", response_model=Token, tags=["auth"], summary="Login with email/password to get token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate user via email and password.
    """
    user = get_user_by_email(form_data.username)
    if not user or not user["hashed_password"] or not verify_password(
            form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token = create_access_token(user["id"])
    return {"access_token": token}


# PUBLIC_INTERFACE
@app.post("/auth/google", tags=["auth"], summary="Login with Google OAuth", response_model=Token)
def google_login(
    authorization: str = Header(..., description="Google OAuth token in Authorization header (Bearer <token>)"),
    request: Request = None
):
    """
    Authenticate via Google OAuth token (mock/demo; in production validate token with Google).

    Expects the Google OAuth token in the Authorization header as 'Bearer <token>'.
    """
    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=400, detail="Invalid Authorization header format")
    token = authorization[7:]

    # This should verify token with Google OAuth2 endpoint; here, just pseudo-demo.
    google_id = "mock_google_id_from_token_" + token[-8:]

    # Search for existing user or create new
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    if not user:
        email = f"user_{google_id}@google.mock"
        conn.execute("INSERT INTO users (email, google_id) VALUES (?,?)", (email, google_id))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    token_val = create_access_token(user["id"])
    conn.close()
    return {"access_token": token_val}


# --- USER ENDPOINTS ---
# PUBLIC_INTERFACE
@app.get("/user/me", response_model=UserRead, tags=["user"])
def get_me(current_user=Depends(get_current_user)):
    """Get current user's data."""
    return UserRead(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        theme_pref=current_user["theme_pref"],
    )


# PUBLIC_INTERFACE
@app.patch("/user/me", response_model=UserRead, tags=["user"])
def update_me(
    full_name: Optional[str] = None,
    theme_pref: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """
    Update current user's profile (full name, light/dark theme).
    """
    conn = get_db()
    if full_name:
        conn.execute(
            "UPDATE users SET full_name = ? WHERE id = ?",
            (full_name, current_user["id"])
        )
    if theme_pref in ["light", "dark"]:
        conn.execute(
            "UPDATE users SET theme_pref = ? WHERE id = ?",
            (theme_pref, current_user["id"])
        )
    conn.commit()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (current_user["id"],)
    ).fetchone()
    conn.close()
    return UserRead(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        theme_pref=user["theme_pref"]
    )


# --- STRATEGY CRUD ENDPOINTS ---
# PUBLIC_INTERFACE
@app.post("/strategies", response_model=StrategyRead, tags=["strategy"])
def create_strategy(strategy: StrategyCreate, current_user=Depends(get_current_user)):
    """
    Create a new trading strategy.
    """
    conn = get_db()
    now = datetime.datetime.now()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO strategies "
        "(user_id, name, description, config_json, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            current_user["id"],
            strategy.name,
            strategy.description,
            str(strategy.config_json),
            now,
            now,
        ),
    )
    conn.commit()
    id_ = cur.lastrowid
    row = conn.execute(
        "SELECT * FROM strategies WHERE id = ?",
        (id_,)
    ).fetchone()
    conn.close()
    return StrategyRead(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        config_json=eval(row["config_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


# PUBLIC_INTERFACE
@app.get("/strategies", response_model=List[StrategyRead], tags=["strategy"])
def list_strategies(current_user=Depends(get_current_user)):
    """
    List all trading strategies for the current user.
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM strategies WHERE user_id = ?",
        (current_user["id"],)
    ).fetchall()
    strategies = []
    for row in rows:
        strategies.append(
            StrategyRead(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                config_json=eval(
                    row["config_json"]
                ),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    conn.close()
    return strategies


# PUBLIC_INTERFACE
@app.get("/strategies/{strategy_id}", response_model=StrategyRead, tags=["strategy"])
def get_strategy(strategy_id: int, current_user=Depends(get_current_user)):
    """
    Get a trading strategy by ID.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM strategies WHERE id = ? "
        "AND user_id = ?",
        (
            strategy_id,
            current_user["id"],
        ),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return StrategyRead(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        config_json=eval(row["config_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


# PUBLIC_INTERFACE
@app.put("/strategies/{strategy_id}", response_model=StrategyRead, tags=["strategy"])
def update_strategy(strategy_id: int, strategy: StrategyUpdate, current_user=Depends(get_current_user)):
    """
    Update a trading strategy.
    """
    conn = get_db()
    now = datetime.datetime.now()
    conn.execute(
        "UPDATE strategies "
        "SET name = ?, description = ?, config_json = ?, updated_at = ? "
        "WHERE id = ? AND user_id = ?",
        (
            strategy.name,
            strategy.description,
            str(strategy.config_json),
            now,
            strategy_id,
            current_user["id"],
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM strategies WHERE id = ?",
        (strategy_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return StrategyRead(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        config_json=eval(row["config_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


# PUBLIC_INTERFACE
@app.delete("/strategies/{strategy_id}", tags=["strategy"], response_model=dict)
def delete_strategy(strategy_id: int, current_user=Depends(get_current_user)):
    """
    Delete a trading strategy.
    """
    conn = get_db()
    conn.execute(
        "DELETE FROM strategies WHERE id = ? AND user_id = ?",
        (strategy_id, current_user["id"])
    )
    conn.commit()
    conn.close()
    return {"status": True, "detail": "Strategy deleted"}


# --- BACKTESTING/HISTORICAL DATA ENDPOINTS ---

# PUBLIC_INTERFACE
@app.get("/backtest/history", tags=["backtest"], summary="Get historical data")
def get_historical_data(
    asset: str,
    start_date: str,
    end_date: str,
    resolution: str = "1d"
):
    """
    Retrieve mock historical data for an asset for backtesting.
    Replace with live API integration or database in production.
    """
    # For demo, generate synthetic 'OHLCV' data for given range
    import pandas as pd
    import numpy as np
    rng = pd.date_range(
        start=start_date,
        end=end_date,
        freq="D" if resolution == "1d" else "H"
    )
    np.random.seed(0)
    df = pd.DataFrame({
        "date": rng,
        "open": np.random.uniform(95, 105, len(rng)),
        "high": np.random.uniform(105, 110, len(rng)),
        "low": np.random.uniform(90, 95, len(rng)),
        "close": np.random.uniform(95, 110, len(rng)),
        "volume": np.random.uniform(500, 2000, len(rng))
    })
    return df.to_dict(orient='records')


# PUBLIC_INTERFACE
@app.post("/backtest/process", tags=["backtest"], summary="Run backtest on strategy")
def run_backtest(
    strategy_id: int,
    asset: str,
    start_date: str,
    end_date: str,
    current_user=Depends(get_current_user),
):
    """
    Process a backtest (demo/placeholder).
    """
    # In production: fetch user's strategy config, run backtest logic, return results
    # Here: mock output
    return {
        "strategy_id": strategy_id,
        "asset": asset,
        "start_date": start_date,
        "end_date": end_date,
        "roi": 0.134,
        "sharpe": 1.23,
        "drawdown": 0.072,
        "trade_count": 27,
        "pnl_curve": [
            {"date": start_date, "balance": 10000},
            {"date": end_date, "balance": 11340},
        ],
    }


# --- PAPER TRADING ENDPOINTS ---
# PUBLIC_INTERFACE
@app.post("/trades", tags=["trading"], response_model=PaperTrade)
def place_paper_trade(trade: PaperTrade, current_user=Depends(get_current_user)):
    """
    Place a mock (paper) trade.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO paper_trades "
        "(user_id, strategy_id, asset, side, qty, price) VALUES (?,?,?,?,?,?)",
        (
            current_user["id"],
            trade.strategy_id,
            trade.asset,
            trade.side,
            trade.qty,
            trade.price,
        ),
    )
    conn.commit()
    id_ = cur.lastrowid
    row = conn.execute("SELECT * FROM paper_trades WHERE id = ?", (id_,)).fetchone()
    conn.close()
    return PaperTrade(
        id=row["id"],
        asset=row["asset"],
        side=row["side"],
        qty=row["qty"],
        price=row["price"],
        timestamp=row["timestamp"],
        strategy_id=row["strategy_id"]
    )


# PUBLIC_INTERFACE
@app.get("/trades", tags=["trading"], response_model=List[PaperTrade])
def get_paper_trades(current_user=Depends(get_current_user)):
    """
    List all paper trades for current user.
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM paper_trades WHERE user_id = ?",
        (current_user["id"],)
    ).fetchall()
    trades = [
        PaperTrade(
            id=row["id"],
            asset=row["asset"],
            side=row["side"],
            qty=row["qty"],
            price=row["price"],
            timestamp=row["timestamp"],
            strategy_id=row["strategy_id"]
        )
        for row in rows
    ]
    conn.close()
    return trades


# --- PORTFOLIO TRACKER ENDPOINTS ---
# PUBLIC_INTERFACE
@app.get("/portfolio", tags=["portfolio"], response_model=List[PortfolioEntry])
def get_portfolio(current_user=Depends(get_current_user)):
    """
    Get portfolio assets for current user.
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM portfolios WHERE user_id = ?",
        (current_user["id"],)
    ).fetchall()
    entries = [
        PortfolioEntry(
            id=row["id"],
            asset=row["asset"],
            quantity=row["quantity"],
            cost_basis=row["cost_basis"],
        )
        for row in rows
    ]
    conn.close()
    return entries


# PUBLIC_INTERFACE
@app.post("/portfolio", tags=["portfolio"], response_model=PortfolioEntry)
def add_portfolio_entry(entry: PortfolioEntry, current_user=Depends(get_current_user)):
    """
    Add an asset to user's portfolio.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO portfolios (user_id, asset, quantity, cost_basis) VALUES (?,?,?,?)",
        (current_user["id"], entry.asset, entry.quantity, entry.cost_basis)
    )
    conn.commit()
    id_ = cur.lastrowid
    row = conn.execute(
        "SELECT * FROM portfolios WHERE id = ?",
        (id_,)
    ).fetchone()
    conn.close()
    return PortfolioEntry(
        id=row["id"],
        asset=row["asset"],
        quantity=row["quantity"],
        cost_basis=row["cost_basis"]
    )


# --- AI ASSISTANT ENDPOINT ---
# PUBLIC_INTERFACE
@app.post("/ai/assist", tags=["ai"], response_model=AIResponse, summary="AI assistant for strategies")
def ai_assistant(request: AIRequest, current_user=Depends(get_current_user)):
    """
    AI assistant for strategy recommendations or optimization.
    Demo returns a mock suggestion.
    """
    prompt = request.prompt
    mock_response = (
        f"(AI mock) Based on your request: {prompt} => "
        "Consider a SMA(30)-MACD cross strategy for strong trends."
    )
    conn = get_db()
    conn.execute(
        "INSERT INTO ai_requests (user_id, request, response) VALUES (?,?,?)",
        (current_user["id"], prompt, mock_response)
    )
    conn.commit()
    conn.close()
    return AIResponse(result=mock_response)


# --- THEME ENDPOINT ---
# PUBLIC_INTERFACE
@app.get("/user/theme", tags=["theme"], response_model=ThemePreference)
def get_theme(current_user=Depends(get_current_user)):
    """
    Get current user's light/dark mode preference.
    """
    return ThemePreference(theme=current_user["theme_pref"])


# PUBLIC_INTERFACE
@app.post("/user/theme", tags=["theme"], response_model=ThemePreference)
def set_theme(pref: ThemePreference, current_user=Depends(get_current_user)):
    """
    Set user light/dark mode preference.
    """
    if pref.theme not in ["light", "dark"]:
        raise HTTPException(status_code=400, detail="Must be 'light' or 'dark' theme")
    conn = get_db()
    conn.execute("UPDATE users SET theme_pref = ? WHERE id = ?", (pref.theme, current_user["id"]))
    conn.commit()
    conn.close()
    return pref


# --- INTEGRATION: CHART DATA ENDPOINTS (TradingView/Recharts) ---
# PUBLIC_INTERFACE
@app.get("/integration/chart", tags=["integration"], summary="Candlestick/OHLC chart data")
def chart_data(
    asset: str,
    start_date: str,
    end_date: str,
    resolution: str = "1d"
):
    """
    Endpoint for TradingView or Recharts integration to fetch chart data.
    """
    # For demo, same as /backtest/history
    import pandas as pd
    import numpy as np
    rng = pd.date_range(
        start=start_date,
        end=end_date,
        freq="D" if resolution == "1d" else "H"
    )
    np.random.seed(7)
    df = pd.DataFrame(
        {
            "date": rng,
            "open": np.random.uniform(110, 130, len(rng)),
            "high": np.random.uniform(125, 135, len(rng)),
            "low": np.random.uniform(100, 115, len(rng)),
            "close": np.random.uniform(110, 140, len(rng)),
            "volume": np.random.uniform(
                200, 5000, len(rng)
            ),
        }
    )
    return df.to_dict(orient='records')


# --- Error Handling ---
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


# --- NOTES ON WEBSOCKET/REAL-TIME ---
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Quantico Backend API",
        version="1.0.0",
        description=(
            "API backend for Quantico financial app with user authentication, "
            "strategy management, backtesting, trading, and AI endpoints."
        ),
        routes=app.routes,
    )
    openapi_schema["info"]["x-websocket-usage"] = (
        "For real-time trading/updates: Backend supports future websocket APIs "
        "under /ws/ endpoints. See /docs or contact devs for active real-time feeds."
    )
    return openapi_schema


app.openapi = custom_openapi
