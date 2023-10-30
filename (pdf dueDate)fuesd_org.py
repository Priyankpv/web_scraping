from bs4 import BeautifulSoup as bs
from common.text_utils import get_hash, clean_filename, long_re_date
from core.bid_scraper_plus import BidScraper
from common.misc import tag_text
import core, logging, re
import pydash as py_
import pdftotext
from core.bid_scraper_plus import BidScraper, SkipBid

date_re = re.compile(rf'Proposals Due:\W(?:.*?day)?\W?{long_re_date}',re.I)
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
    'version':          '1.0.0',
    'script_name':      'fuesd_org',
    'created_by':       'pvamja@govspend.com',
    'last_modified_by': 'pvamja@govspend.com',
    'agency_name':      'Fallbrook Union Elementary School District',
    'agency_state':     'CA',
    'agency_type':      'State & Local',
    'base_url':         'https://www.fuesd.org/',
    'agency_website':   'https://www.fuesd.org/',
    'index_url':        'proposals/',
    'row_sel':          '.et_pb_specialty_column .et_pb_column'
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
    bid.title = tag_text(row['row'].select_one(self.settings['row_sel'] + ' .et_pb_text_inner h3'))
    bid.bidNumber = py_.clean(re.search(r'(RFP\s\#?\d+\-\d+\-\d+)',bid.title).group(1))
    files =  self.download_files(list(self.scrape_links(row['row'])), bid)
    bid.sourceURL = bid.bidURL = self.urljoin(self.settings['index_url']+"#"+clean_filename(bid.bidNumber))
    dd = get_date_from_files(bid, files)
    if dd:
       bid.dueDate, desc = dd
       bid.description = f"<h3>{bid.title}</h3><br>{py_.clean(desc)}"
    else:
       raise SkipBid(f"Could not find bid details for URL: {bid.sourceURL}")

    


if __name__ == '__main__': Main().run()
