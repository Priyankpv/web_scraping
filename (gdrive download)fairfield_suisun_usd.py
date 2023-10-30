import logging
import re
from urllib.parse import unquote

import textract
from bs4 import BeautifulSoup as bs
from pydash import py_

import core
from common.text_utils import get_hash
from core.bid_scraper_plus import BidScraper, SkipBid
from core.common import download_google_folder_files


class Main(BidScraper):
    settings = {
        "version": "1.0.4",
        "script_name": "fairfield_suisun_usd",
        "base_url": "https://www.fsusd.org",
        "created_by": "jedmonson@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Fairfield-Suisun Unified School District",
        "agency_state": "CA",
        "agency_type": "State & Local",
        "index_url": "/page/bids-request-for-proposals",
        "agency_website": "https://www.fsusd.org",
    }

    def pre_execute(self):
        if not self.settings["document_download"]:
            logging.warning("This script relies on parsing the dueDates from downloaded files!")
            self.settings["document_download"] = True
        self.index = self.get(py_.get(self, "settings.index_url"))
        self.soup = bs(self.index.text, "html5lib")

    def fetch_rows(self):
        if self.status == "closed":
            yield from lbl if (
              lbl := re.findall(
                  r'buttons\:\[\{link:\"(https:.*?)\"\,title:\"(.*?)?"', self.index.text
              )
          ) else logging.error("No rows found")
        else:
            yield from [
            (i.get("href"), core.tag_text(i))
            for i in self.soup.select('.column > .block ul p a[target*="_blank"]')
            if "https://drive.google.com/" in i.get("href")
        ]

    def bid_id_from_row(self, row):
        self.surl = row[0].replace("\\u002F", "/")
        self.title = row[1].split('"')[0]
        if self.title and self.surl:
            self.surl = self.urljoin(self.surl)
            return get_hash(f"{self.title}|{self.surl}")

    date_res = r"but not? later than\,? (\w+\s\d+\,\s\d+)"

    def scrape_bid(self, bid, row):
        def get_due_date_from_file(soup):
            finfos = []
            fs = download_google_folder_files(self, bid, self.surl)
            finfos.extend(fs)
            for file in finfos:
                if file.path:
                    if dump := textract.process(file.path):
                        dump = dump.decode("utf-8")
                        if c_dump := py_.clean(dump):
                            found_date = re.search(self.date_res, c_dump)
                            if found_date:
                                dd = core.parse_date(found_date.group(1))
                                if len(dump) > 1000:
                                    dump = dump[:997] + "..."
                                dump = dump.replace("\n", "<br>")
                                dump += f"<hr><center><blockquote>{dump}</blockquote></center>"
                                return dump, dd
                        else:
                            logging.warning("Could not dump file to text! URL: %s"%file.url)
            if self.status == "closed":
                dd = bid.set_default_due_date()
                return dump, dd
            else:
                logging.error("No dueDates found in any file for bid :: %s"%bid.sourceURL)

        bid.sourceURL = self.urljoin(f'{self.settings["index_url"]}#{bid.bidNumber}')
        bid.title = self.title
        bid.description = f"<h2>{bid.title}</h2>"
        bno = re.search(r"((RFP|BID|RFQ-P)\s?\:? \#?[0-9]{4}-[0-9]{2})", bid.title)
        bid.bidNumber = bno.group(1)
        if detail_res := self.get(bid.sourceURL):
            bid_page = bs(detail_res.text, "html5lib")
            description, dueDate = get_due_date_from_file(bid_page)
            bid.dueDate = dueDate
            bid.description += description
        else:
            raise SkipBid("No Google drive folder found! Skipping.")


if __name__ == "__main__":
    Main().run()

