import logging

import pandas as pd
from bs4 import BeautifulSoup as bs
from pydash import py_

from core.common import parse_name, parse_phone, phone_reg, tag_text
from core.contact.scraper import ContactScraper


def get_hidden_inputs(page_content):
    return {
        input.get("name"): input.get("value")
        for input in page_content.find_all("input", {"type": "hidden"})
    }


def main(base):
    initial_page = base.get(base.settings["index_url"])
    if initial_page:
        initial_soup = bs(initial_page.text, "html5lib")
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "X-MicrosoftAjax": "Delta=true",
            "Cache-Control": "no-cache",
            "Origin": "https://apps.dnr.wi.gov/",
            "Referer": "https://apps.dnr.wi.gov/staffdir/contactsearchext.aspx",
        }
        hids = {
            **{
                k: v
                for k, v in get_hidden_inputs(initial_soup).items()
                if k in ["__EVENTVALIDATION", "__VIEWSTATEGENERATOR", "__VIEWSTATE"]
            },
            "ctl00$cphBody$ps1$ScriptManager1": "ctl00$cphBody$ps1$UpdatePanelTop|ctl00$cphBody$ps1$btnSearch",
            "__LASTFOCUS": "",
            "ctl00$cphBody$ps1$txtLastName": "",
            "ctl00$cphBody$ps1$dropLastNameSearchType": "begins",
            "ctl00$cphBody$ps1$txtFirstName": "",
            "ctl00$cphBody$ps1$txtSubjectOfExpertise": " ",
            "ctl00$cphBody$ps1$dropSOEFilter": "contains",
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__ASYNCPOST": "true",
            "__SCROLLPOSITIONX": "0",
            "__SCROLLPOSITIONY": "0",
            "ctl00$cphBody$ps1$btnSearch": "Search",
            "ctl00$cphBody$ps1$dropSOECounty": "0",
        }
        county_list = [
            (py_.get(c, "value", ""), tag_text(c))
            for c in initial_soup.select("select#cphBody_ps1_dropSOECounty option")
            if tag_text(c) and "Statewide" not in tag_text(c)
        ]
        for county in county_list:
            logging.info("Grabbing table data for %s" % county[1])
            county_page = base.post(
                base.settings["index_url"],
                headers=headers,
                data={
                    **hids,
                    "ctl00$cphBody$ps1$dropSOECounty": str(county[0]),
                },
            )
            if not county_page:
                logging.info("Skipping %s county" % county[1])
            county_soup = bs(county_page.text, "html5lib")
            contact_rows = county_soup.select("table#cphBody_ps1_gvResults tr.RowStyle")
            header = [
                "name",
                "desc",
                "title",
                "subject",
                "counties",
                "phone",
                "email",
                "url",
                "station",
            ]
            logging.info("Parsing %s County" % (county[1]))
            all_data = pd.DataFrame(columns=header)
            for row in contact_rows:
                cells = row.select("td")
                row_dict = {header[i]: tag_text(cells[i]) for i in range(len(cells))}
                row_dict.update(parse_name(row_dict.pop("name")))
                if row_dict["title"] and row_dict["email"] and not row_dict["url"]:
                    all_data = pd.concat(
                        [all_data, pd.DataFrame(row_dict, index=[0])], ignore_index=True
                    )
            del contact_rows
            all_data = all_data.drop(["name", "desc", "url", "station"], axis=1)
            all_data = all_data.drop_duplicates()
            all_data["phone"] = all_data["phone"].apply(
                lambda x: parse_phone(p.group(0) if (p := phone_reg.search(x)) else "")
            )
            columns = all_data.columns.to_list()
            for contact in all_data.itertuples():
                base.write_to_output(
                    dict(
                        {
                            c: py_.get(contact, c, "")
                            for c in columns
                            if c not in ["subject", "counties"]
                        },
                        department=f"{py_.get(contact, 'subject')} Counties Served: {py_.get(contact, 'counties')}",
                    )
                )
            del all_data
            logging.info(county[1] + " county done")
    else:
        logging.error("No response from index page: %s" % base.urljoin(base.settings["index_url"]))


settings = {
    "script_name": "wisconsin_department_natural_resources_contacts",
    "version": "1.1.1",
    "created_by": "jalbu@govspend.com",
    "last_modified_by": "pvamja@govspend.com",
    "agency_name": "Wisconsin Department of Natural Resources",
    "org_id": 29307,
    "agency_state": "WI",
    "base_url": "https://apps.dnr.wi.gov/",
    "index_url": "staffdir/contactsearchext.aspx",
}


if __name__ == "__main__":
    ContactScraper(settings).run(main)

