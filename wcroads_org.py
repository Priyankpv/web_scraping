import datetime
import logging
import re
from itertools import count

import dateutil.parser as dparser
from bs4 import BeautifulSoup as bs
from pydash import py_

import core
from common.misc import tag_text, todays_date
from common.text_utils import clean_filename, get_hash, modify_html
from core.bid_scraper_plus import BidScraper


class Main(BidScraper):
    settings = {
        "version": "1.0.0",
        "script_name": "wcroads_org",
        "created_by": "pvamja@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Washtenaw County Road Commission",
        "agency_state": "MI",
        "agency_type": "State & Local",
        "base_url": "https://www.wcroads.org",
        "agency_website": "https://www.wcroads.org",
        "index_url": "/category/bids/",
        "row_sel": ".title > a[href]",
    }

    def fetch_rows(self):
        if self.status == "closed":
            return
        index_link = self.settings["index_url"]
        while True:
            if res := self.get(index_link):
                soup = bs(res.text, "html5lib")
                yield from map(
                    lambda row: {"row": row, "link": row.get("href")},
                    soup.select(self.settings["row_sel"]),
                )
                if next_page := soup.select_one(".next > a[href]"):
                    index_link = py_.get(next_page, "href")
                else:
                    break
            else:
                logging.error("No response from URL :: %s", self.urljoin(index_link))

    def bid_id_from_row(self, row):
        text = tag_text(row["row"])
        if text:
            return get_hash(text)

    def scrape_bid(self, bid, row):
        detail_res = self.get(row["link"])
        page_detail = bs(detail_res.text, "html5lib")
        if page_detail.select(".content-inner > p"):
            desc = [py_.clean(modify_html(i)) for i in page_detail.select(".content-inner > p")]
            bid.description = "<br>".join(desc)
        elif page_detail.select(".wpb_wrapper > p"):
            desc = [py_.clean(modify_html(i)) for i in page_detail.select(".wpb_wrapper > p")]
            bid.description = "<br>".join(desc)
        elif page_detail.select(".field-item > p"):
            desc = [py_.clean(modify_html(i)) for i in page_detail.select(".field-item > p")]
            bid.description = "<br>".join(desc)

        bid.title = page_detail.select_one(".entry-title").text
        bid.postedDate = core.parse_date(
            page_detail.select_one('[class*="meta-date date updated"]').text
        )
        bid_duedate_re = re.compile(
            r"(\w+\s\d{2}[,]?\s\d{4}|\w+\s\d[,]?\s\d{4}|\w+\s\d\w+[,]?\s\d{4})", re.I
        )
        if bid_duedate := re.search(bid_duedate_re, bid.description):
            bid.dueDate = core.parse_date(bid_duedate.group(1) if bid_duedate else "")
        else:
            bid.dueDate = core.parse_date(
                page_detail.select_one('[class*="meta-date date updated"]').text
            )
        if not bid.dueDate:
            a = 1
        bid.sourceURL = bid.bidURL = self.urljoin(row["link"] + "#" + clean_filename(bid.bidNumber))
        return lambda: [
            a.get("href") for a in page_detail.select('p > a[href*="/wp-content/uploads/"]')
        ]


if __name__ == "__main__":
    Main().run()

