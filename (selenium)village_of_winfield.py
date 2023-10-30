import datetime
import logging
import re

import textract
from bs4 import BeautifulSoup as bs
from pydash import clean
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import core
from core.bid_scraper_plus import BidScraper
from core.common import get_hash, long_re_date, _tt
from core.common.selenium import make_chrome_driver


regexes = "|".join([r"submitted.*? no later than"])

date_search = re.compile(rf"(:?{regexes})[ \w\.\:\,]*?{long_re_date}", re.I)


class Main(BidScraper):
    settings = {
        "version": "1.0.0",
        "script_name": "village_of_winfield",
        "base_url": "https://www.villageofwinfield.com",
        "created_by": "jclervil@govspend.com",
        "last_modified_by": "jclervil@govspend.com",
        "agency_name": "Village of Winfield",
        "agency_state": "IL",
        "agency_type": "State & Local",
        "agency_website": "https://www.villageofwinfield.com/",
        "index_url": "/DocumentCenter/Index/47",
        "post_url": "/Admin/DocumentCenter/Home/Document_AjaxBinding",
        "row_sel": 'tr.t-master-row a[href*="ocumentCent"]',
    }

    def pre_execute(self):
        if not self.settings["document_download"]:
            logging.info(
                "Setting document download to true. This script relies on extracting text from pdf."
            )
            self.settings["document_download"] = True
        self.get()

    def fetch_rows(self):
        if self.status == "open":
            driver = make_chrome_driver(["--headless"])
            driver.get(self.urljoin(self.settings["index_url"]))
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.settings["row_sel"]))
            )
            yield from bs(driver.page_source, "html5lib").select(self.settings["row_sel"])
            driver.quit()

    def bid_id_from_row(self, row):
        if _tt(row):
            return get_hash(_tt(row))

    def scrape_bid(self, bid, row):
        bid.title = bid.description = _tt(row)
        bid.sourceURL = self.urljoin(f'{self.settings["index_url"]}#{bid.bidNumber}')
        if file_info := self.download_file(bid, row.get("href")):
            text = ""
            try:
                text = textract.process(file_info.path).decode("utf-8")
            except Exception as e:
                logging.info("Unable to extract text from the document. %s", e)
            if text:
                if due_date := date_search.search(clean(text)):
                    bid.dueDate = core.common.parse.parse_date(due_date.group(1))
                    if len(text) > 1000:
                        text = text[:997] + "..."
                    text = text.replace("\n", "<br>")
                    bid.description = clean(f"<hr><center><blockquote>{text}</blockquote></center>")


if __name__ == "__main__":
    Main().run()

