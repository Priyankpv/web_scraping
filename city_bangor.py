import logging
import re

import pdftotext
from bs4 import BeautifulSoup as bs
from pydash import clean, get
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import core
from core.bid_scraper_plus import BidScraper
from core.common import _tt, get_hash, long_re_date
from core.common.functions import split_at
from core.common.selenium import make_chrome_driver
from core.common.soup import wrap_tags


class Main(BidScraper):
    settings = {
        "version": "2.2.2",
        "script_name": "city_bangor",
        "base_url": "https://www.bangormaine.gov",
        "ext_url": {"open": "/proposals", "closed": "/bidtabs"},
        "created_by": "dparisi@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "City of Bangor",
        "agency_state": "ME",
        "agency_type": "State & Local",
        "agency_website": "https://www.bangormaine.gov",
        "regex_strings": {
            "open": r"To be considered, return .+ in an envelope clearly marked "
            r"[\"“].+[\"”]? by (?:\d+:\d\d\s?[ap]\.?m\.?,)(?: .+day,)? "
            rf"{long_re_date} to the purchasing department",
            "closed": rf"bid opening: (?:.+day, )?{long_re_date}",
        },
    }

    def pre_execute(self):
        self.driver = make_chrome_driver(
            [
                "--headless",
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
            ]
        )
        self.driver.set_page_load_timeout(180)
        self.driver.maximize_window()
        if self.settings["all_solicitations"] and not self.settings["document_download"]:
            logging.warning(
                "Setting document_download to True. This script relies on downloading and extracting text "
                "from the pdf on each bid page."
            )
            self.settings["document_download"] = True

    def fetch_rows(self):
        page_url = self.urljoin(self.settings["ext_url"][self.status])
        self.driver.get(page_url)
        WebDriverWait(self.driver, 90).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "td.ContentTemp_MainCol"))
        )
        soup = bs(self.driver.page_source, "lxml")
        if self.status == "open":
            if main_table_sel := soup.select("table.ContentTemp_2Column tbody tr td p:nth-of-type(n+2)"):
                yield from filter(
                    lambda x: _tt(x) != "",
                    list(
                        map(
                            wrap_tags,
                            split_at(
                                lambda tag: tag.name == "p" and _tt(tag) == "", main_table_sel
                            ),
                        )
                    ),
                )
            else:
                logging.error("Error finding bid table on page! URL: %s", page_url)
        elif self.status == "closed":
            yield from soup.select("ul.FB_FileListUL > li")

    def bid_id_from_row(self, data):
        return get_hash(str(data))

    def scrape_bid(self, bid, row):
        def get_date_from_file(row):
            find_date = re.compile(self.settings["regex_strings"][self.status], re.I)
            download = get(row, "a.href")
            row.a.extract()
            if download:
                file_infos = self.download_file(bid, download, use_remote_file_name=True)
                with open(file_infos.path, "rb") as _file:
                    try:
                        _pdf = pdftotext.PDF(_file)
                        pdf_dump = clean(" ".join(_pdf))
                        if not pdf_dump:
                            logging.info("Could not dump PDF file %s", file_infos.path)
                    except Exception as ex:
                        logging.info(
                            "Could not dump PDF file %s - Exception: %s",
                            file_infos.path,
                            ex,
                        )
                        return
                    look_for_date = find_date.search(pdf_dump)
                    if look_for_date:
                        dd = look_for_date.group(1)
                        if dd:
                            bid.dueDate = core.common.parse.parse_date(dd)

        bid.sourceURL = self.urljoin(f"{self.settings['ext_url'][self.status]}#{bid.bidNumber}")
        if self.status == "open":
            if row_title := get(row, "b"):
                bid.title = _tt(row_title)
            else:
                logging.error("Problem parsing bid title!")
            if find_dates := [
                re.search(long_re_date, _tt(strong_tag), re.I)
                for strong_tag in row.select("strong")
                if re.search(long_re_date, _tt(strong_tag), re.I)
            ]:
                if len(find_dates) == 1:
                    bid.dueDate = core.common.parse.parse_date(find_dates[0].group(0))
            else:
                get_date_from_file(row)

            bid.description = clean(core.common.modify_html(row))
            return lambda: [
                self.urljoin(x.get("href")) for x in row.select('a[href^="/filestorage"]')
            ]
        elif self.status == "closed":
            bid.title = _tt(get(row, "a"))
            bid.description = clean(core.common.modify_html(row))
            if awarded_to_tag := get(row, "a.attrs.title"):
                if 'Pending Award.' not in awarded_to_tag:
                  awarded = re.sub(r"awarded to ", "", awarded_to_tag, re.I).split("-")
                  bid.awardedTo = clean(awarded[0])
                  bid.awardedDate = core.parse_date(awarded[1]) if len(awarded) > 1 else ''
            get_date_from_file(row)


if __name__ == "__main__":
    Main().run()

