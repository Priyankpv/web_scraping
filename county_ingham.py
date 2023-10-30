import logging
import re
from datetime import datetime, timedelta

import textract
from bs4 import BeautifulSoup
from pydash import arrays as _arrays
from pydash import clean as _c
from pydash import flow, head
from pydash import objects as _objects

import core
from common.misc import tag_text
from common.text_utils import get_hash, long_re_date
from core.bid_scraper_plus import BidScraper

_tt = lambda x: _c(tag_text(x))


class Main(BidScraper):
    settings = {
        "version": "2.0.1",
        "script_name": "county_ingham",
        "created_by": "michalkras@gmail.com",
        "last_modified_by": "pvamja@govspend.com",
        "base_url": "http://pu.ingham.org",
        "agency_name": "Ingham County",
        "agency_state": "MI",
        "agency_type": "State & Local",
        "agency_website": "http://pu.ingham.org",
        "status_dict": {
            "open": {
                "url": "/departments_and_officials/purchasing/current_bids.php",
                "row_sel": "[id*='post'] > table > tbody tr:not(tr[style])",
                "head_sel": "[id*='post'] > table > thead > tr > th",
            },
            "closed": {
                "url": "/departments_and_officials/purchasing/bid_archives.php",
                "row_sel": ".faqs-toggle-content tbody tr",
                "head_sel": ".faqs-toggle-content> table > thead > tr > th",
            },
        },
        "tab_sel": "[id*='post'] > table > tbody",
        "tab_sel_archive": ".faqs-toggle-content > table > tbody",
    }

    def fetch_rows(self):
        def filter_records(rec):
            vals = list(rec["_txt"].values())
            if len(_arrays.compact(map(_c, vals))) <= 1:
                return False
            if not any(vals):
                return False
            if any(i in vals for i in ["Click on Packet Number for RFP/ITB"]):
                return False
            return True

        def parse(resp):
            if not resp:
                logging.warning(f"Failed to get a valid response!")
            else:
                soup = BeautifulSoup(resp.text, "html5lib")
                rows = soup.select(self.settings["status_dict"][self.status]["row_sel"])
                head_detail = soup.select(self.settings["status_dict"][self.status]["head_sel"])
                header_info = list(
                    map(
                        _tt,
                        head_detail,
                    )
                )

                for row in rows:
                    _tags = {
                        header_info[n]: x for n, x in enumerate(row.find_all("td", recursive=False))
                    }
                    record = {
                        "_tags": _tags,
                        "_txt": _objects.map_values(_tags, lambda v: v.get_text().strip()),
                        "_tag": row,
                    }
                    if filter_records(record):
                        yield record

        response = self.get(self.settings["status_dict"][self.status]["url"])
        soup = BeautifulSoup(response.text, "html5lib")
        if not response:
            logging.error(
                f"Failed to get a valid response for: {self.urljoin(self.settings['status_dict'][self.status]['url'])}"
            )
        self.index_url = response.url
        yield from parse(response)

    def bid_id_from_row(self, data):
        if any(data.get("_txt", {}).values()):
            return get_hash(str(data["_txt"]))

    find_due_date = re.compile(
        r"(?:Sealed)?\s*(?:proposals|bids?) due\s*:\s*" + long_re_date,
        flags=re.I | re.M,
    )

    def scrape_bid(self, bid, data):
        dl_urls = [
            x.get("href")
            for x in data["_tag"].select("a[href]")
            if not any(
                i in x.get("href", "")
                for i in [
                    "mailto:",
                    "sharepoint.com",
                    "forms.ingham.org/F/Purchasing_Bids",
                    ".box.com",
                ]
            )
        ]
        if self.status == "open":
            find_key = lambda x: head(list(filter(lambda y: re.search(x, y), data["_txt"].keys())))
            core.set_obj_attributes(
                bid,
                data["_txt"],
                {
                    "bidNumber": find_key(r"Packet Number"),
                    "title": "Description",
                    "dueDate": (
                        find_key(r"Bid Opening"),
                        flow(
                            lambda x: re.search(long_re_date, x, flags=re.I),
                            lambda y: core.parse_date(y.group(1)) if y else "",
                        ),
                    ),
                    "description": (
                        ".",
                        lambda x: core.make_description_from_obj(x, header=None),
                    ),
                },
            )
            bid.sourceURL = self.urljoin(f"{self.index_url}#{bid.bidNumber}")
            return lambda: dl_urls
        else:
            bid.description = core.make_description_from_obj(
                _objects.map_keys(data["_txt"], lambda v, k: re.sub(r"_+", "", k)),
                header=None,
            )
            find_field_name = lambda crit: _arrays.head(list(filter(crit, data["_txt"].keys())))
            _d = lambda x: data["_txt"].get(x, "")
            # get fields
            r_a_field = _d(
                find_field_name(lambda x: ("(R)" in x and "(A)" in x) or "Recommendation" in x)
            )
            if "(A)" in r_a_field:
                filter_from_name_col = [
                    "bid opening",
                    "click here",
                    "see left",
                    "bid tab",
                ]
                found_name = list(
                    filter(
                        lambda x: (
                            not any(i in x.lower() for i in filter_from_name_col)
                            and x != "(A)"
                            and x != "(R)"
                            and not re.search(r"^Item ([ivx]|\d)", x, flags=re.I)
                        ),
                        _arrays.compact(map(_c, r_a_field.splitlines())),
                    )
                )
                if found_name:
                    bid.awardedTo = _arrays.head(found_name).replace("(A)", "").strip()
            desc_name = find_field_name(lambda x: "Description" in x)
            desc_tag = data["_tags"].get(desc_name)
            bid.title = _c(_arrays.head(list(desc_tag.stripped_strings)) or _d(desc_name))
            price_field = _d(find_field_name(lambda x: "Price" in x))
            packet_no_field = _d(find_field_name(lambda x: "Packet #" in x))
            bno_m = re.search(r"(?:\s|^)(\d+-\d+)(?:\s|$)", packet_no_field)
            bid.bidNumber = bno_m.group(1) if bno_m else bid.sourceID
            bid.sourceURL = self.urljoin(f"{self.index_url}#{bid.bidNumber}")
            files = self.download_files(dl_urls, bid)
            due_date_changes = re.findall(
                r"due date to (\d{1,2}\/\d{1,2}\/\d{2,4})", _tt(data["_tag"])
            )
            if due_date_changes:
                bid.dueDate = core.parse_date(due_date_changes[-1])
            else:
                for file in files:
                    if file.path:
                        dump = ""
                        try:
                            dump = textract.process(file.path).decode()
                        except Exception as exception:
                            logging.warning(
                                f"Failed to process {exception=} -- {file.path=} -- {file.url=}"
                            )
                        if dump:
                            due_date_found = self.find_due_date.search(dump)
                            if due_date_found:
                                bid.dueDate = core.parse_date(due_date_found.group(1))
                                break
            if not bid.dueDate:
                bid.dueDate = (datetime.now() - timedelta(days=1)).strftime(core.datefmt)


if __name__ == "__main__":
    Main().run()
