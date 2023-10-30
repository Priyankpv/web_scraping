import logging
import re

from bs4 import BeautifulSoup as bs
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper
from core.common import _tt, get_hash, modify_html, tag_text
from core.common.functions import split_at
from core.common.soup import wrap_tags


class Main(BidScraper):
    settings = {
        "version": "2.0.1",
        "script_name": "city_brenham",
        "base_url": "https://www.cityofbrenham.org/",
        "created_by": "jalbu@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "City of Brenham",
        "agency_state": "TX",
        "agency_type": "State & Local",
        "agency_website": "https://www.cityofbrenham.org",
        "index_url": "/city_government/departments/finance/purchasing.php",
        "row_sel": ".col-md-8 .entry .post.clearfix",
    }

    def pre_execute(self):
        if index_page := self.get(self.settings["index_url"]):
            self.soup = bs(index_page.text, "html5lib").select_one(self.settings["row_sel"])
        else:
            self.soup = ""
            logging.error(
                "No response from index page: %s",
                self.urljoin(self.settings["index_url"]),
            )

    def fetch_rows(self):
        if self.status == "closed":
            return
        if not self.soup:
            return
        for i in py_.tail(
            list(
                split_at(
                    lambda x: x.name == "span" and py_.get(x, "attrs.class.0") == "subheader",
                    self.soup.find_all(),
                    include="second",
                )
            )
        ):
            yield wrap_tags(i)

    def bid_id_from_row(self, row):
        text = tag_text(row)
        if text:
            return get_hash(text)

    def scrape_bid(self, bid, row):
        title = _tt(row.select_one(".subheader"))
        bid.bidNumber = re.search(r"(.+\d{3})", title).group(1)
        bid.title = (
            (
                _tt(row.select_one("p")).split("Deadline")[0]
                if (not row.select_one("li")) or (_tt(row.select_one("li")) == "Addendum No. 1")
                else (_tt(row.select_one("li")).split(".")[0]).split(";")[0]
            )
            if title == bid.bidNumber
            else title
        )
        dd = re.search(r"(:?Deadline|Bid Opening)\s?\:?(.+\d{4})", _tt(row))
        bid.dueDate = core.parse_date(dd.group(2)) if dd else ""
        bid.description = modify_html(row)
        bid.sourceURL = bid.bidURL = self.urljoin(f'{self.settings["index_url"]}#{bid.bidNumber}')
        if doc_link := row.select('a[href$="pdf"]'):
            return lambda: [i.get("href") for i in set(doc_link) if re.search(bid.bidNumber, str(i))]


if __name__ == "__main__":
    Main().run()

