import logging

from core.common import parse_phone, phone_reg
from core.contact.scraper import ContactScraper


def main(base):
    resp = base.get(base.settings["json_url"])
    if resp:
        json_data = resp.json()
        for person in json_data:
            contact_dict = {}
            contact_dict["first_name"] = person["firstName"]
            contact_dict["last_name"] = person["lastName"]
            contact_dict["title"] = person["title"]
            contact_dict["department"] = person["department"]
            contact_dict["email"] = person["email"]
            contact_dict["phone"] = (
                parse_phone(t.group(0)) if (t := phone_reg.search(person["phone"])) else ""
            )
            filter_contact = base.filter_contact_obj(contact_dict)
            if filter_contact:
                base.write_to_output(contact_dict)
    else:
        logging.error("No response from index page: %s" % base.urljoin(base.settings["json_url"]))


settings = {
    "script_name": "bowie_state_university_contacts",
    "version": "1.0.0",
    "agency_name": "Bowie State University",
    "org_id": 15471,
    "agency_state": "MD",
    "base_url": "https://www.bowiestate.edu",
    "index_url": "/directories/faculty-and-staff-directory/index.php",
    "json_url": "/_resources/php/get-json-feed.php?path=/directories/faculty-and-staff-directory&type=directory&filter=&max=&externalPath=/_resources/xml/WebCampusDirectory.xml",
    "created_by": "kpasqualini@govspend.com",
    "last_modified_by": "kpasqualini@govspend.com",
}


if __name__ == "__main__":
    ContactScraper(settings).run(main)

