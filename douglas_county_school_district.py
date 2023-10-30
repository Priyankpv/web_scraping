import datetime
import logging
import re

from bs4 import BeautifulSoup as bs
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper
from core.common import _tt, get_hash, tag_text

todays_date = datetime.datetime.now()


class Main(BidScraper):
    settings = {
        "version": "1.0.7",
        "script_name": "douglas_county_school_district",
        "base_url": "https://www.dcsd.k12.nv.us",
        "agency_website": "https://www.dcsd.k12.nv.us",
        "ext_url": "/departments/business-services",
        "created_by": "dparisi@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Douglas County School District",
        "agency_state": "NV",
        "agency_type": "State & Local",
    }

    def fetch_rows(self):
        if self.status == 'closed': return
        self.bid_rows = []
        if not (res_soup:=self.get(self.settings["ext_url"],soup = True)):
            logging.error("No response from %s", self.urljoin(self.settings["ext_url"]))
        table = div.parent if (div:= res_soup.find(
            True,
            text=re.compile(
                "Bidding & Current Projects" if self.status == "open" else "Awarded Contracts"
            ), 
        )) else None
        table_url = table.select_one("a").get("href")
        table_resp = self.get(self.settings["ext_url"] + table_url)
        if not table_resp:
            logging.error("Table tag not found - exiting")
            return
        rows = bs(table_resp.text, "html5lib").select(
            ".fsElementContent .fsElement.fsContent .fsElementContent table tr"
        )
        header, *rows = rows
        header = [tag_text(h) for h in header.select("th")]
        yield from [
                    dict(
                        **{header[n]: _tt(cell) for n, cell in enumerate(row.select("td"))},
                        downloads=[(py_.clean(a.text), a.get("href")) for a in row.select("a[href]")]
                    )
                    for row in rows
                ]

    def bid_id_from_row(self, rdict):
        return get_hash(str(rdict))

    def scrape_bid(self, bid, rdict):
        if self.status == "open":
            core.common.objects.set_obj_attributes(
                bid,
                rdict,
                {
                    "title": "Project Name",
                    "dueDate": ("Bid Submission Due Date", core.common.parse.parse_date),
                    "awardedTo": "Contract Awarded",
                },
            )
            bid.dueDate = core.common.parse.parse_date(str(todays_date - datetime.timedelta(1)))

        bid.bidURL = bid.sourceURL = self.urljoin(self.settings["ext_url"] + "#" + bid.bidNumber)
        bid.description = core.common.objects.make_description_from_dict(
            py_.omit(rdict, "downloads")
        )
        return lambda: py_.get(rdict, "downloads") if self.status == "open" else []


if __name__ == "__main__":
    Main().run()

