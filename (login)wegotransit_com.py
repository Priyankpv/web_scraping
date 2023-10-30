import logging
import re
from urllib.parse import quote, unquote

from bs4 import BeautifulSoup
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper
from core.common import _tt, get_hash, tag_text


class Main(BidScraper):
    settings = {
        "version": "1.0.2",
        "script_name": "wegotransit_com",
        "base_url": "https://www.wegotransit.com/",
        "created_by": "jedmonson@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "default_agency_name": "Nashville Metropolitan Transit Authority",
        "agency_state": "TN",
        "agency_type": "State & Local",
        "agency_website": "https://www.wegotransit.com/",
        "index_url": "/doing-business/current-opportunities/",
        "row_sel": {"open":["#CT_Main_0_gvOpen_up > div:not([class])","#CT_Main_0_gvInReview_up > div:not([class])"],"closed":["#CT_Main_0_gvAwarded_up > div:not([class])"]},
    }

    agency_lookup = {
        "MTA": "Nashville Metropolitan Transit Authority",
        "RTA": "Regional Transportation Authority of Middle Tennessee",
        "DTO": "Davidson Transit Organization",
    }

    def fetch_rows(self):
        if resp := self.get(self.settings["index_url"]):
            soup = BeautifulSoup(resp.text, "html5lib")
            for r in self.settings["row_sel"][self.status]:
              yield from filter(
                  lambda x: "PUBLIC NOTICE" not in _tt(x.select_one("h3")),
                  soup.select(r),
              )
        else:
            logging.error(
                "Failed to get response for url: %s",
                self.urljoin(self.settings["index_url"]),
            )

    bid_id_from_row = staticmethod(lambda row: get_hash(tag_text(row)) if tag_text(row) else None)

    def scrape_bid(self, bid, row):
        desc = {}
        get_details_dict = lambda content: py_.pick_by(
            {
                k: v
                for x in content.select("table > tbody > tr")
                if len(x.findAll("td", recursive=False)) == 2
                for a, b in [x.findAll("td", recursive=False)]
                for k, v in [[a.text.strip(" :\n"), b.text.strip()]]
            }
        )
        txt_child = py_().invoke("findChild", None, text=True, recursive=False).thru(tag_text)

        if bno := row.select_one("[id$='_pBidNumber']"):
            bid.bidNumber = txt_child(bno)
        else:
            bid.bidNumber = bid.sourceID
        bid.dueDate = (
            py_(row.select_one("[id$='_pBidDeadline']"))
            .thru(txt_child)
            .split("by")
            .head()
            .thru(core.parse_date)
            .value()
        ) if row.select_one("[id$='_pBidDeadline']") else ''
        bid.title = (
            py_(row)
            .invoke("h3.text.strip")
            .replace(bid.bidNumber, "")
            .invoke("strip", " -")
            .clean()
            .value()
        )

        if detail_href := py_.get(row, "h3.a.href"):
            bid.sourceURL = bid.bidURL = self.urljoin(detail_href)
            if resp := self.get(bid.sourceURL):
                soup = BeautifulSoup(resp.text, "html5lib")
                if info := soup.select_one("div#tabInfo"):
                    desc.update(py_.pick_by({"Info": get_details_dict(info)}))
                    if agency := py_.get(desc, "Info.Agency"):
                        bid.agencyName = self.agency_lookup.get(agency)
                        if not bid.agencyName:
                            logging.warning(
                                "message: %s value: %s",
                                "Found no matching abbreviation.",
                                agency,
                            )

                if bid_tab := soup.select_one("div#tabTabulation"):
                    desc.update(py_.pick_by({"Bid Tabulation": get_details_dict(bid_tab)}))
                if award := soup.select_one("div#tabAwardees"):
                    header = [tag_text(h) for h in award.select("tr th")]
                    if len(header) == len(award.select("tr td")):
                        row_dict = {header[n]: _tt(cell) for n, cell in enumerate(award.select("tr td"))}
                    else: 
                        row_dict = None
                    if row_dict:
                        bid.awardedTo = row_dict["Firm Name"]
                        bid.awardedAmount = row_dict["Price"]
                if soup.select("div#tabDocuments"):
                    file_resp = self.post(
                        bid.sourceURL,
                        data={
                            **core.get_hidden_inputs(soup),
                            "sm": "CT_Main_0$upBidForm|CT_Main_0$btnSubmitBidForm",
                            "ctl18$txtSearch": "",
                            "CT_Main_0$txtCompanyName": "SMARTPROCURE INC.",
                            "CT_Main_0$txtContactPerson": "priyank",
                            "CT_Main_0$txtEmail": "pvamja@govspend.com",
                            "CT_Main_0$txtPhone": "9544209900",
                            "__ASYNCPOST": "true",
                            "CT_Main_0$btnSubmitBidForm": "Submit",
                        },
                    )
                    doc_link = unquote(re.search(r"(https.+?)\|", file_resp.text).group(1))
                    if link_data := self.get(doc_link):
                        soup_doc = BeautifulSoup(link_data.text, "html5lib")
                        doc = soup_doc.select("table#CT_Main_0_gvDocuments >tbody >tr a[href]")
                        for i in doc:
                            headers = {
                                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                                "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                                "Cookie": "ASP.NET_SessionId=5kz4syimaq5zm1t3u5qwfgpf",
                            }
                            temp_data = core.get_hidden_inputs(soup_doc)
                            file_data = re.search(r"(CT.+?)\'", i.get("href")).group(1)
                            payload = f"sm=CT_Main_0%24upBidForm%7C{quote(file_data)}&__EVENTTARGET={quote(file_data)}&__EVENTARGUMENT=&hdnSubDirectory=&ctl18%24txtSearch=&__VIEWSTATEGENERATOR=3989C74E&__EVENTVALIDATION={quote(temp_data['__EVENTVALIDATION'])}&__VIEWSTATE={quote(temp_data['__VIEWSTATE'])}&__ASYNCPOST=true&"
                            doc_resp = self.post(url=doc_link, headers=headers, data=payload)
                            if doc_resp:
                                self.download_file(
                                    bid,
                                    self.settings["base_url"]
                                    + unquote((doc_resp.text).split("|")[-2]),
                                )

            else:
                logging.warning(
                    "message: %s sourceURL: %s",
                    "Failed to get a valid detail page response!",
                    bid.sourceURL,
                )

        if not bid.agencyName:
            bid.agencyName = self.settings["default_agency_name"]

        if not bid.dueDate:
            bid.set_default_due_date()

        if desc:
            bid.description = core.make_description_from_obj(desc, header=None)


if __name__ == "__main__":
    Main().run()

