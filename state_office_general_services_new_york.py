import logging
from pathlib import Path
from common.text_utils import get_hash
from bs4 import BeautifulSoup as bs
from pydash import py_

import core
from common.misc import tag_text
from common.requests import parse_remote_file_name, stream_response_to_file
from core.bid_scraper_plus import BidScraper
import re


class Main(BidScraper):
    settings = {
        "version": "1.0.4",
        "script_name": "state_office_general_services_new_york",
        "base_url": "https://ogs.ny.gov",
        "created_by": "dparisi@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "New York State Office of General Services - Procurement Services",
        "agency_state": "NY",
        "agency_type": "State & Local",
        "row_sel": {
            "open": {"/procurement/bid-opportunities": "div[class^='wysiwyg'] > table > tbody > tr:nth-of-type(2)","/23295bid":".layout-content","/23308Bid":".layout-content"},
            "closed": "div[class^='wysiwyg'] > table > tbody > tr",
        },
    }

    def fetch_rows(self):
        self.index_url = (
            ["/23308Bid","/procurement/bid-opportunities","/23295bid"]
            if self.status == "open"
            else ["/procurement/bid-opening-results-0"]
        )
        for self.link in self.index_url:
          if self.status == "open":
            yield from bs(self.get(self.link).text, "html5lib").select(self.settings["row_sel"][self.status][self.link])
          else:        
            yield from bs(self.get(self.link).text, "html5lib").select(
                self.settings["row_sel"][self.status]
            )

    def bid_id_from_row(self, row):
       text = tag_text(row['row'])
       if text: return get_hash(text)
        # if self.link == '/23308Bid' or self.link == '/23295bid':
        #    self.bid_re = re.search(r'Group\s(\d+)\s\W\s(.+)\s(IFB\s\d+)',tag_text(row.select("h6")[0]))
        #    return self.bid_re.group(3) + "-" + self.bid_re.group(1)
        # else:
        #   if not tag_text(row.select("td")[-1]):
        #     return tag_text(row.select("td")[2])
        #   return tag_text(row.select("td")[2]) + " - " + tag_text(row.select("td")[-1])

    empty_tag = bs("<div></div>", "html5lib")

    def scrape_bid(self, bid, row):
        if self.link == '/23308Bid' or self.link == '/23295bid':
           bid.title = bid.description = self.bid_re.group(2)
           bid.dueDate = core.parse_date(re.search(r'no later than .+on\s(\w+\s\d+\,\s\d+)',tag_text(row.select("p")[1])).group(1))
           bid.sourceURL = self.urljoin(f"{self.link}#{bid.bidNumber}")
           return lambda: self.scrape_links(row)
        else:
          bid.title = bid.description = tag_text(row.a)
          bid.dueDate = core.parse_date(tag_text(row.select("td")[1]))
          surl = py_.get(row, "a.href", "").strip("/ ")
          resp = self.get(surl)
          if "text/html" in py_.get(resp, "headers.Content-Type", ""):
              bid.sourceURL = self.urljoin(surl)
              if self.settings["document_download"]:
                  bid_page = bs(resp.text, "html5lib")
                  return lambda: self.scrape_links(
                      bid_page.select_one("div.page-body") or self.empty_tag
                  )
          else:
              bid.sourceURL = self.urljoin(f"{self.link}#{bid.bidNumber}")
              if self.settings["document_download"] and resp:
                  bid.set_documents_subfolder()
                  dldir = Path(self.directories["documents"]) / bid.documentsSubFolder
                  dldir.mkdir(exist_ok=True)
                  fname = parse_remote_file_name(resp)
                  if fname:
                      filepath = stream_response_to_file(resp, dldir / fname)
                      if filepath:
                          logging.info('Downloaded "%s"', filepath)


if __name__ == "__main__":
    Main().run()

