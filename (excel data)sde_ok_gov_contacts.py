import numpy as np
import pandas as pd
import validators
from pydash import py_

from core.contact.item import Contact
from core.contact.spider import ContactCrawler, ContactSpider
from scrapers.contacts.us.ok.sde_ok_gov_contacts.districts_lookup import districts_lookup
from scrapers.contacts.us.ok.sde_ok_gov_contacts.schools_lookup import schools_lookup


class Main(ContactSpider):
    custom_settings = {
        "script_name": "sde_ok_gov_contacts",
        "base_url": "https://sde.ok.gov",
        "version": "1.0.2",
        "created_by": "jedmonson@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "org_name": "Oklahoma State Department of Education",
        "org_id": 54114,
        "org_state": "OK",
        "start_urls": [
            "https://sde.ok.gov/sites/default/files/documents/files/FY23%20Certified%20Email%2002152023.xlsx",
            "https://sde.ok.gov/sites/default/files/documents/files/FY23%20Support%20Email%2002152023.xlsx",
        ],
    }

    field_map = {
        "TeacherNumber": "contact_number",
        "Support ID": "contact_number",
        "job Desc": "title",
        "EMAIL": "email",
        "Last Name": "last_name",
        "First Name": "first_name",
        "School Site": "school",
        "Site Code": "site_code",
    }

    contact_fields = list(Contact.__dict__["fields"].keys()) + ["agency_state"]

    def parse(self, response, *args, **kwargs):
        # load
        df = pd.read_excel(response.body, header=1, dtype=str)

        # prep
        df = df.rename(
            mapper=py_().clean().thru(lambda x: self.field_map.get(x, x)).snake_case(), axis=1
        )
        df = df.applymap(py_.clean)
        df = df.replace({"nan": np.nan})

        # make lookup keys
        df["district|county"] = df["district"] + "|" + df["county"]
        df["school|district"] = df["school"] + "|" + df["district"]

        # apply lookups - schools then districts
        df["org"] = df["school|district"].apply(schools_lookup.get)
        df.loc[df["org"].isnull(), "org"] = df.loc[df["org"].isnull(), "district|county"].apply(
            districts_lookup.get
        )

        # expand results from lookup into dataframe
        df = pd.concat(
            [df.drop(["org"], axis=1), df["org"].apply(pd.Series, dtype="object")], axis=1
        )
        df["org_id"] = pd.to_numeric(df["org_id"]).astype("Int32")

        # normalize email strings
        df.loc[df["email"].isnull(), "email"] = ""
        df["is_email_valid"] = df["email"].apply(lambda x: bool(validators.email(x)))
        df.loc[df["is_email_valid"] == False, "email"] = np.nan

        # set default org_name, org_id, org_state
        df["org_name"] = self.settings["org_name"]
        df.loc[df["org_id"].isnull(), "org_id"] = self.settings["org_id"]
        df["org_state"] = self.settings["org_state"]

        # group duplicate contact rows by contact/org to consolidate fields
        grouped = df.groupby(by=["contact_number", "org_id"])

        # use first row to make new data frame
        df = grouped.agg("first")

        # join unique titles
        df["title"] = grouped["title"].unique().agg("; ".join)

        # prep for export
        df = df.reset_index()
        df = df.replace({np.nan: ""})
        df = df.loc[:, ~df.columns.duplicated()].copy()

        yield from map(lambda x: Contact(py_.pick(x, *self.contact_fields)), df.to_dict("records"))


if __name__ == "__main__":
    ContactCrawler(Main)

