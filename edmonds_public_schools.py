import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup as bs
from dateutil import parser as dparser
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper
from core.common import datefmt, get_hash, long_re_date, _tt

todays_date = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)


class Main(BidScraper):
    settings = {
        "version": "1.0.3",
        "script_name": "edmonds_public_schools",
        "base_url": "https://edmondschools.net",
        "created_by": "jedmonson@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Edmond Public Schools",
        "agency_state": "OK",
        "agency_type": "State & Local",
        "index_url": "/o/eps/page/purchasing",
    }

    def pre_execute(self):
        resp = self.get(py_.get(self, "settings.index_url"))
        if not resp:
            logging.error("Failed to get valid response for url: %s", self.settings["index_url"])
        self.bid_rows = list(filter(lambda x:_tt(x),py_.tail(bs(resp.text, "html5lib").select("table > tbody > tr"))))

    def fetch_rows(self):
        def check_row(row):
            try:
                dd_str = py_.clean(py_.get(row.select_one("td:nth-of-type(2)"), "text"))
                all_matches = list(re.finditer(long_re_date, dd_str, re.I))
                self.duedate = dparser.parse(py_.head(all_matches).group(1))
            except ValueError:
                return False
            if self.status == "open" and self.duedate >= todays_date:
                return True
            elif self.status == "closed" and self.duedate < todays_date:
                return True
            else:
                return False

        yield from filter(check_row, self.bid_rows)

    def bid_id_from_row(self, row):
        self.rowtxt = py_.clean(" ".join(py_.get(row, "stripped_strings")))
        if self.rowtxt:
            return get_hash(self.rowtxt)

    def scrape_bid(self, bid, row):
        get_dd = lambda: self.duedate.strftime(datefmt)
        bid.dueDate, bid.title = get_dd(), py_.get(row, "a.text")
        bno = re.search(r"\d+\-\d+", bid.title)
        if bno:
            bid.bidNumber = bno.group()
        bid.sourceURL = self.urljoin(f"{self.settings.get('index_url')}#{bid.bidNumber}")
        bid.description = core.common.soup.make_description(row)
        return lambda: self.scrape_links(row)


if __name__ == "__main__":
    Main().run()

