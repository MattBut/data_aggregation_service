import httpx
import asyncio
import time
from fastapi import FastAPI, HTTPException, status, Depends # 💡 Depends added
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader # 💡 New import
from typing import Dict, Any, List
import os

import uvicorn

# =================================================================
#                         CONFIGURATION
# =================================================================

# --- SECURITY ---
API_KEY_SECRET = os.getenv('CRYPTO_API_KEY') 
API_KEY_HEADER = "X-API-Key" 

# --- External APIs ---
BYBIT_API_BASE_URL = "https://api.bybit.com"

# Bybit Endpoints
TICKERS_ENDPOINT = "/v5/market/tickers"  # For current prices
KLINE_ENDPOINT = "/v5/market/kline"    # ENDPOINT for Candlestick data

COINGECKO_API_URL = "https://api.coingecko.com/api/v3/coins/markets"
COINGECKO_PARAMS = {
    'vs_currency': 'usd',  
    'per_page': 250,       
    'page': 1,
    'sparkline': False,
}

# --- CACHING Parameters ---
CACHE_DURATION_SECONDS = 300  
data_cache = {
    "last_updated": 0,       
    "data": {}               
}

# =================================================================
#                         FASTAPI SETUP
# =================================================================

app = FastAPI(
    title="Crypto Investment Data Aggregator",
    description="Aggregates CoinGecko and Bybit data with server-side caching and API Key protection.",
    version="2.1.0"
)

# --- CORS Configuration ---
origins = ["*"]  
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================================================================
#                       API KEY VALIDATION FUNCTION
# =================================================================

# Initialize security scheme for the header
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """
    Checks if the provided API key matches the secret key.
    Requires the 'X-API-Key' header to be present.
    """
    if api_key is None or api_key != API_KEY_SECRET:
        # 401 Unauthorized if the key is invalid or missing
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key in X-API-Key header",
            headers={"WWW-Authenticate": "x-api-key"},
        )
    return api_key

# =================================================================
#                       DATA FETCHING FUNCTIONS
# =================================================================

async def fetch_coingecko_data(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Fetches CoinGecko data (Market Cap, Rank, LOGO)"""
    try:
        response = await client.get(COINGECKO_API_URL, params=COINGECKO_PARAMS, timeout=10)
        response.raise_for_status()
        raw_data = response.json()
        
        # Convert list to dictionary for fast access by symbol (BTC, ETH)
        coingecko_map = {}
        for coin in raw_data:
            symbol = coin.get('symbol', '').upper()
            if symbol:
                coingecko_map[symbol] = {
                    "marketCapUSD": coin.get('market_cap'),
                    "marketCapRank": coin.get('market_cap_rank'),
                    "coinName": coin.get('name'),
                    "coinLogoURL": coin.get('image')
                }
        return coingecko_map
    except Exception as e:
        print(f"CoinGecko Error during fetch: {e.__class__.__name__}. Returning empty data.")
        return {}


async def fetch_bybit_spot_tickers(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Fetches current ticker data from Bybit (Price, Volume, % Change)"""
    url = BYBIT_API_BASE_URL + TICKERS_ENDPOINT
    params = {'category': 'spot'}
    
    try:
        response = await client.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('retCode') == 0:
            # Create Bybit dictionary (symbol: data)
            return {item['symbol']: item for item in data['result']['list']}
        else:
            print(f"Bybit API Error: {data.get('retMsg', 'Unknown API error')}")
            return {}
    except Exception as e:
        print(f"Bybit Network Error during fetch: {e.__class__.__name__}. Returning empty data.")
        return {}


async def fetch_bybit_klines(client: httpx.AsyncClient, symbol: str, interval: str, start_time: int = None, end_time: int = None, limit: int = 1000) -> List[List[str]]:
    """
    Fetches candlestick data (OHLCV) from Bybit.
    start_time and end_time must be in milliseconds.
    """
    url = BYBIT_API_BASE_URL + KLINE_ENDPOINT
    
    # Bybit API requires a category. Using 'spot'
    params = {
        'category': 'spot',
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    
    # Add optional parameters if they are provided
    if start_time:
        params['start'] = start_time
    if end_time:
        params['end'] = end_time

    try:
        response = await client.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('retCode') == 0 and data['result']['list']:
            # Bybit returns a list of lists [timestamp, open, high, low, close, volume, turnover]
            return data['result']['list']
        else:
            ret_msg = data.get('retMsg', 'Unknown API error')
            print(f"Bybit Kline API Error for {symbol}/{interval}: {ret_msg}")
            return []
            
    except httpx.HTTPStatusError as e:
        print(f"Bybit Kline HTTP Error for {symbol}/{interval}: {e.response.status_code}")
        return []
    except Exception as e:
        print(f"Bybit Kline Network Error for {symbol}/{interval}: {e.__class__.__name__}")
        return []


def aggregate_data(coingecko_data: Dict[str, Any], bybit_data: Dict[str, Any]) -> Dict[str, Any]:
    """Merges and filters data from both sources."""
    final_data = {}
    
    for symbol, bb_item in bybit_data.items():
        # Filter only USDT pairs for investment purposes
        if not symbol.endswith('USDT'):
            continue
            
        # Extract the base coin (e.g., 'BTCUSDT' -> 'BTC')
        base_coin = symbol.replace('USDT', '')
        cg_item = coingecko_data.get(base_coin)
        
        # Construct the final data structure
        final_data[symbol] = {
            "coinName": cg_item.get('coinName', base_coin) if cg_item else base_coin,
            "currentPrice": bb_item.get('lastPrice'),
            "priceChange24hPcnt": bb_item.get('price24hPcnt'),
            "volume24h": bb_item.get('volume24h'),
            "coinLogoURL": cg_item.get('coinLogoURL') if cg_item else None,
            # Long-term metrics from CoinGecko:
            "marketCapUSD": cg_item.get('marketCapUSD') if cg_item else None,
            "marketCapRank": cg_item.get('marketCapRank') if cg_item else None
        }
        
    return final_data

# =================================================================
#                       MAIN ENDPOINT (CACHING)
# =================================================================

@app.get(
    "/api/market/aggregated_data", 
    response_model=Dict[str, Any],
    summary="Get Cached Aggregated Investment Data",
    # 🛡️ Endpoint requires 'X-API-Key' header
    dependencies=[Depends(verify_api_key)] 
)
async def get_cached_aggregated_investment_data():
    global data_cache
    current_time = time.time()
    
    # 1. CACHE CHECK
    if (current_time - data_cache["last_updated"] < CACHE_DURATION_SECONDS) and data_cache["data"]:
        print(f"LOG: Serving data from cache. Last updated at {time.strftime('%H:%M:%S', time.localtime(data_cache['last_updated']))}")
        return data_cache["data"]
    
    # 2. DATA REFRESH
    print(f"LOG: Cache expired or empty. Refreshing data from external APIs...")
    
    async with httpx.AsyncClient() as client:
        # Run both requests in parallel
        coingecko_data, bybit_data = await asyncio.gather(
            fetch_coingecko_data(client),
            fetch_bybit_spot_tickers(client)
        )

    # 3. AGGREGATION
    final_data = aggregate_data(coingecko_data, bybit_data)

    # 4. CACHE STORAGE
    if final_data:
        data_cache["data"] = final_data
        data_cache["last_updated"] = current_time
        print(f"LOG: Cache successfully updated at {time.strftime('%H:%M:%S', time.localtime(current_time))}. Total coins: {len(final_data)}")
        return final_data
    else:
        # If refresh failed, but old data exists, it's better to return it
        if data_cache["data"]:
            print("LOG: Failed to refresh. Serving stale data from cache.")
            return data_cache["data"]
            
        # If neither new nor old data is available
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not fetch data from external APIs and cache is empty."
        )

# =================================================================
#                         NEW ENDPOINT: KLINES (CANDLESTICKS)
# =================================================================

@app.get(
    "/api/market/klines", 
    # Bybit returns List[List[str]], so we specify this as the model
    response_model=List[List[str]],
    summary="Get Candlestick Data (OHLCV) for a specific symbol",
    # 🛡️ Endpoint is protected by API key
    dependencies=[Depends(verify_api_key)] 
)
async def get_klines(
    symbol: str, 
    interval: str, 
    start_time: int = None, 
    end_time: int = None,
    limit: int = 1000 # Limit the maximum number of candles
):
    """
    Fetches historical candlestick data (OHLCV) from Bybit.
    
    :param symbol: Trading pair (e.g., BTCUSDT)
    :param interval: Candlestick interval (e.g., '1', '60', 'D' - 1 minute, 1 hour, 1 day)
    :param start_time: Start time in milliseconds (Unix timestamp * 1000)
    :param end_time: End time in milliseconds (Unix timestamp * 1000)
    :param limit: Maximum number of candles (up to 1000)
    :return: List of lists [timestamp, open, high, low, close, volume, turnover]
    """
    
    # Check for required parameters
    if not symbol or not interval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Symbol and interval are required query parameters."
        )

    async with httpx.AsyncClient() as client:
        klines = await fetch_bybit_klines(client, symbol, interval, start_time, end_time, limit)

    if not klines:
        # If the API returned an empty list, report a 404 error
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No kline data found for {symbol} at interval {interval}. Check symbol and interval validity."
        )
        
    return klines


#if __name__ == "__main__":
#    uvicorn.run("market_data_service:app", host="0.0.0.0", port=8000, reload=True)