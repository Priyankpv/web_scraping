import logging
import re
from functools import partial
from itertools import takewhile

import pydash as py_
from bs4 import BeautifulSoup as bs
import pdftotext
import core
from core.bid_scraper_plus import BidScraper
from core.common import get_hash, _tt
from core.common.functions import compose, split_at
from core.common.soup import tag_text, wrap_tags
from core.bid_scraper_plus import BidScraper, SkipBid

date_re = re.compile(r'(\w+\s\d{2}\,\s\d{4})')
def get_date_from_files(bid, fileinfos):
    for dl in fileinfos:
        dump = ""
        if dl.path:
            try:
                if dl.path.endswith(".pdf"):
                    dump = pdftotext.PDF(open(dl.path, "rb"))
                else:
                    logging.info(f"Could not dump file format: ({dl.ext})")
                dump = py_.clean(" ".join(dump))
            except Exception as ex:
                raise SkipBid(f"Error dumping file to text! Exception: {ex} FILE_URL: {dl.url}")
            if dump:
                if fddate := date_re.search(dump):
                    # dump = dump[:997] + "..." if len(dump) > 1000 else dump
                    return core.parse_date(fddate.group(1))
        else:
            logging.info(f"File could not be downloaded. FILE_URL: {dl.url}")

class Main(BidScraper):
    settings = {
        "version": "2.2.0",
        "script_name": "college_dupage",
        "base_url": "https://www.cod.edu",
        "created_by": "dparisi@govspend.com",
        "last_modified_by": "dparisi@govspend.com",
        "agency_type": "Higher Education",
        "agency_name": "College of DuPage",
        "agency_state": "IL",
        "index_url": "/about/purchasing/requests/index.aspx",
        "download_payload": {
            "firstname": "Ron",
            "lastname": "Bjornsson",
            "companyname": "Smartprocure",
            "emailaddress": "rbjornsson@smartprocure.us",
            "phone": "9544209900",
            "fax": "",
            "streetaddress": "700 W Hillsboro Blvd Ste 4-101",
            "city": "Deerfield Beach",
            "state": "FL",
            "zipcode": "33441",
        },
    }

    def fetch_rows(self):
        def parse_index_row(html):
            if _extract_path := html.select_one('a[href="#rfps"]'):
                _extract_path.parent.extract()
            if _extract := html.find("h2", text="Bids"):
                _extract.extract()
            main_tags = html.select("main#main-content > *")
            filter_strings = [
                r"Under Review - Target Board Approval Date",
                r"Contact Information",
            ]
            if py_.find_index(main_tags, lambda mt: mt.name == "h3") != -1:
                return compose(
                    partial(
                        filter,
                        lambda tag: _tt(tag)
                        and not re.search("|".join(filter_strings), _tt(tag), re.I),
                    ),
                    partial(map, wrap_tags),
                    partial(split_at, lambda tag: tag.name == "h3", include="second"),
                    partial(filter, lambda tag: tag.name and _tt(tag) and tag.name != "h2"),
                )(main_tags)
            else:
                return filter(lambda mt: py_.get(mt, "a"), main_tags)

        self.index_url = self.settings["index_url"]
        if res := self.get(self.index_url):
            index_soup = bs(res.text, "html5lib")
            if self.status == "open":
                yield from parse_index_row(index_soup)
            elif self.status == "closed":
                for index in index_soup.select(".container aside#sidebar--second ul li")[::-1][:5]:
                    self.index_url = py_.get(index, "a.href")
                    index_soup = bs(self.get(self.index_url).text, "html5lib")
                    yield from parse_index_row(index_soup)

    def bid_id_from_row(self, row):
        return get_hash(_tt(row))

    def scrape_bid(self, bid, row):
        def scrape_downloads(soup, bid):
            self.session.headers.update({"referer": bid.bidURL, "TE": "Trailers"})
            dlresp = self.post(
                "/_resources/ldp/forms/ldp-forms.ldp-forms-connector.php",
                data={
                    **core.common.soup.get_hidden_inputs(soup),
                    **self.settings["download_payload"],
                },
            )
            soupy = bs(dlresp.text, "lxml")
            return [
                a.attrs["href"].replace("\\", "").strip('"')
                for a in soupy.select("a[href]")
                if "mailto:" not in a.get("href")
            ]

        if title_tag := py_.get(row, "h3") or py_.get(row, "a"):
            bid.title = _tt(title_tag)
            if bid_no_re_search := re.search(
                r"(20\d\d[ -] ?[A-Z\d]+)\s-?(.+)", bid.title.replace("‐", "-")
            ):
                bid.bidNumber, bid.title = bid_no_re_search.groups()
        else:
            logging.error("row is not expected format!")
        bid.description = py_.clean(core.common.objects.make_description_from_obj(row, header=None))

        if self.status == "open":
            if row_a_href := py_.get(row, "a.href"):
                bid.sourceURL = bid.bidURL = self.urljoin(row_a_href)
            elif row_href := py_.get(row, "href"):
                bid.sourceURL = bid.bidURL = self.urljoin(row_href)
            if p_tag := py_.get(row, "p"):
                bid.dueDate = core.common.parse.parse_date(_tt(p_tag))
            if detail_res := self.get(bid.bidURL):
                dsoup = bs(detail_res.text, "html5lib")
                return lambda: scrape_downloads(dsoup, bid)

        elif self.status == "closed":
            bid.bidURL = bid.sourceURL = self.urljoin(f"{self.index_url}#{bid.bidNumber}")
            files =  self.download_files(list(self.scrape_links(row)), bid)
            dd = get_date_from_files(bid, files)
            if dd:
                bid.dueDate = dd
            else:
                page_date = re.search(r"bids-(\d+)\.aspx", self.index_url)
                bid.dueDate = core.common.parse.parse_date(f"12/31/{page_date.group(1)}")
            extra_info = []

            if awarded_info := row.find(text=re.compile("Awarded Vendor")):
                extra_info += [
                    j
                    for j in takewhile(
                        lambda x: x.name != "a", [i for i in awarded_info.next_siblings]
                    )
                    if tag_text(j)
                ]
            elif h3_test := row.find_parent("h3"):
                tmp = list(
                    takewhile(
                        lambda x: (x.name != "h3" and x.name != "h2") and not py_.get(x, "a"),
                        h3_test.next_siblings,
                    )
                )
                for ex in tmp:
                    if py_.get(ex, "name") == "p":
                        extra_info += ex.contents

            awarded_info = [awarded_info] + extra_info
            if awarded_info:
                awarded_info = py_.compact(
                    [
                        py_.clean(
                            re.sub(
                                "Awarded Vendors?:|Bid Item \d?:|One Year Contract.+|Bid Rejected|Closed: No proposals received",
                                "",
                                _tt(i),
                            )
                        )
                        for i in awarded_info
                        if i
                        and not re.search(
                            "Rejected|Due Date|Under Review|Addendum|All bids are due to",
                            tag_text(i),
                            re.I,
                        )
                    ]
                )
                if len(awarded_info) > 1:
                    bid.awardedTo = "Multiple Vendors"
                elif awarded_info:
                    bid.awardedTo = py_.head(awarded_info)
            # if download_href_list := row.select('a[href*="requests/"]'):
            #     return lambda: [
            #         ("", self.urljoin(download_href.get("href")))
            #         for download_href in download_href_list
            #     ]
            # else:
            #     return lambda: [("", py_.get(row, "href"))]


if __name__ == "__main__":
    Main().run()

