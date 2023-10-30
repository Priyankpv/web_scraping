import logging
import re

import pdftotext
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper
from core.common import _tt, clean_filename, get_hash, tag_text

bid_re = re.compile(r"(\w+\d+\-\d{3})", re.I)


def get_date_from_files(fileinfos):
    for n, dl in enumerate(fileinfos):
        dump = ""
        if not dl.path:
            continue
        try:
            with open(dl.path, "rb") as fp:
                dump = pdftotext.PDF(fp)
        except Exception as ex:
            logging.info(f"Error dumping file to text! Exception: {ex} FILE_URL: {dl.url}")
            continue
        dump = py_.clean(" ".join(dump))
        if not dump:
            logging.info(f"No text in dump (Likely a scanned doc) FILE_URL: {dl.url}")
            continue
        fddate = re.search(r"(\w*\s\d*\,\s?\d{4})", dump)
        if not fddate:
            logging.info("could not find date in file")
            continue
        else:
            if len(dump) > 1000:
                dump = dump[:997] + "..."
            return (core.parse_date(fddate.group(1)), dump)


class Main(BidScraper):
    settings = {
        "version": "1.0.1",
        "script_name": "city_lawton",
        "created_by": "pvamja@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "city of lawton",
        "agency_state": "OK",
        "agency_type": "State & Local",
        "base_url": "https://www.lawtonok.gov",
        "agency_website": "https://www.lawtonok.gov",
        "index_url": "/departments/city-clerk/bid-items",
        "row_sel": "div.card.bs4-card-accordion.panel",
    }

    def fetch_rows(self):
        if self.status == "closed":
            return
        resp_soup = self.get(self.settings["index_url"], soup=True)
        link_list = {
            (_tt(i).split(" "))[0]: i
            for i in resp_soup.select(".container > .row  .py-3 .file-link a")
        }
        list_1 = link_list.copy()
        if resp_soup:
            for row in resp_soup.select(self.settings["row_sel"]):
                for i in list_1:
                    if i in _tt(row):
                        if i in link_list:link_list.pop(i)
                        doc_flag = True
                        break
                if doc_flag:
                    yield {"row": row, "link": list_1[i], "get_bid": "direct"}
                else:
                    yield {"row": row, "link": "", "get_bid": "direct"}
            for k, v in link_list.items():
                yield {"row": k, "link": v, "get_bid": "pdf"}
        else:
            logging.error(
                "No response from index page: %s", self.urljoin(self.settings["index_url"])
            )

    def bid_id_from_row(self, row):
        return get_hash(str(row["row"]))

    def scrape_bid(self, bid, row):
        if row["get_bid"] == "pdf":
            doc_link = [("", row["link"].get("href"))]
            fileinfo = self.download_files(doc_link, bid)
            d_date, desc = get_date_from_files(fileinfo)
            bid.title = _tt(row["link"]).split(".")[0]
            bid.bidNumber = (
                bid_re.search(_tt(row["link"])).group(1)
                if bid_re.search(_tt(row["link"]))
                else bid.sourceID
            )
            bid.dueDate = d_date
            bid.description = core.make_description_from_obj(desc)
            bid.sourceURL = bid.bidURL = self.urljoin(
                self.settings["index_url"] + "#" + clean_filename(bid.bidNumber)
            )

        else:
            bid.title = py_.clean(py_.get(row["row"], "a.text"))
            bid.bidNumber = (
                bid_re.search(bid.title).group(1) if bid_re.search(bid.title) else bid.sourceID
            )
            ddate_str = row["row"].select(".card-block.panel-body > p")
            for i in ddate_str:
                reddate = re.search(
                    r"(?:BID DUE\:.+on\s|no later than\s\d*\d*\:\d*\s\w\.\w\.\s\w*\s\w*\,\s)(\w*\s\d*\w*\,\s\d*)",
                    tag_text(i),
                )
                if reddate:
                    bid.dueDate = core.parse_date(reddate.group(1))
            bid.description = py_.clean(core.make_description_from_obj(row["row"]))
            bid.sourceURL = bid.bidURL = self.urljoin(
                self.settings["index_url"] + "#" + clean_filename(bid.bidNumber)
            )
            if row["link"]:
                return lambda: [row["link"].get("href")]


if __name__ == "__main__":
    Main().run()
    
hotfix/46246_city_lawton_bug_fix

