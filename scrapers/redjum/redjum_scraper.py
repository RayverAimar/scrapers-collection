import argparse
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from scrapers.base_scraper import BaseScraper


class RedjumScraper(BaseScraper):
    """Class to scrape information from Redjum website."""

    def __init__(self, headless: bool = False, csv_path: str = None):
        """Initialize the scraper with browser options.

        Args:
            headless (bool): Whether to run the browser in headless mode
            csv_path (str, optional): Path to the CSV file containing DNI data
        """
        super().__init__(headless=headless, log_file="redjum_scraper")
        self.csv_path: Optional[str] = csv_path
        self.csv_data: Optional[pd.DataFrame] = None
        self.dni_results = pd.DataFrame(columns=["dni", "result"])
        self.data: Optional[Dict[str, Any]] = {}
        self.network_enabled = False

    def perform_complete_cleanup(self):
        """Perform a complete cleanup of browser data, cache, cookies, and network state."""
        try:
            self.cleanup_network_listeners()

            self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
            self.driver.execute_cdp_cmd("Network.clearBrowserCookies", {})

            try:
                current_url = self.driver.current_url
                if not current_url.startswith("data:"):
                    self.driver.execute_script("window.localStorage.clear();")
                    self.driver.execute_script("window.sessionStorage.clear();")
            except Exception as storage_error:
                self.logger.debug(f"Storage clearing skipped: {storage_error}")

            try:
                self.driver.execute_cdp_cmd(
                    "Storage.clearDataForOrigin",
                    {
                        "origin": "*",
                        "storageTypes": "all",
                    },
                )
            except Exception as storage_error:
                self.logger.debug(f"Cache storage clearing skipped: {storage_error}")

            try:
                self.driver.execute_cdp_cmd("ServiceWorker.disable", {})
                self.driver.execute_cdp_cmd("ServiceWorker.unregister", {"scopeURL": "*"})
            except Exception as sw_error:
                self.logger.debug(f"Service worker cleanup skipped: {sw_error}")

            self.driver.delete_all_cookies()

            self.driver.get_log("performance")
            self.driver.get_log("browser")

            # We need to reset the page to a blank page before navigating to force the
            # cache to be cleared and other stuff that might be causing problems.
            self.driver.get("about:blank")

            self.logger.info("Completed full browser data cleanup")
        except Exception as e:
            self.logger.warning(f"Error during complete cleanup: {e}")

    def cleanup_network_listeners(self):
        """Cleanup network listeners and interception."""
        try:
            if self.network_enabled:
                self.driver.execute_cdp_cmd("Network.setRequestInterception", {"patterns": []})
                self.driver.execute_cdp_cmd("Network.disable", {})
                self.network_enabled = False
                self.logger.info("Network listeners cleaned up successfully")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup network listeners: {e}")

    def get_captcha_solution(self) -> str:
        """Get the solution to the CAPTCHA."""
        # Here you can implement an automatic CAPTCHA solver
        self.logger.info("Waiting for user to solve CAPTCHA...")
        return input("Enter the CAPTCHA solution: ")

    def navigate_to_page_with_data(self, dni: str) -> None:
        """Navigate to the Redjum website and set up initial search."""
        try:
            self.perform_complete_cleanup()
            self.driver.get("https://redjum.pj.gob.pe/redjum/#/")
            time.sleep(1)  # Hate doing this but it's necessary. We could try a dynamic wait too.

            try:
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                self.logger.warning("Page might not be fully loaded, attempting to proceed anyway")

            dni_section = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.nav-link.ng-binding"))
            )

            dni_section = self.driver.find_elements(By.CSS_SELECTOR, "a.nav-link.ng-binding")[2]
            dni_section.click()
            self.logger.info("Successfully navigated to DNI section")

            time.sleep(1)

            dropdown = Select(self.driver.find_element(By.CSS_SELECTOR, "select.form-control"))
            dropdown.select_by_visible_text("DNI")
            self.logger.info("Document type set to DNI")

            dni_input = self.driver.find_element(By.ID, "numerodocumento")
            dni_input.clear()
            dni_input.send_keys(str(dni))
            self.logger.info(f"Inserting DNI: {dni}")

            solution = self.get_captcha_solution()
            solution_input = self.driver.find_element(By.ID, "captcha")
            solution_input.clear()
            solution_input.send_keys(solution)

            self.logger.info(f"Submitting CAPTCHA with solution: {solution}")
            submit_button = self.driver.find_element(By.CSS_SELECTOR, "button.btn.btn-red")
            submit_button.click()

        except WebDriverException as e:
            self.logger.error(f"Navigation failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during navigation: {e}")
            raise

    def load_dni_data(self, csv_path: str = None) -> pd.DataFrame:
        """Load DNI data from CSV file or get manual input.

        Args:
            csv_path (str, optional): Path to the CSV file containing DNI data

        Returns:
            pd.DataFrame: DataFrame containing formatted DNI numbers
        """
        if not csv_path:
            return
        try:
            self.csv_data = pd.read_csv(csv_path, dtype={"dni": str})
            # Create new rows in dni_results for each DNI
            new_rows = pd.DataFrame({"dni": self.csv_data["dni"], "result": ""})
            self.dni_results = pd.concat([self.dni_results, new_rows], ignore_index=True)
            self.logger.info(f"Successfully loaded {len(self.csv_data)} DNI numbers from {csv_path}")
        except Exception as e:
            self.csv_data = None
            self.logger.error(f"Failed to load DNI data: {e}")
            raise

    def extract_dni_info(self, dni: str) -> None:
        """Process a single DNI number.

        Args:
            dni (str): DNI number to process
        """
        try:
            if not self.network_enabled:
                self.driver.execute_cdp_cmd("Network.enable", {})
                self.network_enabled = True

            obj_request_id = None
            dni_data = None

            def intercept_request(request):
                nonlocal obj_request_id
                if "deudoresPorDocumento" in request["request"]["url"]:
                    obj_request_id = request["requestId"]

            def process_response(response):
                nonlocal dni_data
                if response["requestId"] == obj_request_id:
                    try:
                        response_body = self.driver.execute_cdp_cmd(
                            "Network.getResponseBody", {"requestId": response["requestId"]}
                        )
                        dni_data = json.loads(response_body["body"])
                    except Exception as e:
                        self.logger.warning(f"Failed to process response: {e}")

            self.driver.execute_cdp_cmd(
                "Network.setRequestInterception", {"patterns": [{"urlPattern": "*deudoresPorDocumento*"}]}
            )

            devtools = self.driver.get_log("performance")

            for entry in devtools:
                if not ("message" in entry):
                    continue
                message = json.loads(entry["message"])
                if not ("message" in message):
                    continue
                msg = message["message"]
                if msg.get("method") == "Network.requestWillBeSent":
                    intercept_request(msg.get("params", {}))
                elif msg.get("method") == "Network.responseReceived":
                    process_response(msg.get("params", {}))

            if not dni_data:
                raise Exception(f"No data found for DNI: {dni}")

            self.logger.info(f"Data successfully extracted for DNI: {dni}")
            self.data[str(dni)] = dni_data

        except Exception as e:
            self.logger.error(f"Failed to process DNI {dni}: {e}")
            raise
        finally:
            self.cleanup_network_listeners()

    def scrape(self) -> None:
        """Main scraping method."""
        self.load_dni_data(self.csv_path)
        if self.csv_data is not None:
            for index, row in self.csv_data.iterrows():
                try:
                    self.logger.info(f"Processing DNI {index+1}/{len(self.csv_data)}...")

                    self.navigate_to_page_with_data(row["dni"])
                    time.sleep(3)
                    self.logger.info(f"Attempting to extract data for DNI: {row['dni']}")
                    self.extract_dni_info(row["dni"])
                    self.dni_results.iloc[index, self.dni_results.columns.get_loc("result")] = "success"
                except Exception as e:
                    self.dni_results.iloc[index, self.dni_results.columns.get_loc("result")] = "fail"
                    self.logger.error(f"Failed to process DNI {row['dni']}: {e}")
                    continue

        else:
            # If no csv file is provided, the scraper will need to retrieve all possible data
            # from the website. This means it will need to set a range of dates and scrape all
            # information from the website for those dates. Not available yet.
            pass

    def save_results(
        self,
        json_file_path: str = "data/redjum_scraper_results.json",
        csv_file_path: str = "data/redjum_scraping_results.csv",
    ) -> None:
        """Save the results to JSON and CSV files.

        Args:
            file_path (str): Path to save the JSON results
        """
        os.makedirs("data", exist_ok=True)

        with open(json_file_path, "w") as f:
            json.dump(self.data, f, indent=2)
        self.logger.info(f"Scraping results data saved to {json_file_path}")

        self.dni_results.to_csv(csv_file_path, index=False)
        self.logger.info(f"Scraping results statuses saved to {csv_file_path}")

    def save_partial_results(self) -> None:
        """Save partial results with timestamp when scraping fails."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"data/redjum_scraper_partial_data_{timestamp}"
        file_path = f"{base_name}.json"

        self.logger.info(f"Partial results saved to {file_path} with {len(self.data)} entries")
        self.save_results(file_path)


def main():
    """Main entry point for the scraper."""
    parser = argparse.ArgumentParser(description="Redjum Scraper")
    parser.add_argument("--csv", type=str, help="Path to the CSV file containing DNI data")
    args = parser.parse_args()

    try:
        scraper = RedjumScraper(headless=False, csv_path=args.csv)
        scraper.run()
    except Exception as e:
        logging.getLogger("redjum_scraper").error(f"Failed to complete scraping process: {e}")
        raise


if __name__ == "__main__":
    main()
