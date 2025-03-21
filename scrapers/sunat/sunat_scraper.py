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
from selenium.webdriver.support.ui import WebDriverWait

from scrapers.base_scraper import BaseScraper


class SunatScraper(BaseScraper):
    """Class to scrape information from Sunat website."""

    def __init__(self, headless: bool = False, csv_path: str = None):
        """Initialize the scraper with browser options.

        Args:
            headless (bool): Whether to run the browser in headless mode
            csv_path (str, optional): Path to the CSV file containing RUC data
        """
        super().__init__(headless=headless, log_file="sunat_scraper")
        self.csv_path: Optional[str] = csv_path
        self.csv_data: Optional[pd.DataFrame] = None
        self.ruc_results = pd.DataFrame(columns=["ruc", "result"])
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

    def navigate_to_page_with_data(self, ruc: str) -> None:
        """Navigate to the Redjum website and set up initial search."""
        try:
            self.perform_complete_cleanup()
            self.driver.get("https://e-consultaruc.sunat.gob.pe")

            try:
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                self.logger.warning("Page might not be fully loaded, attempting to proceed anyway")

            ruc_input = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, "txtRuc")))

            ruc_input.clear()
            ruc_input.send_keys(str(ruc))
            self.logger.info(f"Inserting RUC: {ruc}")

            submit_button = self.driver.find_element(By.ID, "btnAceptar")
            submit_button.click()

        except WebDriverException as e:
            self.logger.error(f"Navigation failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during navigation: {e}")
            raise

    def load_ruc_data(self, csv_path: str = None) -> pd.DataFrame:
        """Load RUC data from CSV file or get manual input.

        Args:
            csv_path (str, optional): Path to the CSV file containing RUC data

        Returns:
            pd.DataFrame: DataFrame containing formatted RUC numbers
        """
        if not csv_path:
            return
        try:
            self.csv_data = pd.read_csv(csv_path, dtype={"ruc": str})
            new_rows = pd.DataFrame({"ruc": self.csv_data["ruc"], "result": ""})
            self.ruc_results = pd.concat([self.ruc_results, new_rows], ignore_index=True)
            self.logger.info(f"Successfully loaded {len(self.csv_data)} RUC numbers from {csv_path}")
        except Exception as e:
            self.csv_data = None
            self.logger.error(f"Failed to load RUC data: {e}")
            raise

    def get_field_data(self, css_selector: str) -> str:
        """Get field data using a CSS selector with proper exception handling.

        Args:
            css_selector (str): The CSS selector to find the element

        Returns:
            str: The extracted text value or empty string if not found
        """
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, css_selector)
            return element.text.strip()
        except Exception:
            return None

    def extract_ruc_info(self, ruc: str) -> None:
        """Process a single RUC number and extract all available information.

        Args:
            ruc (str): RUC number to process
        """
        try:
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.list-group")))
            self.logger.info("Main container found successfully")

            ruc_data = {}

            self.logger.info("Starting data extraction for RUC: " + ruc)

            self.logger.info("Extracting basic information...")
            ruc_data["ruc_nombre"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(1) > div > div.col-sm-7"
                )
            )
            ruc_data["tipo_contribuyente"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(2) > div > div.col-sm-7 > p"
                )
            )
            ruc_data["tipo_documento"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(3) > div > div.col-sm-7 > p"
                )
            )
            ruc_data["nombre_comercial"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(4) > div > div.col-sm-7 > p"
                )
            )
            if ruc_data["nombre_comercial"] is None:
                ruc_data["nombre_comercial"] = self.get_field_data(
                    (
                        "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                        "div:nth-child(3) > div > div.col-sm-7 > p"
                    )
                )
            self.logger.info("Extracting dates...")
            ruc_data["fecha_inscripcion"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(5) > div > div:nth-child(2) > p"
                )
            )
            ruc_data["fecha_inicio_actividades"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(5) > div > div:nth-child(4) > p"
                )
            )
            if ruc_data["fecha_inicio_actividades"] is None:
                ruc_data["fecha_inicio_actividades"] = self.get_field_data(
                    (
                        "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                        "div:nth-child(4) > div > div:nth-child(4) > p"
                    )
                )

            self.logger.info("Extracting status information...")
            ruc_data["estado"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(6) > div > div.col-sm-7 > p"
                )
            )

            self.logger.info("Extracting address and system information...")
            ruc_data["domicilio"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(8) > div > div.col-sm-7 > p"
                )
            )
            if ruc_data["domicilio"] is None:
                ruc_data["domicilio"] = self.get_field_data(
                    (
                        "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                        "div:nth-child(7) > div > div.col-sm-7 > p"
                    )
                )
            ruc_data["sistema_emision"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(9) > div > div:nth-child(2) > p"
                )
            )
            ruc_data["actividad_comercio_exterior"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(9) > div > div:nth-child(4) > p"
                )
            )
            if ruc_data["actividad_comercio_exterior"] is None:
                ruc_data["actividad_comercio_exterior"] = self.get_field_data(
                    (
                        "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                        "div:nth-child(8) > div > div:nth-child(4) > p"
                    )
                )
            ruc_data["sistema_contabilidad"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(10) > div > div.col-sm-7 > p"
                )
            )
            if ruc_data["sistema_contabilidad"] is None:
                ruc_data["sistema_contabilidad"] = self.get_field_data(
                    (
                        "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                        "div:nth-child(9) > div > div:nth-child(2) > p"
                    )
                )

            self.logger.info("Extracting table-based information...")
            ruc_data["actividades_economicas"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(11) > div > div.col-sm-7 > table > tbody > tr > td"
                )
            )
            if (
                ruc_data["actividades_economicas"] is None
                or ruc_data["actividades_economicas"] == ruc_data["sistema_contabilidad"]
            ):
                ruc_data["actividades_economicas"] = self.get_field_data(
                    (
                        "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                        "div:nth-child(10) > div > div.col-sm-7 > table > tbody > tr:nth-child(1) > td"
                    )
                )
            fallback = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(10) > div > div.col-sm-7 > table > tbody > tr:nth-child(1) > td"
                )
            )
            if fallback and len(fallback) > len(ruc_data["actividades_economicas"]):
                ruc_data["actividades_economicas"] = fallback

            self.logger.info("Extracting electronic emission information...")
            ruc_data["emisor_electronico_desde"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(14) > div > div.col-sm-7 > p"
                )
            )
            ruc_data["comprobantes_electronicos"] = self.get_field_data(
                (
                    "body > div > div.row > div > div.panel.panel-primary > div.list-group > "
                    "div:nth-child(15) > div > div.col-sm-7 > p"
                )
            )

            self.data[ruc] = ruc_data
            self.logger.info(f"Successfully extracted all data for RUC: {ruc}")
            self.logger.debug(f"Complete data for RUC {ruc}: {json.dumps(ruc_data, indent=2)}")

        except Exception as e:
            self.logger.error(f"Failed to extract RUC info for {ruc}: {e}")
            raise

    def scrape(self) -> None:
        """Main scraping method."""
        self.load_ruc_data(self.csv_path)
        if self.csv_data is not None:
            for index, row in self.csv_data.iterrows():
                try:
                    self.logger.info(f"Processing RUC {index+1}/{len(self.csv_data)}...")

                    self.navigate_to_page_with_data(row["ruc"])
                    time.sleep(3)
                    self.logger.info(f"Attempting to extract data for RUC: {row['ruc']}")
                    self.extract_ruc_info(row["ruc"])
                    self.ruc_results.iloc[index, self.ruc_results.columns.get_loc("result")] = "success"
                except Exception as e:
                    self.ruc_results.iloc[index, self.ruc_results.columns.get_loc("result")] = "fail"
                    self.logger.error(f"Failed to process RUC {row['ruc']}: {e}")
                    continue

        else:
            raise ValueError("No CSV file provided")

    def save_results(
        self,
        json_file_path: str = "data/sunat_scraper_results.json",
        csv_file_path: str = "data/sunat_scraping_results.csv",
    ) -> None:
        """Save the results to JSON and CSV files.

        Args:
            file_path (str): Path to save the JSON results
        """
        os.makedirs("data", exist_ok=True)

        with open(json_file_path, "w") as f:
            json.dump(self.data, f, indent=2)
        self.logger.info(f"Scraping results data saved to {json_file_path}")

        self.ruc_results.to_csv(csv_file_path, index=False)
        self.logger.info(f"Scraping results statuses saved to {csv_file_path}")

    def save_partial_results(self) -> None:
        """Save partial results with timestamp when scraping fails."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"data/sunat_scraper_partial_data_{timestamp}"
        file_path = f"{base_name}.json"

        self.logger.info(f"Partial results saved to {file_path} with {len(self.data)} entries")
        self.save_results(file_path)


def main():
    """Main entry point for the scraper."""
    parser = argparse.ArgumentParser(description="Sunat Scraper")
    parser.add_argument("--csv", type=str, help="Path to the CSV file containing RUC data")
    args = parser.parse_args()

    try:
        scraper = SunatScraper(headless=False, csv_path=args.csv)
        scraper.run()
    except Exception as e:
        logging.getLogger("sunat_scraper").error(f"Failed to complete scraping process: {e}")
        raise


if __name__ == "__main__":
    main()
