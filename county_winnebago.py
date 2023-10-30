# RUN-FREQUENCY : { DAILY }
# RUN-LEVEL : { INFO }

import logging
import re

import pdftotext
import pydash as py_
from bs4 import BeautifulSoup as bs

import core
from common.text_utils import get_hash
from core.bid_scraper_plus import BidScraper


def get_date_from_pdf(fileinfos):
    for n, dl in enumerate(fileinfos):
        dump = ""
        if not dl.path:
            logging.info(f"Could not download file! URL: {dl.url}")
            if n != len(fileinfos) - 1:
                continue
            else:
                break
        with open(dl.path, "rb") as fp:
            try:
                pdf = pdftotext.PDF(fp)
                dump = py_.clean(" ".join(pdf))
                if not dump:
                    if n != len(fileinfos) - 1:
                        continue
                    else:
                        raise Exception("Error dumping file to text! (Likely a scanned doc)")
            except Exception as ex:
                logging.warning(f"Error dumping file to text! Exception: {ex}")
                continue
        try:
            if due_date_re := re.search(r"DUE DATE (\d+\/\d+\/\d\d\d\d)", dump):
                fddate = due_date_re.group(1)
            elif due_date_re := re.search(r"(\w+\s\d\d,\s\d\d\d\d)", dump):
                fddate = due_date_re.group(1)
            else:
                fddate = ""
            if post_date_re := re.search(r"ISSUE DATE (\d+\/\d+\/\d+)", dump):
                pdate = post_date_re.group(1)
            else:
                pdate = ""
        except:
            logging.error(f"Can not parse the dueDate from PDF: {dl.url}")
        if not fddate:
            if n != len(fileinfos) - 1:
                continue
            else:
                logging.warning("Counld not find dueDate!")
                continue
        else:
            if len(dump) > 10000:
                dump = dump[:997] + "..."
            return (core.parse_date(fddate), core.parse_date(pdate), dump)


class Main(BidScraper):
    settings = {
        "version": "1.0.2",
        "script_name": "county_winnebago",
        "base_url": "https://wincoil.gov",
        "created_by": "arupnarine@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Winnebago County",
        "agency_state": "IL",
        "agency_type": "State & Local",
        "index_url": "/departments/purchasing-department/open-bids-quotes-rfps",
        "row_sel": "div.sppb-addon-content > ul > li",
    }

    def pre_execute(self):
        if not py_.get(self, "settings.document_download"):
            logging.warning(
                "Setting document_download to True. This script relies"
                "on downloading and extracting text from pdf."
            )
        self.settings["document_download"] = True

    def fetch_rows(self):
        yield from bs(self.get(self.settings["index_url"]).text, "html5lib").select(
            self.settings["row_sel"]
        )

    def bid_id_from_row(self, row):
        addto = py_.get(row, "a.attrs.href")
        if addto:
            return get_hash(self.urljoin(addto))
        else:
            logging.warning("Cannot find sourceID. Skipping.")

    def scrape_bid(self, bid, row):
        bid.agencyWebsite = self.settings["base_url"]
        bid.sourceURL = self.urljoin(py_.get(row, "a.attrs.href"))
        try:
            bid.title = title = row.a.text
            bid.bidURL = (row.a).get("href")
            b_number = re.search(r"(\d+\w-\d+)", title)
            if b_number:
                bid.bidNumber = b_number.group(1)
            else:
                bid.bidNumber = title
        except:
            pass

        files = self.download_files(list(self.scrape_links(row)), bid)
        bid.dueDate, bid.postedDate, desc = get_date_from_pdf(files)
        bid.description = f"<br><p>{desc}</p>"


if __name__ == "__main__":
    Main().run()
