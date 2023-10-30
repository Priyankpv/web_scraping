import logging
from bs4 import BeautifulSoup as bs
from pydash import py_
import core
from core.bid_scraper_plus import BidScraper
from core.common import _tt, get_hash, tag_text
import re


class Main(BidScraper):
    settings = {
        "version": "1.0.0",
        "script_name": "grand_river_dam_authority",
        "created_by": "pvamja@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Grand River Dam Authority",
        "agency_state": "OK",
        "agency_type": "State & Local",
        "base_url": "https://www.grda.com",
        "agency_website": "https://www.grda.com",
        "index_url": "/purchasing/bid-list/?wpv_column_sort_id=types-field-bid-status&wpv_column_sort_dir=desc&wpv_view_count=1&bid=&bid=&wpv_paged={}",
        "row_sel": ".post-content table tr",
    }

    def fetch_rows(self):
        if self.status == "closed": return

        if resp := self.get(self.settings["index_url"].format('1')):
          page_sel = bs(resp.text,"html5lib").select_one(".post-content  p:has(#wpv-page-selector-1)")
          total_pg = int(py_.clean(page_sel.find_all(text=True,recursive = False)[-1]).split(' ')[-1])
          for pg in range(1,total_pg+1):
            if resp := self.get(self.settings["index_url"].format(pg)):
              rows = bs(resp.text, "html5lib").select(self.settings["row_sel"])
              header, *rows = rows
              header = [tag_text(h) for h in header.select("th")]
              for row in rows:
                  row_dict = {header[n]: _tt(cell) for n, cell in enumerate(row.select("td"))}
                  row_dict["link"] = row.select_one("td a").get("href")
                  yield row_dict
            else:
                logging.error(
                    "No response from index page: %s", self.urljoin(self.settings["index_url"].format(pg))
                )
                return
        else:
          logging.error(
              "No response from index page: %s", self.urljoin(self.settings["index_url"].format('1'))
          )
          return

    def bid_id_from_row(self, row):
            return get_hash(str(row))

    def scrape_bid(self, bid, row):        
        bid.sourceURL = bid.bidURL = row['link']                                                     
        if bid_resp := self.get(row["link"]):
            bid_doc = bs(bid_resp.text, "html5lib")
            bid_link = bid_doc.select(".post-content p a[href*='.pdf']")
            row['desc'] = row["Description"]+tag_text(bid_doc.select_one(".post-wrap"))
            if not row['Closing Date']:
              if dd:= re.search(r'due\s(\w+\s?\d+\,\s?\d{4})', row['desc']):
                  row['Closing Date'] = dd.group(1)
        else:
            row['desc'] = row["Description"]
        core.set_bid_attributes(
            bid,
            row,
            {
                "title": "Description",
                "description": "desc",
                "bidNumber": "Bid Link",
                "dueDate": ("Closing Date", core.parse_date),
                "postedDate": ("Posted Date", core.parse_date),
                "awardedDate": ("Awarded Date",lambda ad:core.parse_date(ad) if ad else ""),
            },
        )

        # if bid_link:
        #     return lambda: [i.get("href") for i in bid_link]


if __name__ == "__main__":
    Main().run()

