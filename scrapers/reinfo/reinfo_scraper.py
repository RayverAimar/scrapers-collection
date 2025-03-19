import logging
import os
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait

from scrapers.reinfo.enum_types import (
    DropdownType,
    FormaType,
    ListadoType,
    OrdenadoType,
    PersonaType,
)
from scrapers.reinfo.scrapeops import ScrapeOps

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/reinfo_scraper.log", mode="w"),
        logging.StreamHandler(),
    ],  # we can change to append mode if we want to keep the log historical file
)
logger = logging.getLogger(__name__)


class ReinfoScraper:
    """Class to scrape information from REINFO website."""

    def __init__(self, headless: bool = False):
        """Initialize the scraper with browser options.

        Args:
            headless (bool): Whether to run the browser in headless mode
        """
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

        self.driver = None
        self.data: List[List[str]] = []
        self.start_time = None

    def get_random_headers(self) -> Dict[str, str]:
        """Get random headers from ScrapeOps."""
        return ScrapeOps.get_random_headers()

    def set_headers(self, headers: Dict[str, str]) -> None:
        """Apply headers to web driver options."""
        logger.info("Successfully fetched headers from ScrapeOps")

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
                logger.debug(f"Applied header {header_key}: {value}")
            except Exception as e:
                logger.warning(f"Failed to apply header {header_key}: {e}")

        logger.info("Applied random headers to web driver options")

    def set_random_headers(self) -> None:
        """Set random headers to web driver options."""
        self.set_headers(self.get_random_headers())

    def setup_driver(self) -> None:
        """Initialize the web driver."""
        try:
            self.driver = webdriver.Chrome(options=self.options)
            logger.info("Web driver initialized successfully")
        except WebDriverException as e:
            logger.error(f"Failed to initialize web driver: {e}")
            raise

    def navigate_to_page(self) -> None:
        """Navigate to the REINFO website and set up initial search."""
        try:
            self.driver.get("https://pad.minem.gob.pe/REINFO_WEB/Index.aspx")

            logger.info("Waiting for page to load...")
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.ID, "ddllistado")))
            wait.until(EC.visibility_of_element_located((By.ID, "ddllistado")))
            logger.info("Page loaded successfully")

            logger.info("Setting search filters...")
            self.set_search_filters()

            logger.info("Searching for results...")
            self.driver.find_element(By.ID, "btnBuscar").click()
            logger.info("Successfully navigated to search results")

            wait.until(EC.presence_of_element_located((By.ID, "lblhasta")))
            self.total_pages = self.driver.find_element(By.ID, "lblhasta").text
            # we can create a periodic task out of this to check to see if the total pages have
            # changed so we run the scraper to fetch fresh data
        except (WebDriverException, TimeoutException) as e:
            logger.error(f"Failed to navigate to page: {e}")
            raise

    def set_dropdown_filter(self, dropdown_type: DropdownType, choice: Enum) -> None:
        """
        Set the dropdown filter using enums for type safety.

        Args:
            dropdown_type (DropdownType): The type of dropdown to set
            choice (Enum): The choice to select from the dropdown's options
        """
        try:
            wait = WebDriverWait(self.driver, 10)
            select_element = wait.until(EC.presence_of_element_located((By.ID, dropdown_type.element_id)))
            wait.until(EC.element_to_be_clickable((By.ID, dropdown_type.element_id)))

            select = Select(select_element)
            select.select_by_visible_text(choice.value)
            time.sleep(1)  # Give the page time to update after selection
        except (WebDriverException, TimeoutException) as e:
            logger.error(f"Failed to set dropdown filter: {e}")
            raise

    def set_search_filters(self) -> None:
        """
        Set the search filters using enums.

        We can set our custom filters here by using the enum types provided in the `enum_types.py` file.
        """
        self.set_dropdown_filter(DropdownType.LISTADO, ListadoType.TODOS)
        logger.info(f"Listado filter [{ListadoType.TODOS.value}] set")

        self.set_dropdown_filter(DropdownType.TIPO_PERSONA, PersonaType.TODOS)
        logger.info(f"Tipo persona filter [{PersonaType.TODOS.value}] set")

        self.set_dropdown_filter(DropdownType.ORDENADO, OrdenadoType.RUC)
        logger.info(f"Ordenado filter [{OrdenadoType.RUC.value}] set")

        self.set_dropdown_filter(DropdownType.FORMA, FormaType.ASC)
        logger.info(f"Forma filter [{FormaType.ASC.value}] set")

        # We can set more filters here if we want to (like departamento, provincia, distrito, etc.),
        # but for now we will just use the default ones

    def set_ruc_filter(self, ruc: str) -> None:
        """
        Set the RUC filter.

        - We currently don't use the RUC filter, but it's here if we need it so we can add it to the search.
        - Take into consideration that the RUC filter will need to have enabled all parameters and will only return one
          row, so we will need to make sure we address this case in the code if we decide to use it.
        """

        self.driver.find_element(By.ID, "txtruc").send_keys(ruc)

    def extract_row_data(self, row) -> List[str]:
        """Extract data from a single row.

        Args:
            row: WebElement representing a table row

        Returns:
            List[str]: List of cell values from the row
        """
        cols = row.find_elements(By.CSS_SELECTOR, "td")[1:]
        return [data.text for data in cols]

    def process_current_page(self) -> None:
        """Process the current page of results."""
        table = self.driver.find_element(By.CSS_SELECTOR, "table.gvRow")
        rows = table.find_elements(By.CSS_SELECTOR, "tr")[3:]

        for row in rows:
            row_data = self.extract_row_data(row)
            self.data.append(row_data)
            logger.debug(f"Processed row: {row_data}")

    def has_next_page(self) -> bool:
        """Check if there is a next page of results.

        Returns:
            bool: True if next page exists, False otherwise
        """
        next_button = self.driver.find_element(By.ID, "ImgBtnSiguiente")
        return next_button.get_attribute("disabled") is None

    def scrape_all_pages(self) -> None:
        """Scrape all available pages of results."""
        page_count = 1
        # We manually count the pages even though we can get it from the total_pages variable because we don't want to
        # request for a number we know is incrementing by one in each iteration
        while (
            self.has_next_page()
        ):  # You could also change headers every random-ranged number of pages (e.g. random between 5 and 10 visited
            # pages) to avoid detection if you want to. The downside is that we will need to reinitialize the driver
            # and navigate to the page again requesting same pages again :/
            # This website does not allow us to change web driver headers as we'd like to but it could work in another
            # case so I'm leaving this here as an advice
            logger.info(f"Processing page {page_count} of {self.total_pages}")
            self.process_current_page()

            next_button = self.driver.find_element(By.ID, "ImgBtnSiguiente")
            next_button.click()
            time.sleep(2)
            # Personally hate applying static wait times, but it's the only way to make sure the page is loaded as it
            # does not change dynamically except for contents and it's a bit more complex to check if contents have
            # changed in relation to the previous page

            page_count += 1

    def save_results(
        self,
        txt_path: str = "data/reinfo_scraper_results.txt",
        csv_path: str = "data/reinfo_scraper_results.csv",
    ) -> None:
        """Save scraped data to text and CSV files.

        Args:
            txt_path (str): Path to save text file
            csv_path (str): Path to save CSV file
        """
        os.makedirs("data", exist_ok=True)

        with open(txt_path, "w") as file_txt:
            for row in self.data:
                line = ",".join(map(str, row))
                file_txt.write(line + "\n")
        logger.info(f"Data saved to {txt_path}")

        df = pd.DataFrame(
            self.data,
            columns=[
                "id",
                "ruc",
                "nombre",
                "nombre_derecho_minero",
                "codigo_unico",
                "departamento",
                "provincia",
                "distrito",
                "estado",
            ],
        )
        df.to_csv(csv_path, index=False)
        logger.info(f"Data saved to {csv_path}")

    def save_partial_results(self) -> None:
        """Save partial results with timestamp when scraping fails."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"data/reinfo_scraper_partial_data_{timestamp}"
        txt_path = f"{base_name}.txt"
        csv_path = f"{base_name}.csv"

        logger.info(f"Saving partial results with {len(self.data)} rows")
        self.save_results(txt_path, csv_path)

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.driver:
            self.driver.quit()
            logger.info("Web driver closed")

    def run(self) -> None:
        """Run the complete scraping process."""
        self.start_time = datetime.now()
        try:
            self.setup_driver()
            self.navigate_to_page()
            self.process_current_page()
            self.scrape_all_pages()
            self.save_results()
        except (Exception, KeyboardInterrupt) as e:
            logger.error(f"An error occurred during scraping: {e}")
            logger.info("Attempting to save partial results...")
            self.save_partial_results()
            if not isinstance(e, KeyboardInterrupt):
                raise
        finally:
            self.cleanup()
            duration = datetime.now() - self.start_time
            logger.info(f"Scraping process finished in {duration}")


def main():
    try:
        scraper = ReinfoScraper(headless=False)
        scraper.run()
    except Exception as e:
        logger.error(f"Failed to complete scraping process: {e}")
        raise


if __name__ == "__main__":
    main()
