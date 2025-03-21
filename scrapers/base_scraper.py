from datetime import datetime
from typing import Dict, Optional

from selenium import webdriver
from selenium.common.exceptions import WebDriverException

from scrapers.utils.logging_config import setup_logging
from scrapers.utils.scrapeops import ScrapeOps


class BaseScraper:
    """Base class for all web scrapers."""

    def __init__(self, headless: bool = False, log_file: str = "base_scraper"):
        """Initialize the base scraper with common browser options.

        Args:
            headless (bool): Whether to run the browser in headless mode
            log_file (str): Name of the log file (without extension)
        """
        self.logger = setup_logging(log_file)
        self.options = webdriver.ChromeOptions()

        if headless:
            self.options.add_argument("--headless=new")
            self.options.add_argument("--disable-gpu")
        else:
            self.options.add_argument("--start-maximized")

        self.set_random_headers()

        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option("useAutomationExtension", False)
        self.options.add_argument("--disable-infobars")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-notifications")
        self.options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.images": 1,
            "profile.default_content_setting_values.cookies": 1,
            "profile.default_content_settings.popups": 0,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        self.options.add_experimental_option("prefs", prefs)

        self.driver_logs = None
        self.driver: Optional[webdriver.Chrome] = None
        self.start_time: Optional[datetime] = None

    def get_random_headers(self) -> Dict[str, str]:
        """Get random headers from ScrapeOps.

        Returns:
            Dict[str, str]: Dictionary containing browser headers
        """
        return ScrapeOps.get_random_headers(logger=self.logger)

    def set_headers(self, headers: Dict[str, str]) -> None:
        """Apply headers to web driver options.

        Args:
            headers (Dict[str, str]): Dictionary containing browser headers
        """
        self.logger.info("Successfully fetched headers from ScrapeOps")

        header_mappings = {
            "user-agent": ("--user-agent", headers["user-agent"]),
            "accept-language": ("--accept-lang", headers["accept-language"]),
            "accept": ("--accept", headers["accept"]),
            "sec-ch-ua": ("--sec-ch-ua", headers["sec-ch-ua"]),
            "sec-ch-ua-mobile": ("--sec-ch-ua-mobile", headers["sec-ch-ua-mobile"]),
            "sec-ch-ua-platform": ("--sec-ch-ua-platform", headers["sec-ch-ua-platform"]),
            "sec-fetch-dest": ("--sec-fetch-dest", headers["sec-fetch-dest"]),
            "sec-fetch-mode": ("--sec-fetch-mode", headers["sec-fetch-mode"]),
            "sec-fetch-site": ("--sec-fetch-site", headers["sec-fetch-site"]),
            "sec-fetch-user": ("--sec-fetch-user", headers["sec-fetch-user"]),
        }

        for header_key, (arg_name, value) in header_mappings.items():
            try:
                self.options.add_argument(f"{arg_name}={value}")
                self.logger.debug(f"Applied header {header_key}: {value}")
            except Exception as e:
                self.logger.warning(f"Failed to apply header {header_key}: {e}")

        self.logger.info("Applied random headers to web driver options")

    def set_random_headers(self) -> None:
        """Set random headers to web driver options."""
        self.set_headers(self.get_random_headers())

    def setup_driver(self) -> None:
        """Initialize the web driver."""
        try:
            self.driver = webdriver.Chrome(options=self.options)
            self.logger.info("Web driver initialized successfully")
        except WebDriverException as e:
            self.logger.error(f"Failed to initialize web driver: {e}")
            raise

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.driver:
            self.driver.quit()
            self.logger.info("Web driver closed")

    def save_results(self) -> None:
        """Save the results to a file."""
        raise NotImplementedError("Subclasses must implement save_results()")

    def save_partial_results(self) -> None:
        """Save the partial results to a file."""
        raise NotImplementedError("Subclasses must implement save_partial_results()")

    def run(self) -> None:
        """Run the complete scraping process."""
        self.start_time = datetime.now()
        try:
            self.setup_driver()
            self.scrape()
            self.save_results()
        except (Exception, KeyboardInterrupt) as e:
            self.logger.error(f"An error occurred during scraping: {e}")
            self.logger.info("Attempting to save partial results...")
            self.save_partial_results()
            if not isinstance(e, KeyboardInterrupt):
                raise
        finally:
            self.cleanup()
            duration = datetime.now() - self.start_time
            self.logger.info(f"Scraping process finished in {duration}")

    def scrape(self) -> None:
        """Main scraping method to be implemented by child classes."""
        raise NotImplementedError("Subclasses must implement scrape()")
