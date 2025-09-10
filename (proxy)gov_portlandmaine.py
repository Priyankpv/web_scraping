import json
import logging
import os
import re
from datetime import datetime

import pdftotext
from bs4 import BeautifulSoup as bs
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper, SkipBid
from core.common import clean_filename, get_hash, long_re_date

filter_id_re = re.compile(r"Current Bids(?:.*?)manualContentItemIds: *(.*?)\],", re.I)
title_re = re.compile(r"(?P<bid_id>(?:Bid|RFP) *#*\d+) *(?P<titile>.*)", re.I)
dd_re = re.compile(
    r"(?:received[\W\s]*(?:until|by)?\s?.*?)"
    rf"(?:\d+:\d+\s?[AP]\.?M\.?,?\s?(?:on\W?)?)?(?:\w+\W*)({long_re_date})",
    re.I,
)


def get_date_from_pdf(fileinfos):
    dump = ""
    if not fileinfos.path:
        logging.info(f"Could not download file! URL: {fileinfos.url}")
    with open(fileinfos.path, "rb") as fp:
        try:
            pdf = pdftotext.PDF(fp)
            dump = py_.clean(" ".join(pdf))
            if not dump:
                raise Exception("Error dumping file to text! (Likely a scanned doc)")
        except Exception as ex:
            logging.warning(f"Error dumping file to text! Exception: {ex}")
    fddate = due_date_re.group(1) if (due_date_re := re.search(dd_re, dump)) else ""
    if len(dump) > 10000:
        dump = dump[:997] + "..."
    return (core.parse_date(fddate), dump)


class Main(BidScraper):
    settings = {
        "version": "1.0.3",
        "script_name": "gov_portlandmaine",
        "base_url": "https://www.portlandmaine.gov",
        "api_base_url": "https://content.civicplus.com/api/assets/",
        "api_url": "https://content.civicplus.com/api/apps/me-portland/all",
        "agency_website": "https://www.portlandmaine.gov",
        "index_url": "/1210/Current-BidsRFPs",
        "created_by": "achikni@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "City of Portland",
        "agency_state": "ME",
        "agency_type": "State & Local",
    }

    def fetch_rows(self):
        if self.status == "closed":
            return []
        proxy_url = os.environ.get("SP_PROXY", "")
        proxies = {"http": proxy_url, "https": proxy_url}
        self.session.verify = False
        resp = self.get(self.settings["index_url"], proxies=proxies)
        if not resp:
            logging.error(
                "No response from index page: %s", self.urljoin(self.settings["index_url"])
            )
        auth_token = (
            token_re.group(1)
            if (token_re := re.search(r'window\.hcmsClientToken="(.*?)"', resp.text))
            else ""
        )
        self.session.headers.update({"Authorization": auth_token})
        get_fillter_js_sel = bs(resp.text, "html5lib").select_one("title~style").previous
        if req_data_str := re.search(filter_id_re, get_fillter_js_sel):
            filter_list_str = " or id eq ".join(json.loads(req_data_str.group(1) + "]"))
            querystring1 = {
                "$top": "200",
                "$skip": "0",
                "$orderby": "id",
                "$filter": f"(id eq {filter_list_str})",
            }
            if api_resp := self.get(
                url=self.settings["api_url"], params=querystring1, proxies=proxies
            ):
                json_data = json.loads(api_resp.text)
                yield from json_data["items"]

    def bid_id_from_row(self, row):
        if any(row.values()):
            return get_hash(str(row))

    def scrape_bid(self, bid, row):
        if re.search(
            r"(cancel|Notice to Software Developers.|cancelled)", row["fileName"], re.IGNORECASE
        ):
            raise SkipBid("Not a bid: %s" % row["fileName"])

        if title_id_search := re.search(title_re, row["fileName"]):
            bid.bidNumber, bid.title = title_id_search.groupdict().values()
        bid.postedDate = core.parse_date(row["lastModified"])
        dock_link = self.settings["api_base_url"] + py_.get(row, "id")
        bid.sourceURL = self.urljoin(
            self.settings["index_url"] + "#" + clean_filename(bid.bidNumber)
        )

        file = self.download_file(bid, dock_link)
        bid.dueDate, desc = get_date_from_pdf(file)
        bid.description += f"<br><p>{desc}</p>"
        if not bid.dueDate:
            bid.set_default_due_date(datetime.strptime(bid.postedDate, core.datefmt))


if __name__ == "__main__":
    Main().run()

