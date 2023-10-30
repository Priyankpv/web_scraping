from core.contact.spider import ContactSpider, ContactCrawler
from core.contact import Contact
from common.misc import clean_phone
from scrapy import Request
import string


class Main(ContactSpider):
  custom_settings = {
    'script_name':      'lane_community_college',
    'version':          '1.0.0',
    'created_by':       'pvamja@govspend.com',
    'last_modified_by': 'pvamja@govspend.com',
    'agency_name':      'Lane Community College',
    'agency_state':     'or',
    'org_id':           94194,
    'base_url':         'https://directory.lanecc.edu/ln',
    'start_urls':       ['?starts_with=a&page=0'],
    'row_sel':          '.view-content>div>div',
  }

  def start_requests(self):
      for url in string.ascii_lowercase[0:26]:
          yield Request(
            url=self.urljoin("?starts_with="+url), callback=self.parse,meta={'page':True})

  

  def parse(self, resp):
    for contact in resp.css(self.custom_settings['row_sel']):
      name = contact.css('h2 a[hreflang]::text').get().split(' ')
      email = contact.css('.card-body.d-flex.flex-column .field__item a[href*="mailto:"]::text').get('')
      address_1 = contact.css('.field.field--name-field-lep-primary-office.field--type-entity-reference.field--label-inline .field__item::text').get('')
      department = contact.css('.field.field--name-field-lom-org-ref.field--type-entity-reference.field--label-hidden.field__item > a[href]::text').get('')
      phone = contact.css(' .field.field--name-field-lep-primary-phone.field--type-telephone.field--label-inline .field__item a::text').get('(541) 463-3000')
      title = contact.css('.field.field--name-field-lom-classification.field--type-string.field--label-hidden.field__items > div::text').get('')
      
      yield Contact(
              {
                  'first_name' : name[0],
                  "last_name" : name[1],
                  "title": title,
                  "department": department,
                  "email": email,
                  "direct_phone": clean_phone(phone),
                  "address_1": address_1,
              }
          )

    page = resp.css('.pagination a[title*="last"]::attr(href)').get()
    if page and resp.meta['page']:
      final_page_no = int(page.split('=')[-1])
      for i in range(1,final_page_no+1):
        next_page_url = self.urljoin(page.replace(f"={final_page_no}",f"={i}"))
        yield Request(url=next_page_url,callback=self.parse,meta={'page':False})
    
      
    
if __name__ == '__main__':
  ContactCrawler(Main)
