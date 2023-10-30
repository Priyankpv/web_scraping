import re
from core.common import parse_name, parse_phone
from core.common.objects import filter_contact_obj
from core.contact import Contact
from core.contact.spider import ContactCrawler, ContactSpider


class Main(ContactSpider):
    custom_settings = {
        "script_name": "nhti_edu",
        "version": "1.0.0",
        "created_by": "jedmonson@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "NHTI-Concord's Community College",
        "agency_state": "NH",
        "org_id": 169444,
        "base_url": "https://www.nhti.edu/",
        "start_urls": ["/directory/"],
    }

    def parse(self, resp):
        headers = list(map(self.tag_text, resp.css(".row .table-staff table > thead > tr > th")))
        for row in resp.css(".row .table-staff table > tbody > tr"):
            meta = dict(zip(headers, row.css("td")))
            if self.tag_text(meta["Department"]):
                yield filter_contact_obj(
                    Contact(
                        {
                            **parse_name(self.tag_text(meta["Name"].css("a h2"))),
                            "title": self.tag_text(meta["Title"])
                            if self.tag_text(meta["Title"])
                            else self.tag_text(meta["Department"]),
                            "department": self.tag_text(meta["Department"])
                            if self.tag_text(meta["Title"])
                            else "",
                            "email": (meta["Email"]).css('a::attr("title")').get(""),
                            "phone": parse_phone(re.sub(r"603\W*603", "603", self.tag_text(meta["Phone"])))
                            if self.tag_text(meta["Phone"])
                            else "",
                            "address_1": self.tag_text(meta["Location"]),
                        }
                    )
                )
        yield from resp.follow_all(
            css = '.js-wpv-pagination-next-link',
             callback = self.parse
        )

if __name__ == "__main__":
    ContactCrawler(Main)

