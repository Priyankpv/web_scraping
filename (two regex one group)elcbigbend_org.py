import logging
import re

import pdftotext
from bs4 import BeautifulSoup as bs
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper
from core.common import _tt, get_hash, long_re_date


class Main(BidScraper):
    settings = {
        "version": "1.0.5",
        "script_name": "elcbigbend_org",
        "base_url": "https://elcbigbend.org",
        "created_by": "dparisi@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Early Learning Coalition of the Big Bend",
        "agency_state": "FL",
        "agency_type": "State & Local",
        "agency_website": "https://elcbigbend.org/",
        "index_url": "/procurement",
    }

    def pre_execute(self):
        if not py_.get(self, "settings.document_download"):
            logging.warning(
                "Setting document_download to True. This script relies on downloading and extracting text "
                "from the pdf on each bid page."
            )
            self.settings["document_download"] = True

    def fetch_rows(self):
        if self.status == "closed":
            return
        if res := self.get(self.settings["index_url"]):
            soup = bs(res.text, "html5lib")
            yield from filter(
                lambda rr: not re.search(r"Call for Presenters", _tt(rr), re.I),
                soup.select("main#main > div > div.container"),
            )
        else:
            logging.error(
                "No response from index page URL: %s",
                self.urljoin(self.settings["index_url"]),
            )

    def bid_id_from_row(self, row):
        return get_hash(str(row))

    def scrape_bid(self, bid, row):
        def get_date_from_file(file_infos):
            regex_search_strings = [
                r"Proposal due date(?: \(E-mail PDFs to ELC\))?",
                r"Proposers must e-?mail their quotes to ELC by(?: .+day,?)",
                r"shall submit their written Proposal by email to purchasing@elcbigbend.org no later than .+\([A-Z]+\) on",
                r"Due Date:?",
                r"Date Due:?",
                r"deadline \(",
            ]
            due_date_re = re.compile(
                rf'(?:{"|".join(regex_search_strings)})'
                rf" {long_re_date[:-1]}|\d+/\d+/(?:20\d\d|\d\d))",
                re.I,
            )
            for file_info in filter(lambda fi: fi.path and fi.path.endswith(".pdf"), file_infos):
                dump = None
                try:
                    with open(file_info.path, "rb") as fp:
                        dump = pdftotext.PDF(fp)
                    dump = py_.clean(" ".join(dump))
                except Exception as ex:
                    logging.warning(
                        "custom_message: %s :: File: %s :: URL: %s :: Exception: %s",
                        "Failed to dump file to text!",
                        file_info.path,
                        file_info.url,
                        ex,
                    )
                    continue
                if dump:
                    if date_search := due_date_re.search(dump):
                        return core.common.parse.parse_date(date_search.group(1))
                    else:
                        logging.debug("No date found for file: %s", file_info.url)
            logging.warning("No dueDate found for bid URL: %s", bid.bidURL)

        title_tag = _tt(py_.get(row, "h2"))
        if parse_title_tag := re.search(
            r"^(.+) (\([A-Z]{3}\)\s?#\s?\d+\.\d+\s?[-━. ]\s?\d+)", title_tag
        ):
            bid.title, bid.bidNumber = parse_title_tag.groups()
        else:
            bid.title = title_tag
        bid.sourceURL = bid.bidURL = py_.get(row, "a.href")
        if detail_resp := self.get(bid.sourceURL):
            detail_soup = bs(detail_resp.text, "html5lib")
            bid.description = core.common.objects.make_description_from_obj(
                detail_soup.select_one("div.page-full > div.container > div > div"),
                header=None,
            )
            download_infos = self.download_files(
                py_.uniq(
                    [py_.get(a, "href") for a in detail_soup.select(f'a[href*="/wp-content/"]')]
                ),
                bid,
            )
            if due_date_tag := detail_soup.find("li", text=re.compile("Due Date:?", re.I)):
                bid.dueDate = core.common.parse.parse_date(_tt(due_date_tag))
            elif due_date_title_tag := detail_soup.find(
                "td",
                text=re.compile(r"Due Date:?|Anticipated Date of Notice of Intent to Award", re.I),
            ):
                due_date_tag = due_date_title_tag.findNext("td")
                bid.dueDate = core.common.parse.parse_date(_tt(due_date_tag))
            elif due_date_parse := detail_soup.find(
                "p", text=re.compile(r"submit it by|end on|proposal form by")
            ):
                date_parse_re = re.search("(?:following proposal form by .*?\,\s?|end on )((\w+\s?\d+\,?\s?\d+|\d*\/\d*\/\d*))", _tt(due_date_parse))
                if date_match := date_parse_re.group(1):
                    bid.dueDate = core.parse_date(date_match)
            else:
                if due_date_from_file := get_date_from_file(download_infos):
                    bid.dueDate = due_date_from_file


if __name__ == "__main__":
    Main().run()

