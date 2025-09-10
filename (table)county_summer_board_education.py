import logging
import re

import core
from bs4 import BeautifulSoup as bs
from core.bid_scraper_plus import BidScraper, SkipBid
from core.common import get_hash, tag_text, make_description_from_dict
from core.common.file_download import clean_filename
from pydash import py_


class Main(BidScraper):
    settings = {
        "version": "1.1.2",
        "script_name": "county_summer_board_education",
        "base_url": "https://www.sumnerschools.org",
        "created_by": "jclervil@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Sumner County Board of Education",
        "agency_state": "TN",
        "agency_type": "State & Local",
        "agency_website": "https://sumnerschools.org",
        "index_url": "/about-us/departments/finance/invitation-to-bid",
        "row_sel": "div.fsElementContent table",
    }

    def fetch_rows(self):
      if self.status == "closed":
          return
      resp = self.get(self.settings["index_url"])
      if resp:
        # soup = bs(resp.text, "html5lib")
        for table in bs(resp.text, "html5lib").select(self.settings["row_sel"]):
                header = [tag_text(h) for h in table.select("thead th")]
                for row in table.select("tbody tr"):
                    bid_data = {**{header[n]: v for n, v in enumerate(row.select("td"))}, "doc": list(self.scrape_links(row))}
                    if tag_text(bid_data["Title / Description"]) == '':
                        return
                    yield bid_data
      else:
          logging.error(
              self.website_error_message, {"url": self.urljoin(self.settings["index_url"])}
          )


    def bid_id_from_row(self, row):
        data = str([tag_text(row["Project"]), tag_text(row["Title / Description"])])
        if data:
            return get_hash(data)

    def scrape_bid(self, bid, row):
        core.common.objects.set_obj_attributes(
                bid,
                row,
                {
                    "title": ("Title / Description", tag_text),
                    "dueDate": ("Due Date", lambda x: core.common.parse.parse_date((tag_text(x)) if tag_text(x) else "")),
                    "bidNumber": ("Project", tag_text),
                },
            )
        bid.sourceURL = bid.bidURL = self.urljoin(
            self.settings["index_url"] + "#" + clean_filename(bid.bidNumber)
        )
        bid.description = make_description_from_dict(py_.omit(row, "Pre-Bid Meeting", "Awarded Vendor"))
        return lambda: self.scrape_links(row["Project"])


if __name__ == "__main__":
    Main().run()

