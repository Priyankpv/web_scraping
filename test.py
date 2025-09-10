import re

import dateutil.parser as dparser
from bs4 import BeautifulSoup as BS
from pydash import strings

import core
from core.bid_scraper_plus import BidScraper
from core.common import get_hash

today = core.common.variables.today


class Main(BidScraper):
    settings = {
        "version": "1.0.1",
        "script_name": "spokane_public_schools",
        "base_url": "https://www.spokaneschools.org",
        "created_by": "bpolonia@govspend.com",
        "last_modified_by": "jedmonson@govspend.com",
        "agency_name": "Spokane Public Schools",
        "agency_state": "WA",
        "agency_type": "State & Local",
        "agency_website": "https://www.spokaneschools.org",
        "index_url": "/Page/1035",
    }

    def pre_execute(self):
        self.pattern1 = re.compile(r"(Bid|RFP|RFQ|Quote)\s(No.)?\s?\d+\-\d+\s(-|–)\s")
        self.pattern2 = re.compile(r"(Bid|RFP|RFQ|Quote)\s(No.)?\s?\d+\-\d+.?\s")
        resp = self.get(self.settings["index_url"])
        soup = BS(resp.text, "html5lib")
        self.rows = soup.select(
            "div#module-content-1443 > div > div.ui-widget-detail > ul > li > div > div > span > span > ul > li"
        )
        sec_resp = self.get("/Page/1034")
        sec_soup = BS(sec_resp.text, "html5lib")
        self.sec_rows = sec_soup.select("div#accordion-container-10217 > div")

    def fetch_rows(self):
        for bids in self.rows:
            row = strings.clean(bids.text)
            if self.pattern1.search(row) is not None:
                wBid = self.parse_row(row, bids)
                self.previousDate = wBid["date"]
                wBid["pattern"] = 1
                wBid["page"] = 1
                date = dparser.parse(wBid["date"])
                if date >= today and self.status == "open":
                    yield wBid
                elif date < today and self.status == "closed":
                    yield wBid
            elif self.pattern2.search(row) is not None:
                wBid = self.parse_row(row, bids)
                wBid["pattern"] = 2
                wBid["page"] = 1
                date = dparser.parse(wBid["date"])
                if date >= today and self.status == "open":
                    yield wBid
                elif date < today and self.status == "closed":
                    yield wBid

        for sec_bids in self.sec_rows:
            for bids in sec_bids.select("ul > li"):
                row = strings.clean(bids.text)
                if self.pattern1.search(row) is not None:
                    wBid = self.parse_row(row, bids)
                    wBid["pattern"] = 1
                    wBid["page"] = 2
                    date = dparser.parse(wBid["date"])
                    if date >= today and self.status == "open":
                        yield wBid
                    elif date < today and self.status == "closed":
                        yield wBid
                elif self.pattern2.search(row) is not None:
                    wBid = self.parse_row(row, bids)
                    wBid["pattern"] = 2
                    wBid["page"] = 2
                    date = dparser.parse(wBid["date"])
                    if date >= today and self.status == "open":
                        yield wBid
                    elif date < today and self.status == "closed":
                        yield wBid
                else:
                    continue

    def parse_row(self, bid, row):
        if re.search(r"\w+\s\d+,\s\d+", bid):
            date = core.common.parse.parse_date(re.search(r"\w+\s\d+,\s\d+", bid).group(0))
        elif re.search(r"\w+\s\d+,\d+", bid):
            predate = re.search(r"\w+\s\d+,\d+", bid).group(0)
            date = core.common.parse.parse_date(re.sub(",", ", ", predate))
        elif re.search(r"\w+,\s\d+", bid) is None:
            date = self.previousDate
        else:
            date = core.common.parse.parse_date(re.search(r"\w+,\s\d+", bid).group(0))
        number = re.search(r"\d+\-\d+", bid).group(0)
        wBid = {"date": date, "number": number, "description": bid, "download": row}
        return wBid

    @staticmethod
    def bid_id_from_row(bid_table):
        return get_hash(strings.clean(bid_table["description"]))

    def scrape_bid(self, bid, bid_table):
        bid.agencyWebsite = self.settings["base_url"]
        bid.bidNumber = bid_table["number"]
        if bid_table["page"] == 1:
            bid.sourceURL = self.urljoin(self.settings["index_url"] + "#" + bid.bidNumber)
        elif bid_table["page"] == 2:
            bid.sourceURL = self.urljoin("/Page/1034" + "#" + bid.bidNumber)
        bid.dueDate = bid_table["date"]
        bid.description = re.split(r"\s\(.+", bid_table["description"])[0]
        if bid_table["pattern"] == 1:
            title = self.pattern1.split(bid_table["description"])[4]
            bid.title = re.split(r"\s\((D|d)ue\s.+", title)[0]
        else:
            title = self.pattern2.split(bid_table["description"])[3]
            bid.title = re.split(r"\s\((D|d)ue\s.+", title)[0]
        urls = list(self.scrape_links(bid_table["download"]))
        for url in urls:
            if re.search("publicpurchase", url[1]) is not None:
                urls.remove(url)
            else:
                pass
        return lambda: urls


if __name__ == "__main__":
    Main().run()

