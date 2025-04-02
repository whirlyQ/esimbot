import os
import aiohttp
import logging
import certifi
import ssl
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

logger = logging.getLogger(__name__)

class AiraloAPI:
    def __init__(self):
        self.api_key = os.getenv('AIRALO_API_KEY')
        if not self.api_key:
            raise ValueError("AIRALO_API_KEY not found in environment variables")
            
        self.base_url = "https://partners-api.airalo.com/v2"
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        self.usage_cache = {}  # Cache for usage data
        logger.info(f"Initialized AiraloAPI with base_url: {self.base_url}")

    async def _handle_response(self, response, iccid: str):
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
            error_msg = f"Invalid ICCID: {iccid}. This eSIM is not available on our platform."
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

        url = f"{self.base_url}/sims/{iccid}/topups"
        logger.info(f"Fetching top-up packages for ICCID: {iccid}")
        logger.info(f"Request URL: {url}")

        # Create SSL context using certifi's certificate bundle
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.check_hostname = True

        timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds timeout

        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url, headers=self.headers, ssl=ssl_context) as response:
                    return await self._handle_response(response, iccid)
            except ssl.SSLError as e:
                error_msg = f"SSL Certificate Error: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            except aiohttp.ClientError as e:
                error_msg = f"Network error: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)

    async def get_usage(self, iccid: str):
        """Get eSIM usage data with caching."""
        if not iccid:
            raise ValueError("ICCID cannot be empty")

        # Check cache first
        cache_key = f"{iccid}_{datetime.now().strftime('%Y%m%d%H%M')}"
        if cache_key in self.usage_cache:
            return self.usage_cache[cache_key]

        url = f"{self.base_url}/sims/{iccid}/usage"
        logger.info(f"Fetching usage data for ICCID: {iccid}")
        logger.info(f"Request URL: {url}")

        # Create SSL context using certifi's certificate bundle
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.check_hostname = True

        timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds timeout

        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url, headers=self.headers, ssl=ssl_context) as response:
                    data = await self._handle_response(response, iccid)
                    # Cache the response
                    self.usage_cache[cache_key] = data
                    return data
            except ssl.SSLError as e:
                error_msg = f"SSL Certificate Error: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            except aiohttp.ClientError as e:
                error_msg = f"Network error: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg) 