from core.contact.spider import ContactSpider, ContactCrawler
from core.contact import Contact
from common.misc import parse_name
from pydash import py_
from common.misc import _tt, parse_name, parse_phone, phone_reg
from common.misc import clean_phone, parse_name
import scrapy

class Main(ContactSpider):
  custom_settings = {
    'script_name':      'middle_georgia_state_university_contacts',
    'version':          '1.0.0',
    'created_by':       'pvamja@govspend.com',
    'last_modified_by': 'pvamja@govspend.com',
    'agency_name':      'Middle Georgia State University',
    'agency_state':     'GA',
    'org_id':           8393,
    'base_url':         'https://www.mga.edu/directory/',
    'row_sel':          'table > tr',
  }
  
  def start_requests(self):
      headers = {'Accept': ' text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
  'Accept-Encoding': 'gzip, deflate, br',
  'Content-Type': 'application/x-www-form-urlencoded',
  'Host': 'www.mga.edu',
  'Origin': 'https://www.mga.edu',
  'Pragma': 'no-cache',
  'Referer': 'https://www.mga.edu/directory/',
  'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
}
      yield scrapy.Request(url = self.urljoin('index.php?search=true'), method='POST', body='searchText=', headers=headers)

  def parse(self, resp):
      for contact_tag in resp.css(self.custom_settings["row_sel"]):
            contact_dict = {}
            title = contact_tag.css("span.caption")
            if title:
                contact_dict["title"] = self.tag_text(title)
                name = contact_tag.css("a[href]")
                if name:
                    test_name = self.tag_text(name).split(" - ")[0]
                    if "Dr." in test_name:
                        s_name = (test_name.split(".")[1]).split( )
                        contact_dict["name"] = s_name[0]+s_name[1] 
                    else:
                        s_name = test_name.split( )
                        contact_dict["name"] = s_name[0]+s_name[1]                
                dept = contact_tag.css("td:nth-of-type(3) a")
                if dept:
                    contact_dict["department"] = self.tag_text(dept)
                phone = contact_tag.css("td:nth-of-type(2)")
                if phone:
                    phone_test = phone_reg.search(self.tag_text(phone))
                    if phone_test:
                        contact_dict["phone"] = parse_phone(phone_test.group(0))
                name = contact_dict.pop("name")
                contact_dict.update(parse_name(name))
            yield Contact(contact_dict)
       
if __name__ == '__main__':
  ContactCrawler(Main)
