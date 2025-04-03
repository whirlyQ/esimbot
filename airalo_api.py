import os
import aiohttp
import logging
import certifi
import ssl
import time
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

logger = logging.getLogger(__name__)

class AiraloAPI:
    def __init__(self):
        self.client_id = os.getenv('AIRALO_CLIENT_ID')
        self.client_secret = os.getenv('AIRALO_CLIENT_SECRET')
        if not self.client_id or not self.client_secret:
            raise ValueError("AIRALO_CLIENT_ID and AIRALO_CLIENT_SECRET must be set in environment variables")
            
        self.base_url = "https://partners-api.airalo.com/v2"
        self.token = None
        self.token_expiry = 0
        self.usage_cache = {}  # Cache for usage data
        logger.info(f"Initialized AiraloAPI with base_url: {self.base_url}")

    async def _get_token(self):
        """Get or refresh the access token."""
        current_time = time.time()
        
        # If we have a valid token, return it
        if self.token and current_time < self.token_expiry:
            return self.token

        # Request new token
        url = f"{self.base_url}/token"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        headers = {
            'Accept': 'application/json'
        }

        # Create SSL context using certifi's certificate bundle
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.check_hostname = True

        timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds timeout

        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(url, data=data, headers=headers, ssl=ssl_context) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        self.token = response_data['data']['access_token']
                        # Set expiry to 23 hours to be safe (token is valid for 24 hours)
                        self.token_expiry = current_time + (23 * 60 * 60)
                        logger.info("Successfully obtained new access token")
                        return self.token
                    else:
                        error_msg = f"Failed to get access token: {response.status}"
                        logger.error(error_msg)
                        raise Exception(error_msg)
            except Exception as e:
                error_msg = f"Error getting access token: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)

    async def _make_request(self, method, endpoint, **kwargs):
        """Make an authenticated request to the API."""
        # Get or refresh token
        token = await self._get_token()
        
        # Add authorization header
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {token}'
        headers['Accept'] = 'application/json'
        kwargs['headers'] = headers

        # Create SSL context using certifi's certificate bundle
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.check_hostname = True
        kwargs['ssl'] = ssl_context

        # Add timeout
        kwargs['timeout'] = aiohttp.ClientTimeout(total=30)

        url = f"{self.base_url}/{endpoint}"
        logger.info(f"Making {method} request to {url}")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(method, url, **kwargs) as response:
                    return await self._handle_response(response)
            except Exception as e:
                error_msg = f"API request failed: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)

    async def _handle_response(self, response):
        """Handle API response and extract error messages."""
        response_text = await response.text()
        logger.info(f"Response status: {response.status}")
        logger.info(f"Response body: {response_text}")

        try:
            response_data = await response.json()
        except:
            response_data = {}

        if response.status == 200:
            return response_data
        elif response.status in [401, 403, 404]:
            # Standardize error message for any case where we can't access the ICCID
            error_msg = "Invalid ICCID. This eSIM is not available on our platform."
            logger.error(error_msg)
            raise Exception(error_msg)
        elif response.status == 429:
            retry_after = response.headers.get('Retry-After', '900')  # Default to 15 minutes
            error_msg = f"Rate limit exceeded. Please try again in {retry_after} seconds."
            if 'message' in response_data:
                error_msg = f"{response_data['message']} Please try again in {retry_after} seconds."
            logger.error(error_msg)
            raise Exception(error_msg)
        else:
            error_msg = f"API Error: {response.status}"
            if 'message' in response_data:
                error_msg = f"{error_msg} - {response_data['message']}"
            elif 'meta' in response_data and 'message' in response_data['meta']:
                error_msg = f"{error_msg} - {response_data['meta']['message']}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def get_topup_packages(self, iccid: str):
        """Get available top-up packages for an eSIM."""
        if not iccid:
            raise ValueError("ICCID cannot be empty")

        return await self._make_request('GET', f"sims/{iccid}/topups")

    async def get_usage(self, iccid: str):
        """Get eSIM usage data with caching."""
        if not iccid:
            raise ValueError("ICCID cannot be empty")

        # Check cache first
        cache_key = f"{iccid}_{datetime.now().strftime('%Y%m%d%H%M')}"
        if cache_key in self.usage_cache:
            return self.usage_cache[cache_key]

        data = await self._make_request('GET', f"sims/{iccid}/usage")
        
        # Cache the response
        self.usage_cache[cache_key] = data
        return data 