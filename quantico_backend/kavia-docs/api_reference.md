# Quantico Backend API Reference

This document provides a comprehensive reference to all API endpoints implemented in the Quantico FastAPI backend. It details each route, HTTP method, request and response structure, authentication requirements, and a description of its usage.

**Base URL**: `/`

---

## Table of Contents

- [Integration (Landing Page & Chart)](#integration)
- [Auth](#auth)
- [Health](#health)
- [User](#user)
- [Strategy Management](#strategy-management)
- [Backtest](#backtest)
- [Paper Trading](#paper-trading)
- [Portfolio](#portfolio)
- [AI Assistant](#ai-assistant)
- [Theme Preference](#theme-preference)

---

## Integration

### `GET /`
**Description:** Landing page endpoint. Returns a greeting and overview of the application.

**Authentication:** None

**Response Example:**
```json
{
  "message": "Welcome to Quantico! Full-stack fintech platform API is up."
}
```

### `GET /integration/chart`
**Description:** Provides candlestick/OHLC chart data for TradingView or Recharts integrations.

**Authentication:** None

**Query Parameters:**
- `asset` (string, required): Asset symbol (e.g., "AAPL").
- `start_date` (string, required): ISO8601 date.
- `end_date` (string, required): ISO8601 date.
- `resolution` (string, optional, default: "1d"): Data resolution ("1d" or "1h").

**Response:**  
List of OHLCV data objects for the requested period.

---

## Auth

### `POST /auth/register`
**Description:** Register a new user with email and password.

**Authentication:** None

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "your-password",
  "full_name": "John Doe"  // Optional
}
```

**Response** (`UserRead`):
```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "theme_pref": "light"
}
```

### `POST /auth/token`
**Description:** Obtain authentication token using email and password.

**Authentication:** None

**Request Body (application/x-www-form-urlencoded):**
- `username`: Email address
- `password`: Password

**Response** (`Token`):
```json
{
  "access_token": "<jwt_or_access_token>",
  "token_type": "bearer"
}
```

### `POST /auth/google`
**Description:** Login with Google OAuth (for demo; not production-validated).

**Authentication:** None (but expects Google OAuth token in Authorization header)

**Headers:**
- `Authorization: Bearer <google-oauth-token>`

**Response** (`Token`): Same as above

---

## Health

### `GET /health/db`
**Description:** Checks database connectivity.

**Authentication:** None

**Response:**
- Success: `{"status": "ok"}`
- Failure: `{"status": "error", "detail": "...error content..."}`

---

## User

### `GET /user/me`
**Description:** Retrieves the current authenticated user's information.

**Authentication:** Required (`Bearer` token)

**Response** (`UserRead`): Same structure as above

### `PATCH /user/me`
**Description:** Update the current user's profile (full name, theme).

**Authentication:** Required

**Request Body** (form data or JSON):
- `full_name` (string, optional)
- `theme_pref` (string, optional, "light" or "dark")

**Response:** Updated user data

---

## Strategy Management

### `POST /strategies`
**Description:** Create a new trading strategy.

**Authentication:** Required

**Request Body:**
```json
{
  "name": "My Strategy",
  "description": "Description",
  "config_json": { "rule": "SMA(30)" }
}
```

**Response** (`StrategyRead`):
```json
{
  "id": 1,
  "name": "My Strategy",
  "description": "Description",
  "config_json": {"rule": "SMA(30)"},
  "created_at": "...",
  "updated_at": "..."
}
```

### `GET /strategies`
**Description:** Get all strategies for the current user.

**Authentication:** Required

**Response:** List of `StrategyRead` objects

### `GET /strategies/{strategy_id}`
**Description:** Get a specific strategy for the user.

**Authentication:** Required

**Response:** `StrategyRead`

### `PUT /strategies/{strategy_id}`
**Description:** Update a strategy for the current user.

**Authentication:** Required

**Request Body:** Same as create

**Response:** Updated `StrategyRead`

### `DELETE /strategies/{strategy_id}`
**Description:** Delete the strategy for the current user.

**Authentication:** Required

**Response:**
```json
{"status": true, "detail": "Strategy deleted"}
```

---

## Backtest

### `GET /backtest/history`
**Description:** Retrieve historical data for backtesting.

**Authentication:** None

**Query Parameters:**
- `asset` (string, required)
- `start_date` (string, required)
- `end_date` (string, required)
- `resolution` (string, optional, default "1d")

**Response:**  
Array of OHLCV data objects

### `POST /backtest/process`
**Description:** Run a backtest for a strategy on historical data.

**Authentication:** Required

**Request Body/Form:**
- `strategy_id` (int, required)
- `asset` (string, required)
- `start_date` (string, required)
- `end_date` (string, required)

**Response:**
```json
{
  "strategy_id": 1,
  "asset": "AAPL",
  "start_date": "2023-01-01",
  "end_date": "2023-01-31",
  "roi": 0.134,
  "sharpe": 1.23,
  "drawdown": 0.072,
  "trade_count": 27,
  "pnl_curve": [
    {"date": "2023-01-01", "balance": 10000},
    {"date": "2023-01-31", "balance": 11340}
  ]
}
```

---

## Paper Trading

### `POST /trades`
**Description:** Place a mock (paper) trade.

**Authentication:** Required

**Request Body:**
```json
{
  "asset": "ETHUSD",
  "side": "buy",
  "qty": 10.0,
  "price": 2520.0,
  "strategy_id": 1
}
```

**Response:** `PaperTrade` object

### `GET /trades`
**Description:** List all paper trades for the current user.

**Authentication:** Required

**Response:** List of `PaperTrade` objects

---

## Portfolio

### `GET /portfolio`
**Description:** Get the user's portfolio assets.

**Authentication:** Required

**Response:** List of `PortfolioEntry` objects

### `POST /portfolio`
**Description:** Add a new asset to the user's portfolio.

**Authentication:** Required

**Request Body:**
```json
{
  "asset": "AAPL",
  "quantity": 12.5,
  "cost_basis": 196.42
}
```

**Response:** `PortfolioEntry` object

---

## AI Assistant

### `POST /ai/assist`
**Description:** AI assistant for strategy recommendations or optimization.

**Authentication:** Required

**Request Body:**
```json
{
  "prompt": "How do I optimize ROI for a trend-following strategy?"
}
```

**Response:**
```json
{
  "result": "(AI mock) Based on your request: ... Consider a SMA(30)-MACD cross strategy for strong trends."
}
```

---

## Theme Preference

### `GET /user/theme`
**Description:** Get user's current theme preference.

**Authentication:** Required

**Response:**
```json
{
  "theme": "light"
}
```

### `POST /user/theme`
**Description:** Set light/dark theme preference.

**Authentication:** Required

**Request Body:**
```json
{
  "theme": "dark"
}
```

**Response:** Same structure as above

---

## Authentication Flow

Most endpoints (except `/`, `/auth/*`, `/health/db`, `/backtest/history`, `/integration/chart`) require an **Authorization** header:
```
Authorization: Bearer <access_token>
```
Tokens are obtained via `/auth/token` or `/auth/google`.

---

## Response Codes

- `200 OK`: Standard successful response
- `201 Created`: Resource created
- `400 Bad Request`: Validation or input error
- `401 Unauthorized`: Invalid or absent token
- `404 Not Found`: Resource not found
- `503 Service Unavailable`: Database/third-party failures

---

## Notes

- This backend supports (in future) WebSocket endpoints under `/ws/` for real-time features.
- Most data returned is demo/mocked; actual production deployments should replace mock implementations with live trading/data integrations.

---

**Contact the Quantico dev team for more details or for contributor support!**
