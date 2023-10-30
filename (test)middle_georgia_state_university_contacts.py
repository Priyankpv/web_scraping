import scrapy
from pydash import py_

from common.misc import _tt, clean_phone, parse_name, parse_phone, phone_reg
from core.contact import Contact
from core.contact.spider import ContactCrawler, ContactSpider
import core

class Main(ContactSpider):
    custom_settings = {
        "script_name": "middle_georgia_state_university_contacts",
        "version": "1.0.0",
        "created_by": "pvamja@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "Middle Georgia State University",
        "agency_state": "GA",
        "org_id": 8393,
        "base_url": "https://www.mga.edu/directory/",
        "row_sel": "table > tr",
    }

    def start_requests(self):
        headers = {
            "Accept": " text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        yield scrapy.Request(
            url=self.urljoin("index.php?search=true"),
            method="POST",
            body="searchText=",
            headers=headers,
        )

    def parse(self, resp):
        for contact_tag in resp.css(self.custom_settings["row_sel"]):
            contact_header = ['name','phone','dep','title']
            contact_detail = [(self.tag_text(i.css('a')).split('-')[0]).replace('Dr.','') if i.css('a') else self.tag_text(i) for i in contact_tag.css("td")] + [self.tag_text(i.css('span')) for i in contact_tag.css("td") if i.css('span')]
            # for i in contact_tag.css("td"):
            #   if i.css('a'):
            #       contact_detail.append((self.tag_text(i.css('a')).split('-')[0]).replace('Dr.',''))
            #   else:
            #       contact_detail.append(self.tag_text(i))
            #   if i.css('span'):
            #       contact_detail.append(self.tag_text(i.css('span')))
            # for i in contact_tag.css("td"):
            #   if i.css('a[href*="people.php?"]'):
            #       contact_detail.append((self.tag_text(i.css('a')).split('-')[0]).replace('Dr.',''))
            #   elif i.css('a'):
            #       contact_detail.append(self.tag_text(i.css('a')))
            #   else:
            #       contact_detail.append(self.tag_text(i).replace('.','-'))
            #   if i.css('span'):
            #       contact_detail.append(self.tag_text(i.css('span')))
              
            
            contact_dict = dict(zip(contact_header,contact_detail))                   
            contact = Contact(**parse_name(contact_dict["name"]))
            core.set_obj_attributes(
            contact,
            contact_dict,
            {
                "title": "title",
                "department": "dep",
                "direct_phone": ("phone", parse_phone),
            },)
            yield contact


if __name__ == "__main__":
    ContactCrawler(Main)

