import logging
import os
import re
from pathlib import Path
from itertools import count
import ocrmypdf
import textract
from bs4 import BeautifulSoup as bs
from pydash import py_
from core.common import get_hash, parse_date, _tt
from core.contract_scraper_plus import ContractScraper

front = "|".join(["contract award to", "award .+? contract to ?t?h?e? "])
back = "|".join([" for ", ", for "])
find_comp = re.compile(rf"(?:{front})(.+?)(?:{back}).+?(fiscal impact)", re.I)

logging.getLogger("ocrmypdf").disabled = True
logging.getLogger("ocrmypdf._sync").disabled = True
logging.getLogger("tqdm").disabled = True
logging.getLogger("ocrmypdf._exec.tesseract").disabled = True


class Main(ContractScraper):
    settings = {
        "version": "1.0.2",
        "script_name": "city_san_clemente_contracts",
        "base_url": "https://www.san-clemente.org",
        "created_by": "jclervil@govspend.com",
        "last_modified_by": "pvamja@govspend.com",
        "agency_name": "City of San Clemente",
        "agency_state": "CA",
        "agency_type": "State & Local",
        "agency_website": "https://www.san-clemente.org",
        "index_url": "/government/city-council/packets",
        "row_sel": "div.document_widget ul li > a[href]",
    }

    def pre_execute(self):
        if not self.settings["document_download"]:
            logging.info(
                "Setting document_download to true. This script relies on extracting text from documents."
            )
            self.settings["document_download"] = True

    def fetch_rows(self):
        if self.status == "open":
            res = self.get(self.settings["index_url"])
            if not res:
                logging.error(
                    "Response failed on index page: %s",
                    self.urljoin(self.settings["index_url"]),
                )
            packet_years = bs(res.text, "html5lib").select(self.settings["row_sel"])
            for n, yr in enumerate(packet_years[:-1]):
                pakets_href = yr.get("href")
                for i in count(1):
                  yr_resp = self.get(pakets_href+'/-npage-'+str(i))
                  if not yr_resp and i == 1:
                      logging.error("Response failed on index page: %s", self.urljoin(pakets_href))
                  content_links = bs(yr_resp.text, "html5lib").select(
                      "div.document_widget ul a.content_link"
                  )
                  for link in content_links:
                      href = py_.get(link, "href")
                      link_resp = self.get(href)
                      if not link_resp:
                          logging.error("Response failed on index page: %s", self.urljoin(href))
                      if "/home/showpublisheddocument/" in href:
                          yield dict(title=_tt(link), href=href, url=href, yr=n, date='')
                      else:
                          rows = bs(link_resp.text, "html5lib").select(
                              "div.document_widget ul a.content_link"
                          )
                          for row in rows:
                              row_text = _tt(row)
                              if "contract" in row_text.lower():
                                  yield dict(title=row_text, href=row.get("href"), url=href, yr=n, date=_tt(link))
                  if 'Next' in str(bs(yr_resp.text, "html5lib").select_one(".disabled.pg-button.pg-next-button")):
                      break

    def contract_id_from_row(self, row):
        if row["title"]:
            return get_hash(str(row))

    def scrape_contract(self, contract, row):
        def get_vendor_name(dl, dump=""):
            try:
                dump = textract.process(dl.path).decode("utf-8")
            except Exception as ex:
                logging.info(
                    "Error dumping file to text! Exception: %s FILE_PATH: %s",
                    ex,
                    dl.path,
                )
            if not py_.clean(dump) and row["yr"] == 0:
                dlpath = Path(self.directories["documents"]) / contract.sourceID
                sidecar_file = dlpath / ("sidecar_file" + ".txt")
                ocrd_file = dlpath / ("processed_sidecar_file")
                try:
                    exit_code = ocrmypdf.ocr(
                        dl.path, ocrd_file, sidecar=sidecar_file, progress_bar=False
                    )
                    if exit_code == 0:
                        dump = open(sidecar_file, "r").read()
                        os.remove(sidecar_file)
                except Exception as ex:
                    logging.warning("Problem while attempting to OCR file! Exception: %s", ex)
            if dump:
                comp = find_comp.search(py_.clean(dump))
                if comp:
                    contract.companyName = py_.clean(comp.group(1))
                    if len(dump) > 1000:
                        dump = dump[:997] + "..."
                    dump = dump.replace("\n", "<br>")
                    contract.contractDescription = py_.clean(
                        f"<center><blockquote>{dump}</blockquote></center>"
                    )

        contract.contractTitle = contract.contractDescription = row["title"]
        contract.companyName = "N/A"
        contract.contractEndDate = parse_date(row["date"]) if row["date"] else ''
        contract.sourceURL = contract.contractURL = self.urljoin(
            f'{row["url"]}#{contract.contractNumber}'
        )
        file_info = self.download_file(contract, row["href"])
        if file_info:
            get_vendor_name(file_info)


if __name__ == "__main__":
    Main().run()

