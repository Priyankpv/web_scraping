import datetime
import logging
import re
from itertools import count

import dateutil.parser as dparser
import pdftotext
from bs4 import BeautifulSoup as bs
from docx import Document as docx_Document
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper
from core.common import datefmt, get_hash, long_re_date, tag_text

regexes = "|".join(
    [
        r"must be placed in a sealed.+until[ \w\:\.]*\,?\s?[\w]*\,?\s?",
        r"will be received.+until[ \w\:\.]*\,?\s?[\w]*\,?\s?",
        r"Responses must be received on or before[ \w\:\.]*\,?\s?[\w]*\,?\s?",
        r"must be received on or before[ \w\:\.]*\,?\s?[\w]*\,?\s?",
        r"DUE DATE:[ \w\:\.]*\,?\s?[\w]*\,?\s?",
        r"accepting proposals.+until[ \w\:\.]*\,?\s?[\w]*\,?\s?",
    ]
)
find_re = re.compile(f"(?:{regexes})" + long_re_date, re.I)
awarded_reg = re.compile(
    r"Board (?:of (?:Park )?Commissioners )?accepted the (?:base )?.*?(?:from) (.+?(?:LLC,)?)(?:\.|for|in the|$)",
    re.I,
)
amount_reg = re.compile(
    r"(?:in the amount|not[- ]to[- ]exceed).{0,50}?(\$(?:\d{1,3}, ?)*\d+(?:\.\d+)?)",
    re.I,
)


def get_date_from_files(bid, fileinfos):
    date, money, awarded, dump = "", "", "", ""
    for n, dl in enumerate(fileinfos):
        if dl.path:
            try:
                if dl.path.endswith(".docx"):
                    dump = [py_.clean(i, "text") for i in docx_Document(dl.path).paragraphs]
                elif dl.path.endswith(".pdf"):
                    dump = pdftotext.PDF(open(dl.path, "rb"))
                else:
                    logging.info("Could not dump file format: (%s)", dl.ext)
            except Exception as ex:
                logging.info("Error dumping file to text! Exception: %s FILE_URL: %s", ex, dl.url)
            dump = py_.clean(" ".join(dump))
            if dump:
                fddate = find_re.search(dump)
                awarded_test = awarded_reg.search(dump)
                amount_test = amount_reg.search(dump)
                if not date and fddate:
                    date = core.common.parse.parse_date(fddate.group(1))
                if not awarded and awarded_test:
                    awarded = awarded_test.group(1)
                if not money and amount_test:
                    money = core.common.parse.parse_money_string(amount_test.group(1))
                if not date:
                    logging.debug("Could not find dueDate in FILE_URL: %s", dl.url)
                if len(dump) > 1000:
                    dump = dump[:997] + "..."
                if awarded and date:
                    break
            else:
                logging.info("Could not dump document to text! FILE_URL: %s", dl.url)
        else:
            logging.info("File could not be downloaded. FILE_URL: %s", dl.url)
        if n != len(fileinfos) - 1:
            continue
        else:
            break
    return [date, awarded, money, dump]


class Main(BidScraper):
    settings = {
        "version": "1.1.1",
        "script_name": "district_oak_brook_park",
        "base_url": "https://www.obparks.org",
        "created_by": "jclervil@govspend.com",
        "last_modified_by": "jalbu@govspend.com",
        "agency_name": "Oak Brook Park District",
        "agency_state": "IL",
        "agency_type": "State & Local",
        "agency_website": "https://www.obparks.org",
        "index_url": {
            "open": "/bids-rfps?page={}",
            "closed": "/bids-and-requests-proposals-rfps-archives",
        },
        "title_sel": "div.views-field.views-field-title",
        "row_sel": "div.view-content > div",
    }

    def pre_execute(self):
        if not py_.get(self, "settings.document_download"):
            logging.warning(
                "Setting document_download to True. This script relies on downloading and extracting text from the pdf on each bid page."
            )
            self.settings["document_download"] = True

    def fetch_rows(self):
        if self.status == "closed":
            self.the_index = self.settings["index_url"][self.status]
            resp = self.get(self.the_index)
            if resp:
                rows = bs(resp.text, "html5lib").select(self.settings["row_sel"])
                logging.info("There are %s bid(s) on page of closed bids", len(rows))
                yield from rows
        else:
            for pg in count(0):
                self.the_index =  self.settings["index_url"][self.status].format(pg)
                resp = self.get(self.the_index)
                if resp:
                    rows = bs(resp.text, "html5lib").select(self.settings["row_sel"])
                    logging.info("There are %s bid(s) on page %s", len(rows), pg)
                    yield from rows
                else:
                    logging.error("No response from index_page: %s", self.the_index)
                    break
                if len(rows) < 20:
                    break

    def bid_id_from_row(self, row):
        data = tag_text(row)
        if data:
            return get_hash(data)

    def scrape_bid(self, bid, row):
        title = row.select_one(self.settings["title_sel"])
        bid.title = bid.description = tag_text(title)
        postedDate = row.select_one(".views-field-field-date")
        if postedDate:
            bid.postedDate = core.common.parse.parse_date(tag_text(postedDate))
        files = self.download_files(list(self.scrape_links(row)), bid)
        filedate = get_date_from_files(bid, files)
        if filedate[0]:
            bid.dueDate = filedate[0]
        elif bid.postedDate:
            bid.set_default_due_date(starting_from=dparser.parse(bid.postedDate))
        else:
            bid.dueDate = core.common.parse.parse_date(
                (datetime.datetime.now() - datetime.timedelta(days=1)).strftime(datefmt)
            )
        if filedate[1]:
            bid.awardedTo = filedate[1]
        if filedate[2]:
            bid.awardedAmount = filedate[2]
        if filedate[3]:
            bid.description = f"<h3>{bid.title}</h3><br>{filedate[2]}"

        bid.sourceURL = self.urljoin(f"{self.the_index}#{bid.bidNumber}")


if __name__ == "__main__":
    Main().run()

