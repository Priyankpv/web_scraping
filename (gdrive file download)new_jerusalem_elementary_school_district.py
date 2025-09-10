import logging
import re

import textract
from bs4 import BeautifulSoup as bs
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper
from core.common import _tt, get_hash, long_re_date

regexes = "|".join([r"RESPONSE DEADLINE FOR PROPOSALS:\s?\d*\:\d*\s\w\.\w\.\s?\w*\,\s?"])
find_re = re.compile(f"(?:{regexes})" + long_re_date, re.I)
title_re = re.compile(
    r"(?:proposal for your services on|REQUEST FOR PROPOSALS.*?-\d*\W?)(.*?)\W? The following"
)


class Main(BidScraper):
    settings = {
        "version": "1.0.0",
        "script_name": "new_jerusalem_elementary_school_district",
        "base_url": "https://www.njesd.net",
        "created_by": "pvamja@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "New Jerusalem Elementary School District",
        "agency_state": "CA",
        "agency_type": "State & Local",
        "index_url": "/en-US/business-services-29af380f",
        "agency_website": "https://www.njesd.net/",
    }

    def pre_execute(self):
        if not self.settings["document_download"]:
            logging.warning("This script relies on parsing the dueDates from downloaded files!")
            self.settings["document_download"] = True
        self.index = self.get(py_.get(self, "settings.index_url"))
        self.soup = bs(self.index.text, "html5lib")

    def fetch_rows(self):
        if self.status == "closed":
            return

        yield from [
            (i.get("href"), _tt(i))
            for i in self.soup.select(
                "#item-d9634dd7-015f-4606-b907-88b5a43406f7 .QuicklinkBlock_linkItem__eoNMD span a[href]"
            )
            if "https://drive.google.com/" in i.get("href")
        ]

    def bid_id_from_row(self, row):
        return get_hash(row[1])

    def scrape_bid(self, bid, row):
        def get_date_from_files(bid, fileinfos):
            for n, dl in enumerate(fileinfos):
                dump = ""
                try:
                    dump = textract.process(dl.path).decode("utf-8")
                except Exception as ex:
                    logging.info(f"Error dumping file to text! Exception: {ex} FILE_URL: {dl.url}")
                c_dump = py_.clean(dump)
                if dump:
                    title = title_re.search(c_dump)
                    if title:
                        f_title = title.group(1)
                    else:
                        logging.error(f"No Title found in bid PDF: {dl.url}")
                    fddate = find_re.search(c_dump) if find_re.search(c_dump) else ""
                    if len(dump) > 1000:
                        dump = dump[:997] + "..."
                    dump = dump.replace("\n", "<br>")
                    dump = f"<hr><center><blockquote>{dump}</blockquote></center>"
                    return (fddate, py_.clean(dump), py_.clean(f_title))
                else:
                    logging.warning(f"Could not find dueDate in FILE_URL: {dl.url}")
                if n != len(fileinfos) - 1:
                    continue
                else:
                    break

        file_id = row[0].split("/")[-2]
        file_link = "https://drive.google.com/uc?export=download&id=" + file_id
        files = self.download_files([("", file_link)], bid)
        if files:
            fileDate = get_date_from_files(bid, files)
            if fileDate:
                dueDate, desc, title = fileDate
        bid.bidNumber = py_.clean(row[1].split(" ")[-1])
        bid.sourceURL = self.urljoin(f'{self.settings["index_url"]}#{bid.bidNumber}')
        bid.title = title
        bid.dueDate = core.parse_date(dueDate.group(1)) if dueDate else ""
        bid.description = desc


if __name__ == "__main__":
    Main().run()

