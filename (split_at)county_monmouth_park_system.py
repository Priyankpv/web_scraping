import logging
import re

from bs4 import BeautifulSoup as bs
from pydash import py_
import core
from common.misc import tag_text, split_at, dict_key_by_regex
from common.text_utils import get_hash, modify_html
from core.bid_scraper_plus import BidScraper
from w3lib.html import remove_tags

class Main(BidScraper):
    settings = {
        "version": "1.1.4",
        "script_name": "county_monmouth_park_system",
        "base_url": "https://www.monmouthcountyparks.com",
        "created_by": "bpolonia@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Monmouth County Park System",
        "agency_website": "https://www.monmouthcountyparks.com",
        "agency_state": "NJ",
        "agency_type": "State & Local",
        "index_url": {
            'open' : ['/page.aspx?ID=2821','/page.aspx?ID=2823','/page.aspx?ID=2824'],
            'closed' : ['/page.aspx?ID=2820']
        }
    }

    def fetch_rows(self):
        def combine_soup(tags):
          s = bs("<div></div>", "html5lib").div
          [s.insert(0, x) for x in tags[::-1]]
          return s
        
        for i in self.settings["index_url"][self.status]:
            resp = self.get(i)
            if resp:
                soup = bs(resp.text, "html5lib")
                if i == '/page.aspx?ID=2823':
                   page_info = py_.tail(list(map(combine_soup,list(split_at(lambda x :x.name == 'a',soup.select_one('.article-block > p'),include='second')))))
                   for links in page_info:
                       yield{'links' : links,
                             'url': i}
                else:
                  head,*bid_dic = soup.select("table tr")
                  for links in bid_dic:
                      yield {'links' : links,
                            'head' : head,
                            'url' : i}
                
            else: 
                logging.error(
                    "No response from index page %s", self.urljoin(self.settings["index_url"])
                )

    def bid_id_from_row(self, rows):
            return get_hash(tag_text(rows['links']))

    def scrape_bid(self, bid, rows):
        if rows['url'] == '/page.aspx?ID=2824' or rows['url'] == '/page.aspx?ID=2821' or rows['url'] == '/page.aspx?ID=2820':
          data_dict={tag_text(h_):td_ for h_,td_ in zip(rows['head'].select('td,th'),rows['links'].select('td'))}
          desc = modify_html(data_dict[dict_key_by_regex(r'BID NAME|TITLE',data_dict)])
          bid.dueDate = core.parse_date(tag_text(data_dict[dict_key_by_regex(r'OPENING DATE',data_dict)]))
          bid.description = str(desc)
          if rows['url'] == '/page.aspx?ID=2824':
              bid.title = py_.clean(tag_text(desc))
              bid.bidNumber = re.search(r"(Bid\s?#\d+-\d+)",tag_text(desc)).group(1)
          elif rows['url'] == '/page.aspx?ID=2821':
              if re.search(r'(.+) (AWARDED|Bid|No|ALL)',tag_text(desc)):
                bid.title = py_.clean((re.search(r'(.+) (AWARDED|Bid|No|ALL)',tag_text(desc))).group(1))
              else:
                 bid.title = py_.clean(tag_text(desc))
              bid.bidNumber = tag_text(data_dict['BID NUMBER'])
              if re.search(r"AWARDED VENDOR:\s?(.+)", tag_text(desc)) != None: 
                bid.awardedTo = re.search(r"AWARDED VENDOR:\s?(.+)", tag_text(desc)).group(1)
          elif rows['url'] == '/page.aspx?ID=2820':
              bid.title = py_.clean(tag_text(desc))
              bid.bidNumber = tag_text(data_dict['PROPOSAL NUMBER'])
              bid.awardedTo = tag_text(data_dict['AWARDED VENDOR'])
        else:
          desc = modify_html(rows['links'])
          bid.dueDate = core.parse_date(re.search(rf'Due on or before\s(\w+\,\s\w+\s\d+\,\s\d+)',tag_text(desc)).group(1))
          bid.title = py_.clean(re.search(r'Project:(.+),\sInterest',tag_text(desc)).group(1))
          bid.bidNumber = re.search(r'(\w+\#\d+\-\d+)',tag_text(desc)).group(1)
          bid.description = str(desc)
        bid.sourceURL = self.urljoin(rows['url'] + "#" + bid.sourceID)   
        # return lambda: self.scrape_links(rows['links'])


if __name__ == "__main__":
    Main().run()

