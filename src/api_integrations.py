"""
API Integration Module for B5 Factor Trading System

This module provides API clients for Delta Exchange and Shoonya API.
Handles authentication, market data fetching, and order management.
"""

import hmac
import hashlib
import json
import time
import requests
import pytz
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from pathlib import Path


class DeltaExchangeClient:
    """
    Delta Exchange API client for BTC options and futures trading.
    
    Handles authentication using HMAC-SHA256 signatures and provides
    methods for market data fetching and order management.
    
    Requirements: 3.1, 3.2
    """
    
    BASE_URL = "https://api.delta.exchange"
    
    def __init__(self, credentials_path: str = "delta_cred.json"):
        """
        Initialize Delta Exchange client with credentials.
        
        Args:
            credentials_path: Path to JSON file containing api_key and api_secret
        """
        self.credentials_path = credentials_path
        self.api_key = None
        self.api_secret = None
        self._load_credentials()
    
    def _load_credentials(self) -> None:
        """
        Load API credentials from delta_cred.json file.
        
        Raises:
            FileNotFoundError: If credentials file doesn't exist
            KeyError: If required keys are missing from credentials file
            json.JSONDecodeError: If credentials file is not valid JSON
        """
        cred_file = Path(self.credentials_path)
        
        if not cred_file.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_path}"
            )
        
        with open(cred_file, 'r') as f:
            credentials = json.load(f)
        
        # Validate required keys
        if 'api_key' not in credentials:
            raise KeyError("Missing 'api_key' in credentials file")
        if 'api_secret' not in credentials:
            raise KeyError("Missing 'api_secret' in credentials file")
        
        self.api_key = credentials['api_key']
        self.api_secret = credentials['api_secret']
    
    def create_signature(
        self, 
        method: str, 
        endpoint: str, 
        timestamp: str,
        body: str = ""
    ) -> str:
        """
        Create HMAC-SHA256 signature for Delta Exchange API authentication.
        
        The signature is created by:
        1. Concatenating: method + timestamp + endpoint + body
        2. Creating HMAC-SHA256 hash using api_secret as key
        3. Converting to hexadecimal string
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., "/v2/tickers")
            timestamp: Unix timestamp in seconds as string
            body: Request body as string (empty for GET requests)
        
        Returns:
            HMAC-SHA256 signature as hexadecimal string
        
        Requirements: 3.1, 3.2
        Property 26: Authentication Signature Correctness
        """
        # Construct the message to sign
        message = method + timestamp + endpoint + body
        
        # Create HMAC-SHA256 signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def get_headers(
        self, 
        endpoint: str, 
        method: str = "GET",
        body: str = ""
    ) -> Dict[str, str]:
        """
        Generate authentication headers for Delta Exchange API requests.
        
        Headers include:
        - api-key: API key from credentials
        - timestamp: Current Unix timestamp in seconds
        - signature: HMAC-SHA256 signature
        - Content-Type: application/json
        
        Args:
            endpoint: API endpoint path (e.g., "/v2/tickers")
            method: HTTP method (GET, POST, PUT, DELETE)
            body: Request body as string (empty for GET requests)
        
        Returns:
            Dictionary of HTTP headers for authentication
        
        Requirements: 3.1, 3.2
        """
        # Generate timestamp (Unix time in seconds)
        timestamp = str(int(time.time()))
        
        # Create signature
        signature = self.create_signature(method, endpoint, timestamp, body)
        
        # Build headers
        headers = {
            'api-key': self.api_key,
            'timestamp': timestamp,
            'signature': signature,
            'Content-Type': 'application/json'
        }
        
        return headers
    
    def _api_call_with_retry(
        self,
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0
    ):
        """
        Execute API call with exponential backoff retry logic.
        
        Implements retry strategy for handling transient failures:
        - First retry: 1 second delay
        - Second retry: 2 seconds delay
        - Third retry: 4 seconds delay
        
        Args:
            func: Callable that makes the API request
            max_retries: Maximum number of retry attempts (default: 3)
            initial_delay: Initial delay in seconds (default: 1.0)
        
        Returns:
            Result from successful API call
        
        Raises:
            Exception: If all retry attempts fail
        
        Requirements: 3.11, 3.12, 30.2
        Property 24: Order Retry with Exponential Backoff
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return func()
            except requests.exceptions.HTTPError as e:
                last_exception = e
                
                # Check if it's a rate limit error (429)
                if e.response is not None and e.response.status_code == 429:
                    # Get retry-after header if available
                    retry_after = e.response.headers.get('Retry-After')
                    if retry_after:
                        delay = float(retry_after)
                    else:
                        delay = initial_delay * (2 ** attempt)
                    
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        continue
                
                # Check if it's an authentication error (401, 403)
                elif e.response is not None and e.response.status_code in [401, 403]:
                    # Don't retry authentication errors
                    raise
                
                # For other HTTP errors, use exponential backoff
                else:
                    if attempt < max_retries - 1:
                        delay = initial_delay * (2 ** attempt)
                        time.sleep(delay)
                        continue
                    
            except requests.exceptions.RequestException as e:
                # Network errors - retry with exponential backoff
                last_exception = e
                
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
        
        # All retries failed
        raise last_exception


    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time ticker data for a symbol.

        Args:
            symbol: Trading symbol (e.g., "BTCUSD")

        Returns:
            Dictionary containing ticker data with keys:
            - symbol: Trading symbol
            - mark_price: Current mark price
            - last_price: Last traded price
            - bid: Best bid price
            - ask: Best ask price
            - volume: 24h volume
            - timestamp: Data timestamp

        Requirements: 3.3, 3.11, 3.12
        """
        def _make_request():
            endpoint = f"/v2/tickers/{symbol}"
            headers = self.get_headers(endpoint, "GET")

            response = requests.get(
                f"{self.BASE_URL}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        
        return self._api_call_with_retry(_make_request)

    def get_candle_close(
        self,
        symbol: str,
        resolution: str,
        start: int,
        end: int
    ) -> list:
        """
        Fetch historical candle data for a symbol.

        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            resolution: Candle resolution ("1m", "5m", "15m", "1h", "1d")
            start: Start timestamp in seconds (Unix time)
            end: End timestamp in seconds (Unix time)

        Returns:
            List of candle dictionaries, each containing:
            - time: Candle timestamp
            - open: Open price
            - high: High price
            - low: Low price
            - close: Close price
            - volume: Volume

        Requirements: 3.4, 3.11, 3.12
        """
        def _make_request():
            endpoint = f"/v2/history/candles"
            params = {
                'symbol': symbol,
                'resolution': resolution,
                'start': start,
                'end': end
            }

            # Build query string for signature
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            endpoint_with_params = f"{endpoint}?{query_string}"

            headers = self.get_headers(endpoint_with_params, "GET")

            response = requests.get(
                f"{self.BASE_URL}{endpoint}",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
        
        return self._api_call_with_retry(_make_request)

    def get_products(self) -> list:
        """
        Fetch available trading products/instruments.

        Returns:
            List of product dictionaries, each containing:
            - symbol: Product symbol
            - description: Product description
            - contract_type: Type of contract (futures, options, etc.)
            - strike_price: Strike price (for options)
            - expiry: Expiry timestamp
            - underlying_asset: Underlying asset symbol

        Requirements: 3.5, 3.11, 3.12
        """
        def _make_request():
            endpoint = "/v2/products"
            headers = self.get_headers(endpoint, "GET")

            response = requests.get(
                f"{self.BASE_URL}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        
        return self._api_call_with_retry(_make_request)

    def get_first_candle_close(
        self,
        symbol: str,
        resolution: str,
        time_ist: str
    ) -> Optional[float]:
        """
        Get the close price of the first candle at a specific IST time.

        This method is used to fetch the first candle close at 5:30 AM IST
        for BTC trading, which serves as the Base_Price for level calculations.

        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            resolution: Candle resolution ("1m", "5m", "15m")
            time_ist: Time in IST format "HH:MM" (e.g., "05:30")

        Returns:
            Close price of the first candle at specified time, or None if not found

        Requirements: 3.6, 3.7, 3.8
        """
        from datetime import datetime, timedelta
        import pytz

        # Parse IST time
        ist_tz = pytz.timezone('Asia/Kolkata')
        today = datetime.now(ist_tz).date()

        # Parse time string
        hour, minute = map(int, time_ist.split(':'))
        target_time_ist = ist_tz.localize(
            datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
        )

        # Convert IST to UTC
        target_time_utc = target_time_ist.astimezone(pytz.UTC)

        # Calculate start and end timestamps
        # Fetch a window around the target time to ensure we get the candle
        start_timestamp = int(target_time_utc.timestamp()) - 300  # 5 minutes before
        end_timestamp = int(target_time_utc.timestamp()) + 300    # 5 minutes after

        # Fetch candles
        candles = self.get_candle_close(
            symbol=symbol,
            resolution=resolution,
            start=start_timestamp,
            end=end_timestamp
        )

        # Find the candle closest to target time
        if not candles or 'result' not in candles:
            return None

        candle_data = candles['result']
        if not candle_data:
            return None

        # Find candle at or closest to target time
        target_ts = int(target_time_utc.timestamp())

        # Sort candles by time
        sorted_candles = sorted(candle_data, key=lambda x: abs(x['time'] - target_ts))

        if sorted_candles:
            return sorted_candles[0]['close']

        return None
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Place an order on Delta Exchange.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            side: Order side ("buy" or "sell")
            quantity: Order quantity/size
            order_type: Order type ("market_order" or "limit_order")
            price: Limit price (required for limit orders, ignored for market orders)
        
        Returns:
            Dictionary containing order details:
            - id: Order ID
            - symbol: Trading symbol
            - side: Order side
            - size: Order size
            - order_type: Order type
            - limit_price: Limit price (for limit orders)
            - state: Order state
            - created_at: Order creation timestamp
        
        Raises:
            ValueError: If order_type is limit_order but price is not provided
            requests.HTTPError: If API request fails
        
        Requirements: 3.9, 3.11, 3.12
        """
        # Validate inputs
        if order_type == "limit_order" and price is None:
            raise ValueError("Price is required for limit orders")
        
        def _make_request():
            endpoint = "/v2/orders"
            
            # Build order payload
            order_payload = {
                "product_symbol": symbol,
                "side": side,
                "size": quantity,
                "order_type": order_type
            }
            
            # Add limit price if provided
            if price is not None:
                order_payload["limit_price"] = str(price)
            
            # Convert payload to JSON string for signature
            body = json.dumps(order_payload)
            
            # Get headers with signature
            headers = self.get_headers(endpoint, "POST", body)
            
            # Make API request
            response = requests.post(
                f"{self.BASE_URL}{endpoint}",
                headers=headers,
                data=body
            )
            response.raise_for_status()
            return response.json()
        
        return self._api_call_with_retry(_make_request)
    
    def get_positions(self) -> list:
        """
        Fetch current open positions from Delta Exchange.
        
        Returns:
            List of position dictionaries, each containing:
            - product_symbol: Trading symbol
            - size: Position size (positive for long, negative for short)
            - entry_price: Average entry price
            - margin: Margin used
            - liquidation_price: Liquidation price
            - unrealized_pnl: Unrealized profit/loss
            - realized_pnl: Realized profit/loss
        
        Requirements: 3.10, 3.11, 3.12
        """
        def _make_request():
            endpoint = "/v2/positions"
            headers = self.get_headers(endpoint, "GET")
            
            response = requests.get(
                f"{self.BASE_URL}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        
        return self._api_call_with_retry(_make_request)
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an existing order on Delta Exchange.
        
        Args:
            order_id: ID of the order to cancel
        
        Returns:
            Dictionary containing cancellation confirmation:
            - id: Order ID
            - state: Order state (should be "cancelled")
            - cancelled_at: Cancellation timestamp
        
        Raises:
            requests.HTTPError: If API request fails or order cannot be cancelled
        
        Requirements: 3.10, 3.11, 3.12
        """
        def _make_request():
            endpoint = f"/v2/orders/{order_id}"
            headers = self.get_headers(endpoint, "DELETE")
            
            response = requests.delete(
                f"{self.BASE_URL}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        
        return self._api_call_with_retry(_make_request)
    
    def modify_order(
        self,
        order_id: str,
        new_price: float
    ) -> Dict[str, Any]:
        """
        Modify the price of an existing limit order.
        
        Args:
            order_id: ID of the order to modify
            new_price: New limit price for the order
        
        Returns:
            Dictionary containing modified order details:
            - id: Order ID
            - limit_price: New limit price
            - state: Order state
            - updated_at: Update timestamp
        
        Raises:
            requests.HTTPError: If API request fails or order cannot be modified
        
        Requirements: 3.10, 3.11, 3.12
        """
        def _make_request():
            endpoint = f"/v2/orders/{order_id}"
            
            # Build modification payload
            modify_payload = {
                "limit_price": str(new_price)
            }
            
            # Convert payload to JSON string for signature
            body = json.dumps(modify_payload)
            
            # Get headers with signature
            headers = self.get_headers(endpoint, "PUT", body)
            
            # Make API request
            response = requests.put(
                f"{self.BASE_URL}{endpoint}",
                headers=headers,
                data=body
            )
            response.raise_for_status()
            return response.json()
        
        return self._api_call_with_retry(_make_request)


    def _api_call_with_retry(
        self,
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0
    ):
        """
        Execute API call with exponential backoff retry logic.

        Implements retry strategy for handling transient failures:
        - First retry: 1 second delay
        - Second retry: 2 seconds delay
        - Third retry: 4 seconds delay

        Args:
            func: Callable that makes the API request
            max_retries: Maximum number of retry attempts (default: 3)
            initial_delay: Initial delay in seconds (default: 1.0)

        Returns:
            Result from successful API call

        Raises:
            Exception: If all retry attempts fail

        Requirements: 3.11, 3.12, 30.2
        Property 24: Order Retry with Exponential Backoff
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return func()
            except requests.exceptions.HTTPError as e:
                last_exception = e

                # Check if it's a rate limit error (429)
                if e.response is not None and e.response.status_code == 429:
                    # Get retry-after header if available
                    retry_after = e.response.headers.get('Retry-After')
                    if retry_after:
                        delay = float(retry_after)
                    else:
                        delay = initial_delay * (2 ** attempt)

                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        continue

                # Check if it's an authentication error (401, 403)
                elif e.response is not None and e.response.status_code in [401, 403]:
                    # Don't retry authentication errors
                    raise

                # For other HTTP errors, use exponential backoff
                else:
                    if attempt < max_retries - 1:
                        delay = initial_delay * (2 ** attempt)
                        time.sleep(delay)
                        continue

            except requests.exceptions.RequestException as e:
                # Network errors - retry with exponential backoff
                last_exception = e

                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue

        # All retries failed
        raise last_exception



class ShoonyaClient:
    """
    Client for Shoonya (Finvasia) API integration.
    Handles authentication, market data, and order management for NSE/BSE/MCX.
    """

    def __init__(self, credentials_path: str = "shoonya_cred.json"):
        """
        Initialize Shoonya client.

        Args:
            credentials_path: Path to credentials JSON file
        """
        self.credentials_path = credentials_path
        self.base_url = "https://api.shoonya.com/NorenWClientTP"
        self.userid = None
        self.password = None
        self.totp_secret = None
        self.vendor_code = None
        self.api_secret = None
        self.imei = None
        self.session_token = None
        self._load_credentials()

    def _load_credentials(self) -> None:
        """
        Load credentials from JSON file.

        Raises:
            FileNotFoundError: If credentials file not found
            ValueError: If required fields missing
        """
        try:
            with open(self.credentials_path, 'r') as f:
                creds = json.load(f)

            required_fields = ['userid', 'password', 'totp_secret', 'vendor_code', 'api_secret', 'imei']
            missing_fields = [field for field in required_fields if field not in creds]

            if missing_fields:
                raise ValueError(f"Missing required fields in credentials: {', '.join(missing_fields)}")

            self.userid = creds['userid']
            self.password = creds['password']
            self.totp_secret = creds['totp_secret']
            self.vendor_code = creds['vendor_code']
            self.api_secret = creds['api_secret']
            self.imei = creds['imei']

        except FileNotFoundError:
            raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in credentials file: {self.credentials_path}")

    def _generate_totp(self) -> str:
        """
        Generate TOTP token using totp_secret.

        Returns:
            6-digit TOTP token
        """
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        return totp.now()

    def login(self) -> Dict[str, Any]:
        """
        Authenticate with Shoonya API using userid, password, and TOTP.

        Returns:
            Response containing session token

        Raises:
            Exception: If authentication fails
        """
        totp_token = self._generate_totp()

        # Create SHA256 hash of password
        password_hash = hashlib.sha256(self.password.encode()).hexdigest()

        payload = {
            'source': 'API',
            'apkversion': 'js:1.0.0',
            'uid': self.userid,
            'pwd': password_hash,
            'factor2': totp_token,
            'vc': self.vendor_code,
            'appkey': hashlib.sha256((self.userid + self.api_secret).encode()).hexdigest(),
            'imei': self.imei
        }

        response = self._api_call_with_retry(
            method='POST',
            endpoint='/QuickAuth',
            data=payload,
            requires_auth=False
        )

        if response.get('stat') == 'Ok':
            self.session_token = response.get('susertoken')
            return response
        else:
            raise Exception(f"Shoonya login failed: {response.get('emsg', 'Unknown error')}")

    def _api_call_with_retry(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        requires_auth: bool = True,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make API call with exponential backoff retry logic.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            data: Request payload
            requires_auth: Whether authentication token is required
            max_retries: Maximum number of retry attempts

        Returns:
            API response as dictionary

        Raises:
            Exception: If all retries fail
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(max_retries):
            try:
                # Add session token if authentication required
                if requires_auth:
                    if not self.session_token:
                        raise Exception("Not authenticated. Call login() first.")
                    if data is None:
                        data = {}
                    data['jData'] = json.dumps({'uid': self.userid, 'actid': self.userid})
                    data['jKey'] = self.session_token

                if method == 'POST':
                    response = requests.post(url, data=data, timeout=10)
                else:
                    response = requests.get(url, params=data, timeout=10)

                response.raise_for_status()

                # Shoonya returns JSON or text
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {'result': response.text}

            except requests.exceptions.HTTPError as e:
                # Don't retry authentication errors (401, 403)
                if e.response.status_code in [401, 403]:
                    raise Exception(f"Authentication error: {e}")

                # Handle rate limiting (429)
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get('Retry-After', 5))
                    if attempt < max_retries - 1:
                        time.sleep(retry_after)
                        continue
                    raise Exception(f"Rate limit exceeded: {e}")

                # Retry on server errors (500+)
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    time.sleep(delay)
                    continue
                raise Exception(f"HTTP error after {max_retries} attempts: {e}")

            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.RequestException) as e:
                # Retry on network errors
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    time.sleep(delay)
                    continue
                raise Exception(f"Network error after {max_retries} attempts: {e}")

        raise Exception(f"API call failed after {max_retries} attempts")

    def get_quotes(self, exchange: str, symbol: str) -> Dict[str, Any]:
        """
        Get real-time quotes for a symbol.

        Args:
            exchange: Exchange code (NSE, BSE, MCX, etc.)
            symbol: Trading symbol

        Returns:
            Quote data including LTP, bid, ask, volume
        """
        payload = {
            'uid': self.userid,
            'exch': exchange,
            'token': symbol
        }

        return self._api_call_with_retry(
            method='POST',
            endpoint='/GetQuotes',
            data=payload,
            requires_auth=True
        )

    def get_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> list:
        """
        Get historical candle data.

        Args:
            exchange: Exchange code (NSE, BSE, MCX)
            symbol: Trading symbol
            timeframe: Timeframe (1, 5, 15, 60, etc. in minutes)
            start_time: Start time in format 'DD-MM-YYYY HH:MM:SS'
            end_time: End time in format 'DD-MM-YYYY HH:MM:SS'

        Returns:
            List of candles with OHLCV data
        """
        payload = {
            'uid': self.userid,
            'exch': exchange,
            'token': symbol,
            'st': start_time or '',
            'et': end_time or '',
            'intrv': timeframe
        }

        response = self._api_call_with_retry(
            method='POST',
            endpoint='/TPSeries',
            data=payload,
            requires_auth=True
        )

        return response if isinstance(response, list) else []

    def get_first_candle_close(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        time_ist: str = "09:15"
    ) -> Optional[float]:
        """
        Get the close price of the first candle at specified time (IST).
        For NSE/BSE, default is 9:15 AM IST.

        Args:
            exchange: Exchange code
            symbol: Trading symbol
            timeframe: Timeframe in minutes
            time_ist: Time in IST format 'HH:MM'

        Returns:
            Close price of first candle, or None if not found
        """
        from datetime import datetime, timedelta
        import pytz

        # Get current date in IST
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)

        # Parse target time
        hour, minute = map(int, time_ist.split(':'))
        target_time = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Format times for API
        start_time = target_time.strftime('%d-%m-%Y %H:%M:%S')
        end_time = (target_time + timedelta(minutes=int(timeframe))).strftime('%d-%m-%Y %H:%M:%S')

        candles = self.get_candles(exchange, symbol, timeframe, start_time, end_time)

        if candles and len(candles) > 0:
            # Shoonya returns candles as list of dicts
            first_candle = candles[0]
            return float(first_candle.get('intc', 0))  # 'intc' is close price

        return None

    def place_order(
        self,
        exchange: str,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MKT",
        price: Optional[float] = None,
        product_type: str = "I"  # I=Intraday, C=Delivery
    ) -> Dict[str, Any]:
        """
        Place an order.

        Args:
            exchange: Exchange code (NSE, BSE, MCX)
            symbol: Trading symbol
            side: 'buy' or 'sell'
            quantity: Order quantity
            order_type: 'MKT' for market, 'LMT' for limit
            price: Limit price (required for limit orders)
            product_type: 'I' for intraday, 'C' for delivery

        Returns:
            Order response with order_id

        Raises:
            ValueError: If limit order without price
        """
        if order_type == "LMT" and price is None:
            raise ValueError("Price is required for limit orders")

        # Convert side to Shoonya format
        trantype = 'B' if side.lower() == 'buy' else 'S'

        payload = {
            'uid': self.userid,
            'actid': self.userid,
            'exch': exchange,
            'tsym': symbol,
            'qty': str(quantity),
            'prc': str(price) if price else '0',
            'prd': product_type,
            'trantype': trantype,
            'prctyp': order_type,
            'ret': 'DAY'
        }

        return self._api_call_with_retry(
            method='POST',
            endpoint='/PlaceOrder',
            data=payload,
            requires_auth=True
        )

    def get_positions(self, exchange: Optional[str] = None) -> list:
        """
        Get current positions.

        Args:
            exchange: Optional exchange filter

        Returns:
            List of positions
        """
        payload = {
            'uid': self.userid,
            'actid': self.userid
        }

        response = self._api_call_with_retry(
            method='POST',
            endpoint='/PositionBook',
            data=payload,
            requires_auth=True
        )

        positions = response if isinstance(response, list) else []

        # Filter by exchange if specified
        if exchange and positions:
            positions = [p for p in positions if p.get('exch') == exchange]

        return positions

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        payload = {
            'uid': self.userid,
            'norenordno': order_id
        }

        return self._api_call_with_retry(
            method='POST',
            endpoint='/CancelOrder',
            data=payload,
            requires_auth=True
        )

