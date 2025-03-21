import logging
import os
from typing import Dict

import requests
from dotenv import load_dotenv

load_dotenv()


class ScrapeOps:
    """Class to handle ScrapeOps API interactions."""

    API_KEY = os.getenv("SCRAPEOPS_API_KEY")
    API_URL = "https://headers.scrapeops.io/v1/browser-headers"

    # Set up class-level logger
    logger = logging.getLogger(__name__)

    @classmethod
    def get_random_headers(cls, logger=None) -> Dict[str, str]:
        """Fetch random browser headers from ScrapeOps API.

        Args:
            logger: Logger instance from the calling class. If None, uses the class-level logger.

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
            (logger or cls.logger).info("[ScrapeOps] Successfully fetched random headers")
            return headers
        except Exception as e:
            (logger or cls.logger).error(f"[ScrapeOps] Failed to fetch headers: {e}")
            raise
