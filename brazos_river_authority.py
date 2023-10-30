import logging
import re

from bs4 import BeautifulSoup as bs

import core
from core.bid_scraper_plus import BidScraper
from core.common import get_hash, parse_date, tag_text
from core.common.file_download import clean_filename


class Main(BidScraper):
    settings = {
        "version": "1.1.2",
        "script_name": "brazos_river_authority",
        "created_by": "jalbu@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Brazos River Authority",
        "agency_state": "TX",
        "agency_type": "State & Local",
        "base_url": "https://brazos.org",
        "agency_website": "https://brazos.org",
        "index_url": {
            "bids": "/Doing-Business/Purchasing-Professional-Services/Request-for-Bids",
            "proposals": "/Doing-Business/Purchasing-Professional-Services/Request-for-Proposals",
        },
        "row_sel": ".contentpane .boxes_style_1",
    }

    def fetch_rows(self):
        if self.status == "closed":
            return
        self.session.verify = False
        for page in self.settings["index_url"]:
            bid_page = self.get(self.settings["index_url"][page])
            if bid_page:
                for row in bs(bid_page.text, "html5lib").select(self.settings["row_sel"]):
                    data_dict = {
                        tag_text(_tag.select_one("b").extract()).lower().strip(): tag_text(_tag)
                        for _tag in [_gt for _gt in row.select(".col-sm-6") if _gt.select_one("b")]
                    }
                    data_dict["bid_num"] = tag_text(row.select_one(".row h2"))
                    data_dict["url"] = self.settings["index_url"][page]
                    data_dict["links"] = row.select("a[href$='.pdf']")
                    yield data_dict
            else:
                logging.error(
                    "No reponse from index page %s",
                    self.urljoin(self.settings["index_url"][page]),
                )

    def bid_id_from_row(self, row):
        return get_hash(row["bid_num"])

    def scrape_bid(self, bid, row):
        bid_re = re.search(r"(?P<bidNumber>.+\d{2}-\d{2}-\d{4}) (?P<title>.+)", row["bid_num"])
        temp_bid_data = bid_re.groupdict() if bid_re else {}
        core.set_obj_attributes(bid, temp_bid_data, {i: i for i in temp_bid_data})
        bid.dueDate = parse_date(row["closing date:"])
        bid.postedDate = parse_date(row["date posted:"])
        bid.description = core.make_description_from_obj(row["description:"])
        bid.sourceURL = self.urljoin(row["url"] + "#" + clean_filename(bid.bidNumber))
        if row["links"]:
            return lambda: [i.get("href") for i in row["links"]]


if __name__ == "__main__":
    Main().run()
