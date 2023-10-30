import logging
import re
from datetime import datetime
from pydash import py_
import pdftotext
from bs4 import BeautifulSoup as bs
from pydash import arrays as _arrays
from pydash import clean as _c
from pydash import get as _g
from core.bid_scraper_plus import BidScraper, SkipBid
import core
from core.bid_scraper_plus import BidScraper
from core.common import get_hash, long_re_date, tag_text, clean_filename

_tt = lambda x: _c(tag_text(x))
regexes = "|".join(
    [
        r"Date and Time Due:\s?",
        r"SUBMISSION DEADLINE:\s?",
        r"Responses must be received on or before[ \w\:\.]*\,?\s?[\w]*\,?\s?",
        r"must be received on or before[ \w\:\.]*\,?\s?[\w]*\,?\s?",
        r"DUE DATE:[ \w\:\.]*\,?\s?[\w]*\,?\s?",
        r"accepting proposals.+until[ \w\:\.]*\,?\s?[\w]*\,?\s?",
    ]
)
date_re = re.compile(f"(?:{regexes})" + long_re_date, re.I)
def get_date_from_files(bid, fileinfos):
    dump = ""
    if fileinfos.path:
        try:
            if fileinfos.path.endswith(".pdf"):
                dump = pdftotext.PDF(open(fileinfos.path, "rb"))
            else:
                logging.info(f"Could not dump file format: ({fileinfos.ext})")
            dump = py_.clean(" ".join(dump))
        except Exception as ex:
            raise SkipBid(f"Error dumping file to text! Exception: {ex} FILE_URL: {dl.url}")
        if dump:
            if fddate := date_re.search(dump):
                dump = dump[:997] + "..." if len(dump) > 1000 else dump
                return (core.parse_date(fddate.group(1)), dump)
    # else:
    #     logging.info(f"File could not be downloaded. FILE_URL: {fileinfos.url}")


class Main(BidScraper):
    settings = {
        "version": "1.0.3",
        "script_name": "city_santa_maria",
        "base_url": "https://www.cityofsantamaria.org",
        "created_by": "jedmonson@govspend.com",
        "last_modified_by": "dparisi@govspend.com",
        "agency_name": "City of Santa Maria",
        "agency_state": "CA",
        "agency_type": "State & Local",
        "agency_website": "https://www.cityofsantamaria.org",
        "index_url": "/bids",
        "row_sel": "#widget_4_2305_2640 p a[href^='https://www.cityofsantamaria.org/']"
    }

    def fetch_rows(self):
      if self.status == 'closed': return 
      resp = self.get(self.settings['index_url'])
      if resp:
        for row in bs(resp.text, 'html5lib').select(self.settings['row_sel']):
          yield {
            'row': row
          }
      else:
        logging.error('No response from index page: %s', self.urljoin(self.settings['index_url']))
        return 

    def bid_id_from_row(self, row):
      text = tag_text(row['row'])
      if text: return get_hash(text)

    def scrape_bid(self, bid, row):
      bid.title = tag_text(row['row'])
      # files =  self.download_files(list(self.scrape_links(row['row'])), bid)
      files = self.download_file(bid, row['row'].get('href'))
      bid.sourceURL = bid.bidURL = self.urljoin(self.settings['index_url']+"#"+clean_filename(bid.bidNumber))
      dd = get_date_from_files(bid, files)
      if dd:
        bid.dueDate, desc = dd
        bid.description = f"<h3>{bid.title}</h3><br>{py_.clean(desc)}"
      else:
        raise SkipBid(f"Could not find bid details for URL: {bid.sourceURL}")


if __name__ == "__main__":
    Main().run()

