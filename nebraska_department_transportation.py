import datetime
import json
import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup as bs
from pydash import py_
from w3lib.html import remove_tags
import core
from common.text_utils import get_hash
from core.bid_scraper_plus import BidScraper


class Main(BidScraper):
    settings = {
        "version": "1.0.4",
        "script_name": "nebraska_department_transportation",
        "base_url": "https://dot.nebraska.gov",
        "created_by": "jclervil@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Nebraska Department of Transportation",
        "agency_state": "NE",
        "agency_type": "State & Local",
        "agency_website": "https://dot.nebraska.gov",
        "index_url": "/business-center/business-opp/procure-service-opp/",
        "row_sel": "table > tbody",
        "urls": {
            "open": "/umbraco/Surface/Business/GetBids/2374",
            "closed": "/umbraco/Surface/Business/GetPastBids/2374",
        },
    }

    def fetch_rows(self):
        if not (res := self.get(self.settings["urls"][self.status])):
          logging.error(
                  "No content returned from index page: %s",
                  self.urljoin(self.settings["index_url"]),
              )
        yield from json.loads(res.text)

    def bid_id_from_row(self, row):
        if any(row.values()):
            return get_hash(str(row))

    def scrape_bid(self, bid, row):
        date_parse = lambda x:core.parse_date(datetime.fromtimestamp(int(re.search(r"(\d{10})", x).group(1))).strftime("%d-%m-%y"))
        core.set_obj_attributes(
            bid,
            row,
            {
                'title': ("Description",remove_tags),
                'bidNumber': "ItemName",
                'description': "Description",
                'dueDate': ('DeadlineDate',date_parse),
                'postedDate': ('PostDate',date_parse),
                'awardedTo': "Buyer"
            }
        )
        bid.sourceURL = bid.bidURL = self.urljoin(f'{self.settings["index_url"]}#{bid.bidNumber}')
        detail_page_resp = self.get(self.urljoin(row["BidLink"]))
        if detail_page_resp:
            doc_list = bs(detail_page_resp.text, "html5lib").select(".col-md-8.column > div ul a")
            return lambda: [i.get("href") for i in doc_list]
        else:
            logging.error("No Response from url : %s" % self.urljoin(row["BidLink"]))


if __name__ == "__main__":
    Main().run()

