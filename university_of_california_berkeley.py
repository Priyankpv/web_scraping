from pydash import py_
from bs4 import BeautifulSoup as bs
from urllib.parse import urlparse
import core
from core.bid_scraper_plus import BidScraper
from core.common import get_hash, tag_text
from core.common.frameworks.google_drive import get_direct_download_url


class Main(BidScraper):
    settings = {
        "version": "1.0.0",
        "base_url": "https://capitalstrategies.berkeley.edu",
        "script_name": "university_of_california_berkeley",
        "created_by": "bsinghsolanki@govspend.com",
        "last_modified_by": "bsinghsolanki@govspend.com",
        "agency_name": "University of California-Berkeley",
        "agency_state": "CA",
        "agency_type": "State & Local",
        "agency_website": "https://capitalstrategies.berkeley.edu",
        "index_url": ["/current-bids", "/rfq", "/bid-results"],
        "row_sel": ".field-item.even > h3~table > tbody > tr",
        "headers_sel":"div > table > thead > tr",
        "filter_rows": lambda x: _c(tag_text(x))
        and not any(i in str(x) for i in ["Event Type", "UCH #", "Due Date"]),
    }


    def fetch_rows(self):
      self.session.verify = False
      data = []
      for self.url in self.settings["index_url"]:
        if resp := self.get(self.url):
          soup = bs(resp.text, "html5lib")
          open_rows = soup.select(self.settings["row_sel"])
          headers = soup.select(self.settings["row_sel"])[0]
          for row in open_rows[1:]:
              info = {**{tag_text(k):tag_text(v) for k,v in zip ( headers.select('td'),row.select("td"))}, "pdf_urls": list(self.scrape_links(row))}
              data.append(info)
          yield from data

    def bid_id_from_row(self, data):
        
        return get_hash(data["Project Name"],data['Number'])

    def scrape_bid(self, bid, data):
        core.common.objects.set_bid_attributes(
            bid,
            data,
            {
                "title": "Project Name",
                "dueDate": ("Due", core.common.parse.parse_date),
                "bidNumber": "Number",
            },
        )
        
        bid.description = core.common.make_description_from_dict(py_.omit(data,'pdf_urls'))
        bid.sourceURL = f"{urlparse(self.settings['base_url']).netloc}#{bid.sourceID}"
        for url in data['pdf_urls']:

          pdf_url = get_direct_download_url(url[1])

          self.download_file(bid,pdf_url)
          


if __name__ == "__main__":
    Main().run()
