import json
import logging
import re

import pandas as pd
from bs4 import BeautifulSoup as bs
from bs4 import Comment
from pydash import get as _g

import core
from core.bid_scraper_plus import BidScraper
from core.common import get_hash
from core.common.file_download import clean_filename
from scrapers.bids.us.all.procurenow.components import get_script_data, get_subscriptions

# Possible bid statuses in script:
#   included:
#     pending
#     closed
#     open
#     evaluation
#     awardPending
#     review
#   excluded:
#     draft
#     postPending


class Main(BidScraper):
    settings = {
        "version": "1.0.6",
        "script_name": "procurenow",
        "created_by": "jalbu@govspend.com",
        "last_modified_by": "jedmonson@govspend.com",
        "agency_name": "",
        "agency_state": "",
        "agency_type": "State & Local",
        "base_url": "https://secure.procurenow.com/",
        "agency_website": "https://secure.procurenow.com/",
        "sub_url": "vendors/53483/my-subscriptions",
        "portal": "portal/%s",
        "detail_url": "projects/%s",
        "detail_sel": "#project-section-container",
        "login_url": "https://api.procurement.opengov.com/api/v1/auth/login",
        "login_cred": {
            "username": "rbjornsson@smartprocure.us",
            "password": "Hello888888!",
        },
    }

    def fetch_rows(self):
        if self.status == "closed":
            return
        self.subscriptions = get_subscriptions(self)
        if not self.subscriptions:
            logging.error("No subscriptions - exiting")
            return
        all_bids = True if self.settings["all_solicitations"] else False
        for self.sub in self.subscriptions:
            url_code = _g(self.sub, "government.code")
            resp = self.get(self.settings["portal"] % url_code) if url_code else ""
            self.agency_data = {
                "agency_name": _g(self.sub, "government.organization.name"),
                "agency_state": _g(self.sub, "government.organization.state"),
            }
            logging.info(
                "Parsing through %s, %s",
                self.agency_data["agency_name"],
                self.agency_data["agency_state"],
            )
            if resp:
                self.agency_url = resp.url
                script_data = get_script_data(resp)
                bids = _g(script_data, "publicProject.govProjects", [])
                yield from filter(
                    lambda x: (x["status"] == "open")
                    if not all_bids
                    else (not re.search("draft|postPending", x["status"], re.I)),
                    bids,
                )
            else:
                logging.warning(
                    "No response from agency: %s, %s",
                    self.agency_data["agency_name"],
                    self.agency_data["agency_state"],
                )

    def bid_id_from_row(self, row):
        text = " ".join(
            [
                str(v)
                for k, v in row.items()
                if k
                in [
                    "summary",
                    "proposalDeadline",
                    "title",
                    "ProposalDeadline",
                    "status",
                    "addendums",
                ]
            ]
        )
        if text:
            return get_hash(text)

    def scrape_bid(self, bid, row):
        core.common.objects.set_bid_attributes(
            bid,
            row,
            {
                "title": "title",
                "dueDate": ("proposalDeadline", core.common.parse.parse_date),
                "bidNumber": "financialId",
            },
        )
        if not bid.bidNumber:
            bid.bidNumber = row["id"] if row["id"] else bid.sourceID
        bid.agencyName = self.agency_data["agency_name"]
        bid.agencyState = self.agency_data["agency_state"]
        url = self.agency_url + "/" + self.settings["detail_url"] % row["id"]
        detail_resp = self.get(url + "?section=all")
        if detail_resp:
            bid.sourceURL = bid.bidURL = detail_resp.url
            full_soup = bs(detail_resp.text, "html5lib")
            soup = full_soup.select_one(self.settings["detail_sel"])
            if not soup:
                bid.description = row["summary"]
                bid.sourceURL = self.agency_url + "#" + clean_filename(bid.bidNumber)
                return
            draft_alert = soup.select_one(".alert.alert-warning")
            if draft_alert:
                draft_alert.decompose()

            for comments in soup.findAll(text=lambda text: isinstance(text, Comment)):
                comments.extract()

            # Need more filtering for description
            bid.description = str(core.common.modify_html(soup))

            details = get_script_data(detail_resp)
            awarded_list = [
                _g(i, "companyName", "")
                for i in _g(
                    details,
                    "publicProject.project.evaluation.selectedProposals",
                    [],
                )
                if _g(i, "companyName", "")
            ]
            if awarded_list:
                if len(awarded_list) > 1:
                    bid.awardedTo = "Multiple"
                elif awarded_list:
                    bid.awardedTo = awarded_list[0]
                bid.description += "<br><br><h3>Awarded to</h3><ul>%s</ul>" % "".join(
                    ["<li>" + i + "</li>" for i in awarded_list]
                )
            else:
                bid.description += (
                    "<br><br><h3>Awarded to</h3><br><i>No vendor has been selected</i>"
                )

            if results_link := full_soup.find("a", text=re.compile("Results")):
                results_resp = self.get(results_link.get("href"))
                result_details = get_script_data(results_resp)
                bid_results = _g(result_details, "publicProject.project.bidResults", {})
                if bid_results:
                    bid.description += "<br><br><h2>Results</h2>"
                    vendor_names = [i["vendorName"] for i in bid_results["proposalsData"]]
                    for bid_tab in bid_results["bidTabulations"]:
                        table_frame = pd.DataFrame(
                            columns=["Line Item", "Description", "Unit of Measure"]
                            + list(set(vendor_names))
                        )
                        bid.description += "<br><br><h3>%s</h3>" % bid_tab["title"]
                        for row in bid_tab["rows"]:
                            table_frame = pd.concat(
                                [
                                    table_frame,
                                    pd.DataFrame(
                                        [
                                            {
                                                "Line Item": row["lineItem"],
                                                "Description": row["description"],
                                                "Unit of Measure": row["unitToMeasure"],
                                                **{
                                                    vendor_names[n]: float(
                                                        _g(j, "unitPrice", 0)
                                                        * float(_g(j, "quantity", 0))
                                                    )
                                                    for n, j in enumerate(row["vendorResponses"])
                                                },
                                            }
                                        ]
                                    ),
                                ]
                            )
                        if table_frame.shape[0] > 1:
                            sum_dict = table_frame.sum(numeric_only=True).to_dict()
                            sum_dict["Description"] = "Total"
                            table_frame = pd.concat([table_frame, pd.DataFrame([sum_dict])]).fillna(
                                ""
                            )
                        table_frame.dropna(how="all", axis=1, inplace=True)
                        bid.description += table_frame.to_html(index=False)

            # Downloads
            if self.settings["document_download"]:
                download_json = _g(details, "publicProject.project.attachments", []) + [
                    _g(details, "publicProject.project.documentAttachment", {})
                ]
                for adden in _g(details, "publicProject.project.addendums", []):
                    for attach in _g(adden, "attachments", []):
                        download_json.append(attach)
                return lambda: [("", dl.get("url")) for dl in download_json if _g(dl, "url", "")]
        else:
            bid.description = row["summary"]
            bid.sourceURL = self.agency_url + "#" + clean_filename(bid.bidNumber)


if __name__ == "__main__":
    Main().run()

