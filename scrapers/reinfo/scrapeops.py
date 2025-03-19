import logging
import os
from typing import Dict

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ScrapeOps:
    """Class to handle ScrapeOps API interactions."""

    API_KEY = os.getenv("SCRAPEOPS_API_KEY")
    API_URL = "https://headers.scrapeops.io/v1/browser-headers"

    @classmethod
    def get_random_headers(cls) -> Dict[str, str]:
        """Fetch random browser headers from ScrapeOps API.

        Returns:
            Dict[str, str]: Dictionary containing browser headers
        """
        try:
            response = requests.get(
                url=cls.API_URL,
                params={"api_key": cls.API_KEY, "num_results": "1"},
            )
            response.raise_for_status()
            headers = response.json()["result"][0]
            logger.info("Successfully fetched random headers from ScrapeOps")
            return headers
        except Exception as e:
            logger.error(f"Failed to fetch headers from ScrapeOps: {e}")
            raise
