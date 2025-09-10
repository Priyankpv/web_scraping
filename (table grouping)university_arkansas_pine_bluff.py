import datetime
import logging

import dateutil.parser as dp
from bs4 import BeautifulSoup as bs
from pydash import py_

import core
from core.bid_scraper_plus import BidScraper
from core.common import _tt, datefmt
from core.common.file_download import clean_filename
from core.common.objects import get_hash_from_dict

today = core.common.variables.today
yest_date = (today - datetime.timedelta(days=1)).strftime(datefmt)


class Main(BidScraper):
    settings = {
        "version": "1.1.2",
        "script_name": "university_arkansas_pine_bluff",
        "base_url": "http://www.uapb.edu",
        "created_by": "jclervil@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "University of Arkansas at Pine Bluff",
        "agency_state": "AR",
        "agency_type": "State & Local",
        "agency_website": "http://www.uapb.edu",
        "index_url": "/administration/finance_administration/purchasing/bids.aspx",
        "row_sel": "div.formcontgroup > table",
    }

    header_row = {
        "Bid Number": "b_num",
        "Description": "title",
        "Date": "date",
        "Document": "files",
    }

    def fetch_rows(self):
        if self.status == "closed":
            return
        all_bids = True if self.settings["all_solicitations"] else False
        self.session.verify = False
        resp = self.get(self.settings["index_url"])
        if resp:
            tables = bs(resp.text, "html5lib").select(self.settings["row_sel"])
            for table in tables:
                parsed_rows = {}
                header, *bid_rows = table.select("tbody tr")
                header = [
                    (
                        self.header_row[i]
                        if (i := next(filter(lambda x: x in _tt(v), self.header_row.keys()), ""))
                        else ""
                    )
                    for v in header.select("td")
                ]
                for row in filter(_tt, bid_rows):
                    if "none at this time" in _tt(row).lower():
                        continue
                    cells = {
                        h: i if (i := _tt(v)) else ""
                        for n, v in enumerate(row.select("td"))
                        if (h := header[n])
                    }
                    cells["files"] = list(self.scrape_links(row))
                    cells["date"] = (
                        dp.parse(i)
                        if (i := core.common.parse.parse_date(py_.get(cells, "date", ""), False))
                        else ""
                    )
                    if not cells["date"]:
                        if cells["b_num"] in parsed_rows:
                            parsed_rows[cells["b_num"]]["files"].extend(cells["files"])
                        else:
                            parsed_rows[cells["b_num"]] = {"files": cells["files"]}
                    else:
                        if cells["b_num"] in parsed_rows:
                            if "title" not in parsed_rows[cells["b_num"]]:
                                parsed_rows[cells["b_num"]].update(py_.pick(cells, "title", "date"))
                            parsed_rows[cells["b_num"]]["files"].extend(cells["files"])
                            parsed_rows[cells["b_num"]]["title"] = cells["title"]
                        else:
                            parsed_rows[cells["b_num"]] = py_.omit(cells, "b_num")
                if all_bids:
                    yield from parsed_rows.items()
                else:
                    yield from filter(lambda v: v[1]["date"] >= today, parsed_rows.items())
        else:
            logging.error(
                "No content returned from detail page! %s",
                self.urljoin(self.settings["index_url"]),
            )

    def bid_id_from_row(self, row):
        def get_dict_hash(d):
            return get_hash_from_dict(
                {
                    **row[1],
                    "b_num": row[0],
                    "date": row[1]["date"].strftime(core.common.constants.datefmt),
                }
            )

        if text := get_dict_hash(row):
            return text

    def scrape_bid(self, bid, row):
        core.common.objects.set_bid_attributes(
            bid,
            row[1],
            {
                "title": "title",
                "dueDate": ("date", lambda x: x.strftime(core.common.constants.datefmt)),
                "description": "title",
            },
        )
        bid.bidNumber = row[0]
        bid.sourceURL = self.urljoin(
            f'{self.settings["index_url"]}#{clean_filename(bid.bidNumber)}'
        )
        return lambda: row[1]["files"]


if __name__ == "__main__":
    Main().run()

