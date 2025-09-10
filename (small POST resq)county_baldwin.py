import logging
from bs4 import BeautifulSoup as bs
from pydash import py_
from core.common import _tt, get_hash, parse_date, make_description_from_obj
from core.bid_scraper_plus import BidScraper


class Main(BidScraper):
    settings = {
        "version": "1.0.2",
        "script_name": "county_baldwin",
        "base_url": "https://open.baldwincountyal.gov",
        "created_by": "dparisi@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Baldwin County",
        "agency_state": "AL",
        "agency_type": "State & Local",
        "index_url": "/BidsVendor/",
    }

    def fetch_rows(self):
        if self.status == "closed":
            return
        bid_page = self.get(self.settings["index_url"])
        if bid_page:
            bid_page_url = self.urljoin(self.settings["index_url"]+"BidsTable/Read/0")
            if bid_json_res := self.post(bid_page_url):
              bid_id_json = bid_json_res.json()
              for data in bid_id_json["Data"]:
                bid_resp = self.post(self.urljoin(self.settings["index_url"])+"BidAttachments/Read/"+str(data["Id"]))
                bid_json = bid_resp.json()
                data["doc"] = [self.urljoin(self.settings["base_url"]+"/BidsDoc/Doc/"+i["FileName"])for i in bid_json["Data"]]
                data["bid_url"] = self.urljoin(self.settings["index_url"]+"Bids/Details?id="+str(data["Id"]))
                bid_detail_res = self.get(data["bid_url"]) 
                bid_soup = bs(bid_detail_res.text, "html5lib").select_one(".col-sm-8:nth-of-type(15)")
                data["detail"] = _tt(bid_soup)
                yield data
            else:
                logging.error(
                  "No post response from bid page url: %s",
                  self.urljoin(bid_page_url),
              )
        else:
              logging.error(
                  "No post response from index url: %s",
                  self.urljoin(self.settings["index_url"]),
              )

    def bid_id_from_row(self, row):
        return get_hash(str(row["BidNumber"]))

    def scrape_bid(self, bid, row):
        bid.bidURL = bid.sourceURL = row["bid_url"]
        bid.title = py_.clean(row["BidTitle"])
        b_no = row["BidNumber"].split("#")
        bid.bidNumber = b_no[1] if len(b_no) > 1 else bid.sourceID
        bid.postedDate = parse_date(row["BeginDate"])
        bid.dueDate = parse_date(row["CloseDate"])
        bid.description = make_description_from_obj(row["detail"])
        return lambda: row["doc"]


if __name__ == "__main__":
    Main().run()

