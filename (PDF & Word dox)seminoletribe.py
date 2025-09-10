import logging
import re

import pdftotext
from bs4 import BeautifulSoup, Comment
from docx import Document as docx_Document
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper
from core.common import get_hash, long_re_date


class Main(BidScraper):
    settings = {
        "version": "2.1.2",
        "script_name": "seminoletribe",
        "base_url": "https://www.semtribe.com",
        "created_by": "jedmonson@govspend.com",
        "last_modified_by": "dparisi@govspend.com",
        "agency_name": "Seminole Tribe of Florida",
        "agency_state": "FL",
        "agency_type": "State & Local",
        "index_url": "/services/solicitation-to-bid-general",
        "agency_website": "https://www.semtribe.com",
        "row_sel": "div.invitationtobid > ul > li",
        "cont_sel": "div.invitationtobid",
    }

    def pre_execute(self):
        if not py_.get(self, "settings.document_download"):
            logging.warning(
                "Setting document_download to True. This script relies on downloading "
                "and extracting text from the pdf on each bid page."
            )
            self.settings["document_download"] = True

    def fetch_rows(self):
        if self.status == "closed":
            return []
        if r := self.get(self.settings["index_url"]):
            soup = BeautifulSoup(r.text, "html5lib")
            yield from soup.select(self.settings["row_sel"])

    bid_id_from_row = staticmethod(lambda tag: get_hash(str(tag)))

    def scrape_bid(self, bid, tag):
        bno_re = re.compile(r"[ris][fto][pqbi]\s*(\d+\s?\-\d{4})", re.I)
        date_re = re.compile(rf"({long_re_date}|\d\d?[/.\-]\d\d?[/.\-]\d\d\d?\d?)")

        def get_duedate_from_files(files):
            for file_href in files:
                dl_info = self.download_file(bid, file_href, use_remote_file_name=True)
                dump_list = []
                if not dl_info.path:
                    logging.error("NO file")
                if dl_info.path.endswith(".pdf"):
                    with open(dl_info.path, "rb") as fp:
                        try:
                            dump_list = pdftotext.PDF(fp)
                        except Exception as ex:
                            logging.error(ex)
                elif dl_info.path.endswith(".docx"):
                    dump_list = [py_.get(i, "text") for i in docx_Document(dl_info.path).paragraphs]
                if not dump_list:
                    logging.info("No file to parse!")
                dump = py_.clean(" ".join(dump_list))
                if find_re_date := date_re.search(dump):
                    if len(dump) > 1000:
                        dump = dump[:997] + "..."
                    return dump, core.common.parse.parse_date(find_re_date.group(1))
                else:
                    logging.debug("No duedate found in file!")
            logging.error("No date found in any files!")

        posted = ""
        bid.title = tag.text.strip()
        if due_date := date_re.search(bid.title):
            bid.dueDate = core.common.parse.parse_date(due_date.group(1))
        bid.sourceURL = self.urljoin(py_.get(tag, "a.href"))
        if bno := bno_re.search(bid.title):
            bid.bidNumber = bno.group(1)
        if date_comment := tag.find(text=lambda x: isinstance(x, Comment)):
            if posted_date := date_re.search(date_comment):
                bid.postedDate = core.common.parse.parse_date(posted_date.group(1))
                posted = f"<br><p>Last updated on: {bid.postedDate}</p>"
        if r := self.get(bid.sourceURL):
            bid_page = BeautifulSoup(r.text, "html5lib")
            if bid_cont := bid_page.select_one(self.settings["cont_sel"]):
                bid.description = core.common.soup.make_description(bid_cont) + posted
                doc_links = self.scrape_links(bid_cont)
                if not bid.dueDate:
                    bid.description, bid.dueDate = get_duedate_from_files(doc_links)
                else:
                    return lambda: doc_links
            else:
                bid.description = f"<h3>{bid.title}</h3>" + posted


if __name__ == "__main__":
    Main().run()

