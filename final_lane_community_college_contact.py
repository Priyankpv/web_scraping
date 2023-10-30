import re
import string

from pydash import py_
from scrapy import Request

import core
from common.misc import clean_phone, parse_name
from core.contact import Contact
from core.contact.spider import ContactCrawler, ContactSpider


class Main(ContactSpider):
    custom_settings = {
        "script_name": "lane_community_college",
        "version": "1.0.0",
        "created_by": "pvamja@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Lane Community College",
        "agency_state": "or",
        "org_id": 94194,
        "base_url": "https://directory.lanecc.edu/ln",
        "start_urls": ["?starts_with=a&page=0"],
        "row_sel": ".view-content>div>div",
    }

    def start_requests(self):
        for url in string.ascii_lowercase[0:26]:
            yield Request(
                url=self.urljoin("?starts_with=" + url), callback=self.parse, meta={"page": True}
            )

    def parse(self, resp):
        for contact_tag in resp.css(self.custom_settings["row_sel"]):
            person_dict = {
                re.sub(
                    r"field--name-field-(?:lom-lep|lep|lom)-",
                    "",
                    py_.get(py_.get(l, "attrib.class").split(), "1"),
                ): self.tag_text(l)
                for l in contact_tag.css(".field")
            }
            if py_.get(person_dict, "classification"):
                contact = Contact(**parse_name(py_.get(person_dict, "display-name")))
                core.set_obj_attributes(
                    contact,
                    person_dict,
                    {
                        "title": "classification",
                        "email": ("display-email", lambda de: re.sub(r"^Email ", "", de)),
                        "department": "org-ref",
                        "direct_phone": ("primary-phone", lambda ph: clean_phone(ph) if ph else ""),
                        "address_1": "primary-office",
                    },
                )
                yield contact

        page = resp.css('.pagination a[title*="last"]::attr(href)').get()
        if page and resp.meta["page"]:
            final_page_no = int(page.split("=")[-1])
            for i in range(1, final_page_no + 1):
                next_page_url = self.urljoin(page.replace(f"={final_page_no}", f"={i}"))
                yield Request(url=next_page_url, callback=self.parse, meta={"page": False})


if __name__ == "__main__":
    ContactCrawler(Main)
