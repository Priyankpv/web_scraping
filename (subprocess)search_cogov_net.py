import json
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup
from pydash import py_
import subprocess
import core
from core.bid_scraper_plus import BidScraper
from core.common import get_hash, long_re_date

logging.getLogger("ocrmypdf").disabled = True
logging.getLogger("ocrmypdf._sync").disabled = True
logging.getLogger("ocrmypdf._pipeline").disabled = True
logging.getLogger("ocrmypdf._validation").disabled = True
logging.getLogger("tqdm").disabled = True
logging.getLogger("ocrmypdf._exec.tesseract").disabled = True


class Main(BidScraper):
    settings = {
        "version": "1.0.0",
        "script_name": "search_cogov_net",
        "base_url": "https://search.cogov.net/Okcana/Okcana/",
        "created_by": "jedmonson@govspend.com",
        "last_modified_by": "jedmonson@govspend.com",
        "agency_name": "Canadian County",
        "agency_state": "OK",
        "agency_type": "State & Local",
        "agency_website": "https://www.canadiancounty.org/",
        "index_url": "agenda.aspx?subFolders=County%20Bids",
    }

    def pre_execute(self):
        if not self.settings["document_download"]:
            logging.info(
                "Setting document_download to true. This script relies on extracting text from files."
            )
            self.settings["document_download"] = True

    def list_tree(self, link):
        if response := self.get(link):
            logging.info({"fetched_url": link})
            soup = BeautifulSoup(response.text, "html5lib")
            yield from [
                {
                    "text": x.text.strip(),
                    "link": self.urljoin(x.get("href")),
                    "index": self.urljoin(link),
                }
                for x in soup.select("ol#fileList a[href]")
            ]
            for x in soup.select("ul#directoryList a[href]")[::-1]:
                yield from self.list_tree(x.get("href"))
        else:
            logging.error({"error_url": link})

    def get_bid_number(self, r):
        clean_bid_number = lambda x: x.replace("#", "")
        if m := re.search(r"\d+\-\#?\d+(\-?\d+)?", r["text"], flags=re.I):
            return clean_bid_number(m.group())

    def fetch_rows(self):
        if self.status == "closed":
            return []
        by_bid_number = {
            k: {"bid_number": k, "files": v}
            for k, v in py_.group_by(
                self.list_tree(self.settings["index_url"]), self.get_bid_number
            ).items()
        }
        if None in by_bid_number:
            no_bid_number_files = by_bid_number.pop(None)["files"]

        for k, v in by_bid_number.items():
            if k:
                yield v

    bid_id_from_row = staticmethod(lambda data: get_hash(json.dumps(data)))

    due_pattern = re.compile(
        r"(?:(?:bid\s*)?closing\s*date\s*(?:and hour)?\:?\s*[|\-\u2014]?\s*|"
        r"bids will be received)" + long_re_date,
        flags=re.I,
    )

    exception_pattern = re.compile(
        r"no earlier than(?:.*?)?((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
        r"Sept?(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?) \d+)[sthrdn]+",
        flags=re.I | re.S,
    )

    def scrape_bid(self, bid, data):
        bid.bidNumber = data.get("bid_number") or bid.sourceID
        bid.sourceURL = bid.bidURL = py_.get(data, "files.0.index") + f"#{bid.bidNumber}"
        bid.title = py_(data).get("files.0.text").thru(lambda s: re.sub(r"\.pdf$", "", s)).value()
        bid.description = f"<p>{bid.title}</p>"
        dlpath = Path(self.directories["documents"]) / bid.sourceID
        downloads = self.download_files(
            py_(data["files"]).map(("text", "link")).map(tuple).value(), bid
        )
        for file in downloads:
            if file.path:
                dump = None
                sidecar_file = dlpath / f"{file.base}.sidecar.txt"
                ocrd_file = dlpath / f"{file.base}.ocr.pdf"
                try:
                    subprocess.run(
                        [
                          "ocrmypdf",
                          "--skip-text",  # Force OCR processing on the input file
                          "--sidecar",
                          sidecar_file,  # Extract OCR text to a separate file
                          "--quiet",  # Suppresses progress bar and other output (equivalent to progress_bar=False)
                          file.path,
                          ocrd_file,
                        ],
                        stderr=subprocess.DEVNULL,  # skips the error log
                        check=True,
                    )
                    dump = open(sidecar_file, "r").read()
                except Exception as exception:
                    logging.warning(
                        {
                            "message": "Unexcepted error dumping file to text!",
                            "ocrmypdf_exception": exception,
                            "filepath": file.path,
                            "fileurl": file.url,
                        }
                    )
                if py_.clean(dump):
                    if m := self.due_pattern.search(dump):
                        bid.dueDate = core.common.parse.parse_date(m.group(1))
                        break
                    else:
                        if m := self.exception_pattern.search(dump):
                            if year_m := re.search(r"FY(\d+)", py_.get(data, "files.0.index")):
                                bid.dueDate = core.common.parse.parse_date(
                                    m.group(1) + f" {year_m.group(1)}"
                                )
                                break

if __name__ == "__main__":
    Main().run()

