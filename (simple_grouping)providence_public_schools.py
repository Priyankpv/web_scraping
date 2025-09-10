import datetime
import logging
import re

from bs4 import BeautifulSoup as bs
from pydash import clean as _c
from pydash import get as _g

import core
from core.bid_scraper_plus import BidScraper
from core.common import datefmt, get_hash, long_re_date

yest_date = (core.common.variables.today - datetime.timedelta(days=1)).strftime(datefmt)
_tt = lambda x: _c(_g(x, "text"))


class Main(BidScraper):
    settings = {
        "version": "1.0.1",
        "script_name": "providence_public_schools",
        "base_url": "https://www.providenceschools.org",
        "created_by": "jclervil@govspend.com",
        "last_modified_by": "jclervil@govspend.com",
        "agency_name": "Providence Public Schools",
        "agency_state": "RI",
        "agency_type": "State & Local",
        "agency_website": "https://www.providenceschools.org",
        "index_urls": {
            "open": ("/Page/4633", "div.layoutArea div.column a"),
            "closed": ("/Page/4634", 'a[href*="cms/lib"]'),
        },
        "row_sel": "div.ui-article-description > span > span > p",
    }

    def fetch_rows(self):
        url, sel = self.settings["index_urls"][self.status]
        res = self.get(url)
        if not res:
            logging.error(self.website_error_message,{"url":self.urljoin(url)})
        rows = bs(res.text, "html5lib").select(sel)
        for n, row in enumerate(rows):
            if _tt(row):
                if "ddend" in _tt(row):
                    continue
                temp = {"title": _tt(row), "files": [row.get("href")], "url": url}
                for x in rows[n + 1 :]:
                    if _tt(x) and "ddend" in _tt(x):
                        temp["files"].append(x.get("href"))
                    else:
                        break
                previous_tag = row.find_previous(text=re.compile(r"bids? due.+", re.I))
                date_tag = re.search(long_re_date, previous_tag if previous_tag else "", re.I)
                temp["dd"] = (
                    core.common.parse.parse_date(date_tag.group()) if date_tag else yest_date
                )
                yield temp

    def bid_id_from_row(self, row):
        if any(row.values()):
            return get_hash(str(row))

    def scrape_bid(self, bid, row):
        core.common.objects.set_bid_attributes(
            bid, row, {"title": "title", "dueDate": "dd", "description": "title"}
        )
        bid.sourceURL = self.urljoin(f'{row["url"]}#{bid.bidNumber}')
        return lambda: row["files"]


if __name__ == "__main__":
    Main().run()

