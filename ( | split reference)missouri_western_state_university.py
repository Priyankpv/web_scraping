# RUN-FREQUENCY : { DAILY }
# RUN-LEVEL : { INFO }

import datetime
import logging
import re

from bs4 import BeautifulSoup as bs
from pydash import clean as _c

import core
from core.bid_scraper_plus import BidScraper
from core.common import datefmt, get_hash
from core.common import replace_non_ascii as _rp
from core.common import tag_text

findBid = re.compile(r"^[A-Z]+\d+\-\w+", re.I)
yest_date = (core.common.variables.today - datetime.timedelta(days=1)).strftime(datefmt)


class Main(BidScraper):
    settings = {
        "version": "1.0.2",
        "script_name": "missouri_western_state_university",
        "base_url": "https://www.missouriwestern.edu",
        "created_by": "jclervil@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Missouri Western State University",
        "agency_state": "MO",
        "agency_type": "State & Local",
        "agency_website": "https://www.missouriwestern.edu",
        "index_url": "/purchasing/current-bids/",
        "closed_url": "/purchasing/{}-closed-bids/",
        "row_sel": "section#content div > ul > li ",
    }

    def fetch_rows(self):
        if self.status == "open":
            res = self.get(self.settings["index_url"])
            if res:
                rows = bs(res.text, "html5lib").select(self.settings["row_sel"])
                if rows:
                    yield from [x for x in rows if x.select_one("a")]
            else:
                logging.error(
                    f'No content returned from the open index page...URL: {self.urljoin(self.settings["index_url"])}'
                )
        else:
            curYear = datetime.datetime.now().year
            for pg in range(4):
                self.theIndex = self.settings["closed_url"].format(curYear)
                res = self.get(self.theIndex)
                if res:
                    bidRows = bs(res.text, "html5lib").select(self.settings["row_sel"])
                    yield from [x for x in bidRows if x.select_one("a")]
                else:
                    logging.error(
                        f'No response from the closed index page...URL: {self.urljoin(self.settings["closed_url"])}'
                    )
                curYear -= 1

    def bid_id_from_row(self, row):
        self.rowText = tag_text(row)
        if self.rowText:
            return get_hash(self.rowText)

    def scrape_bid(self, bid, row):
        posted_date = re.search(r"Issued *(\d+[\/\-]\d+[\/\-]\d+)", self.rowText, re.I)
        if posted_date:
            bid.postedDate = core.parse_date(posted_date.group(1))
        rowSplit = self.rowText.split("|")
        if len(rowSplit) > 1:
            dd = re.search(r"(?:opens)? *\|?\d+[\/\-]\d+[\/\-]\d+", rowSplit[-1], re.I)
            if dd:
                bid.dueDate = core.parse_date(rowSplit[-1].replace('Opens','')) if 'Opens' in rowSplit[-1] else core.parse_date(rowSplit[-1])
                bid.title = bid.description = _rp(_c(rowSplit[-2]))
                if re.match(r"(Bid)? *Results| *\d+[\/\-]\d+[\/\-]\d+ *", bid.title, flags=re.I):
                    bid.title = bid.description = re.sub(
                        r" *(opens)? *\|?\d+[\/\-]\d+[\/\-]\d+",
                        "",
                        rowSplit[-1],
                        flags=re.I,
                    )
            else:
                bid.title = bid.description = _rp(_c(rowSplit[-1]))
                if self.status == "closed":
                    bid.dueDate = yest_date
                elif bid.postedDate:
                    bid.set_default_due_date(starting_from=bid.postedDate)
                else:
                    bid.set_default_due_date()
        bidNum = findBid.search(self.rowText)
        if bidNum:
            bid.bidNumber = bidNum.group()
        if self.status == "open":
            bid.sourceURL = bid.bidURL = self.urljoin(
                f"{self.settings['index_url']}#{bid.bidNumber}"
            )
        else:
            bid.sourceURL = bid.bidURL = self.urljoin(f"{self.theIndex}#{bid.bidNumber}")
        return lambda: self.scrape_links(row)


if __name__ == "__main__":
    Main().run()

