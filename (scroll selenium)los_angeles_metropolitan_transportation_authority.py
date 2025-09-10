import time

from bs4 import BeautifulSoup
from pydash import py_
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import core
from core.bid_scraper_plus import BidScraper
from core.common import clean_filename, get_hash, parse_date, tag_text
from core.common.objects import make_description_from_dict
from core.common.selenium import make_chrome_driver, wait_for


class Main(BidScraper):
    settings = {
        "version": "1.1.9",
        "script_name": "los_angeles_metropolitan_transportation_authority",
        "base_url": "https://business.metro.net/webcenter/portal/VendorPortal/pages_home/solicitations/openSolicitations",
        "created_by": "ahernandez@gmail.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Los Angeles Metropolitan Transportation Authority",
        "agency_state": "CA",
        "agency_type": "State & Local",
        "agency_website": "https://business.metro.net",
    }

    def pre_execute(self):
        self.driver = driver = make_chrome_driver(
            ["user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"]
        )
        driver.get(self.urljoin(self.settings["base_url"]))

    def fetch_rows(self):
        driver = self.driver
        driver.implicitly_wait(10)
        time.sleep(5)
        search_input_field = driver.find_element(By.CSS_SELECTOR, '[class="af_inputText_content"]')
        search_input_field.clear()
        time.sleep(0.5)
        driver.find_element(By.XPATH, '//button[text()="Search"]').click()
        time.sleep(2)
        table_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".AFStretchWidth.af_panelCollection"))
        )
        table_element = driver.find_element_by_class_name("AFStretchWidth.af_panelCollection")
        driver.execute_script("arguments[0].scrollIntoView();", table_element)
        driver.save_screenshot("screenshot.png")
        try:
            max_scroll_height = driver.execute_script(
                "return document.querySelector(\"div[style='position: absolute; overflow: auto; z-index: 0; width: 691px; top: 38px; height: 613px; right: 0px;']\").scrollHeight;"
            )
        except Exception:
            max_scroll_height = 8500
        bid_numbers = set()
        scroll_height = 400
        while scroll_height < max_scroll_height:
            rows = driver.find_elements(By.CSS_SELECTOR, "tr.af_table_data-row")
            for row in rows:
                bid_number = row.find_element(By.CSS_SELECTOR, "td:first-child").text
                if bid_number:
                    bid_numbers.add(bid_number)
            try:
                driver.execute_script(
                    f"document.querySelector(\"div[style='position: absolute; overflow: auto; z-index: 0; width: 691px; top: 38px; height: 613px; right: 0px;']\").scrollTop = {scroll_height}"
                )
            except Exception as e:
                pass
            if scroll_height >= max_scroll_height:
                break
            time.sleep(3)
            scroll_height += 400
        for data in bid_numbers:
            back_button = driver.find_elements(By.XPATH, '//a[contains(text(), "Back to")]')
            if back_button:
                back_button[0].click()
                time.sleep(2)
            searchInput = driver.find_element(By.CSS_SELECTOR, '[class="af_inputText_content"]')
            searchInput.clear()
            searchInput.send_keys(data)
            time.sleep(1)
            driver.find_element(By.XPATH, '//button[text()="Search"]').click()
            time.sleep(2)
            table = driver.find_element_by_class_name("AFStretchWidth.af_panelCollection")
            driver.execute_script("arguments[0].scrollIntoView();", table)
            time.sleep(2)
            table.find_element(By.CSS_SELECTOR, '[class="af_commandLink"]').click()
            time.sleep(5)
            bid_data_table = driver.find_elements(
                By.CSS_SELECTOR, '[class="af_panelLabelAndMessage p_AFReadOnly"]'
            )
            bid_dict = {}
            for element in bid_data_table:
                bid_data = element.text.split("\n")
                if len(bid_data) > 1 and bid_data[0] and bid_data[1]:
                    bid_dict[bid_data[0].strip()] = bid_data[1].strip()
            html_content = driver.page_source
            self.soup = BeautifulSoup(html_content, "html.parser")
            time.sleep(3)
            try:
                driver.find_element(By.XPATH, '//a[contains(text(), "Back to")]').click()
                time.sleep(2)
            except Exception as e:
                continue
            yield bid_dict

    def bid_id_from_row(self, row):
        if py_.get(row, "Number"):
            return get_hash(str(row))

    def scrape_bid(self, bid, row):
        core.common.set_obj_attributes(
            bid,
            row,
            {
                "bidNumber": ("Number"),
                "title": "Title",
                "postedDate": ("Issue Date", parse_date),
                "dueDate": ("Due Date and Time", parse_date),
            },
        )
        bid.sourceURL = (
            self.urljoin(self.settings["base_url"]) + "#" + clean_filename(bid.bidNumber)
        )
        bid.bidURL = self.settings["base_url"]
        bid.description = make_description_from_dict(row)
        return lambda: filter(
            lambda x: "media" in x[1] and not x[1].endswith(".zip"), self.scrape_links(self.soup)
        )


if __name__ == "__main__":
    Main().run()

