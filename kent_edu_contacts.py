from core.contact.spider import ContactSpider, ContactCrawler
from core.contact import Contact
from common.misc import parse_name, clean_phone
from scrapy import Request
from pydash import py_
import re
import core

class Main(ContactSpider):
  custom_settings = {
    'script_name':      'kent_edu_contacts',
    'version':          '1.0.0',
    'created_by':       'pvamja@govspend.com',
    'last_modified_by': 'pvamja@govspend.com',
    'agency_name':      'Kent State University at Trumbull',
    'agency_state':     'OH',
    'org_id':           181971,
    'base_url':         'https://www.kent.edu/',
    'start_urls':       ['trumbull/faculty-directory'],
    'row_sel':          '.views-element-container .pane-content ul li > a::attr("href")',
  }

  def parse(self, resp):
    for contact_tag in set(resp.css(self.custom_settings["row_sel"]).getall()):
      yield Request(contact_tag, callback= self.parse_contact)

  def parse_contact(self, row):
    person_dict =  {
                re.sub(
                    r"views-field-(?:field)?-?(?:profile)?-?",
                    "",
                    py_.get(py_.get(l, "attrib.class").split(), "1"),
                ): self.tag_text(l)
                for l in row.css(".profile-contact-area .views-field")
            }
    person_dict['person_title'] = self.tag_text(row.css('.profile-contact-area .job-title'))
    person_dict['bio'] = self.tag_text(row.css('.panel-inner-wrap.clearfix .field-content p'))
    if person_dict['person_title']:
      contact = Contact(**parse_name(py_.get(person_dict, "title")))
      core.set_obj_attributes(
        contact,
        person_dict,
        {
          "title": "person_title",
          "department": "job-department",
          "address_1": ("campus-location", lambda de: re.sub(r"Campus: ", "", de)),
          "email": ("email-work", lambda de: re.sub(r"Email: ", "", de)),
          "direct_phone": ("phone-work", clean_phone),
          "biography": "bio"
        },
      )
      yield contact

if __name__ == '__main__':
  ContactCrawler(Main)
