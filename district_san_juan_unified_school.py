import logging
import re
from collections import defaultdict

import pdftotext
from bs4 import BeautifulSoup as bs
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper, SkipBid
from core.common import _tt, get_hash, long_re_date

date_re = re.compile(rf"(?:RFPs|Bids) must be submitted by\:?\s?{long_re_date}", re.I)


def get_date_from_files(bid, fileinfos):
    for dl in fileinfos:
        dump = ""
        if dl.path:
            try:
                if dl.path.endswith(".pdf"):
                    dump = pdftotext.PDF(open(dl.path, "rb"))
                else:
                    logging.info(f"Could not dump file format: ({dl.ext})")
                dump = py_.clean(" ".join(dump))
            except Exception as ex:
                raise SkipBid(f"Error dumping file to text! Exception: {ex} FILE_URL: {dl.url}")
            if dump:
                if fddate := date_re.search(dump):
                    dump = dump[:997] + "..." if len(dump) > 1000 else dump
                    return (core.parse_date(fddate.group(1)), dump)
        else:
            logging.info(f"File could not be downloaded. FILE_URL: {dl.url}")


class Main(BidScraper):
    settings = {
        "version": "1.0.3",
        "script_name": "district_san_juan_unified_school",
        "base_url": "https://www.sanjuan.edu",
        "created_by": "jclervil@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "San Juan Unified School District",
        "agency_state": "CA",
        "agency_type": "State & Local",
        "agency_website": "https://www.sanjuan.edu",
        "index_url": "/our-district/contracts-and-bids/other-services-contracts-and-bids/bidrfp-files",
        "row_sel": "div.fsElementContent p a",
    }

    def fetch_rows(self):
        if self.status == "closed":
            return
        if res := self.get(self.settings["index_url"]):
            self.bid_rows = bs(res.text, "html5lib").select(self.settings["row_sel"])
            grouped_documents = defaultdict(list)
            for i in self.bid_rows:
                match = re.search(r"(?:RFP|Bid)\s?(\d{2}\-\d+)", _tt(i))
                if match:
                    rfp_number = match.group(1)
                    grouped_documents[rfp_number].append(i)
            result = [{rfp: docs} for rfp, docs in grouped_documents.items()]
            yield from result

        else:
            logging.error(
               self.website_error_message,{"url":self.urljoin(self.settings["index_url"])}
            )

    def bid_id_from_row(self, row):
        if row.keys():
            return get_hash(list(row.keys())[0])

    def scrape_bid(self, bid, row):
        bid.bidNumber = list(row.keys())[0]
        bid.title = _tt(row[bid.bidNumber][0])
        doc_list = [("", str(i.get("href"))) for i in row[bid.bidNumber]]
        files = self.download_files(doc_list, bid)
        if dd := get_date_from_files(bid, files):
            bid.dueDate, desc = dd
            bid.description = f"<h3>{bid.title}</h3><br>{py_.clean(desc)}"
        bid.sourceURL = bid.bidURL = self.urljoin(self.settings["index_url"]) + "#" + bid.bidNumber


if __name__ == "__main__":
    Main().run()

