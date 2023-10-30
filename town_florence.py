import logging
import random
import re
import time

from bs4 import BeautifulSoup as bs
from pydash import get as _g
from pydash import strings as _strings

import core
from core.bid_scraper_plus import BidScraper
from core.common import get_hash, tag_text

_c = _strings.clean


class Main(BidScraper):
    settings = {
        "version": "1.0.1",
        "script_name": "town_florence",
        "base_url": "http://www.florenceaz.gov",
        "created_by": "jedmonson@govspend.com",
        "last_modified_by": "jedmonson@govspend.com",
        "agency_name": "Town of Florence",
        "agency_state": "AZ",
        "agency_type": "State & Local",
        "agency_website": "http://www.florenceaz.gov",
        "index_url": "/rfp/",
        "statuses": {
            "open": [("Open", 4)],
            "closed": [("Closed", 3), ("Awarded", 1), ("Canceled", 2)],
        },
        "row_sel": "table.listtable.responsive > tbody > tr",
        "sub_form": {
            "Business Name": "Smartprocure",
            "First Name": "Ron",
            "Last Name": "Bjornsson",
            "Email Address": "rbjornsson@smartprocure.us",
        },
    }

    def fetch_rows(self):
        self.session.verify = False
        for status, st_num in self.settings["statuses"][self.status]:
            resp = self.get(self.settings["index_url"], params={"searchby": st_num})
            if resp:
                soup = bs(resp.text, "html5lib")
                rows = soup.select(self.settings["row_sel"])
                if not rows or "No Solicitations or Bids at this time" in str(_g(rows, "0", "")):
                    break
                logging.info(f'{len(rows)} bid(s) on "{status}" page')
                yield from rows
            else:
                logging.error(
                    "No response from index page: %s",
                    self.urljoin(self.settings["index_url"] + "?searchby=" + str(st_num)),
                )
                yield from []

    def bid_id_from_row(self, row):
        if _c(tag_text(row)):
            return get_hash(str(row))

    def scrape_bid(self, bid, row):
        core.common.objects.set_bid_attributes(
            bid,
            {x.get("data-th"): _c(tag_text(x)) for x in row.select("td[data-th]")},
            {
                "bidNumber": "RFP Number",
                "title": "Title",
                "dueDate": ("Closing", core.common.parse.parse_date),
            },
        )
        found_id = re.search(r"\&id\=(\d+)", _g(row, "a.href", ""))
        if found_id:
            surl = f"/rfp-detail/?id={found_id.group(1)}"
        else:
            surl = _g(row, "a.href")
        bid.sourceURL = self.urljoin(surl)
        bid.description = f"<h4>{bid.title}</h4>"
        bid_page, files = bs(self.get(bid.sourceURL).text, "html5lib"), []
        ul_l = bid_page.select_one("ul.detail-list")
        if ul_l:
            pdate = ul_l.find("label", text=re.compile(r"Start Date:"))
            if pdate and pdate.find_next_sibling("span", class_="detail-list-value"):
                bid.postedDate = core.common.parse.parse_date(
                    tag_text(pdate.find_next_sibling("span", class_="detail-list-value"))
                )
            bid.description += "<hr>" + core.common.soup.make_description(ul_l).replace(
                "<div>Please wait while your download link is being generated.</div>",
                "",
            )
        data_submission_key, arf_fieldset = bid_page.select_one(
            "form.arfshowmainform"
        ), bid_page.select_one("div.arf_fieldset.arf_materialize_form")
        if arf_fieldset and self.settings["document_download"] and data_submission_key:
            fill_in = {
                x.get("placeholder"): x.get("name")
                for x in bid_page.select("input[name^='item_meta[']")
            }
            filled_in = {fill_in[k]: v for k, v in self.settings["sub_form"].items()}
            hids = core.common.soup.get_hidden_inputs(bid_page)
            hids["arf_http_referrer_url"], hids["arf_tooltip_settings_120"] = "", ""
            hids.pop("arfmainformurl")
            hids.pop(None)
            st = bid_page.find("input", attrs={"value": "form_filter_st"})
            if st and st.find_previous("input", attrs={"value": True}):
                self.session.headers.update({"Referer": bid.sourceURL})
                pd = (
                    list(hids.items())
                    + [
                        ("fake_text", ""),
                        ("using_ajax", "yes"),
                        (
                            "form_filter_st",
                            st.find_previous("input", attrs={"value": True}).get("value"),
                        ),
                        ("form_filter_kp", str(random.randint(50, 70))),
                        (data_submission_key.get("data-submission-key"), ""),
                        ("form_random_key", data_submission_key.get("data-random-id")),
                    ]
                    + list(filled_in.items())
                )
                self.wait()
            #     r = self.post("http://www.florenceaz.gov/?plugin=ARForms", data=pd)
            #     if r and "error" not in r.text.lower():
            #         self.session.headers.update({"X-Requested-With": "XMLHttpRequest"})
            #         time.sleep(0.1)
            #         dl_tag = bs(
            #             self.post(
            #                 "http://www.florenceaz.gov/wp-admin/admin-ajax.php",
            #                 data={
            #                     "form_id": hids.get("form_id"),
            #                     "action": "arf_dig_pro_get_donwload_link",
            #                 },
            #             ).text,
            #             "html5lib",
            #         )
            #         files += list(self.scrape_links(dl_tag))
            #     else:
            #         logging.warning(
            #             f"Problem submitting form! Check form payload for URL: {bid.sourceURL}"
            #         )
            # else:
            #     logging.warning("Could not find filter key!")
        dl_tab = bid_page.select_one("div.detail-content > table.responsive")
        if dl_tab:
            files += list(self.scrape_links(dl_tab))
        return lambda: files


if __name__ == "__main__":
    Main().run()

