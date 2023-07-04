import os
import tarfile
import warnings
import zipfile
from io import BytesIO

import pandas as pd
import requests
from tqdm import tqdm


class BAERData:
    """Download and proceess BAER data (Intensity Fire)

    This class reads and process fire intesnity raster data from the BAER
    database. This class first retrieves all image metadata and process
    all files following a pattern and save the results in disk with the
    metadata. The class has options for data processing of raster data.
    These options include data extraction and data consolidation.

    Args:
    -----
        - save_data_path (str): Path to save data in disk.
        - pattern (str): a simple regex pattern to filter data inside BAER
        zipfiles.

    Methods:
    --------
        - unzip_filter
        - metadata_request
        - parse_payload
        - make_zip_request
        - process_raster
    """

    def __init__(self, save_data_path, years, pattern) -> None:

        self.save_data_path: str = save_data_path
        self.pattern: str = pattern

        # Take case when year is singleton
        if isinstance(years, int):
            self.years : list = list(years)
        else:
            self.years: list = years

        self.base_url: str = "https://burnseverity.cr.usgs.gov/baer/api/form/baer-downloads"
        self.headers: dict = {"accept": "*/*", "accept-encoding": "gzip;deflate"}

    def unzip_filter(self, response, pattern=None) -> None:
        """Unzip file, but be selective ;)

        Parse zip-request-payload in memory as a io.Bytes object, Unzip in
        memory and save only the files we care about. The parser can take zip
        or tar files.

        Args
        ----
            - reponse (request.models.Response) response object
            - pattern (str): Pattern to capture files within zipfile

        Returns
        -------
            Byte-stream object to save to disk
        """

        content: BytesIO = BytesIO(response.content)

        if response.url.endswith(".zip"):
            try:
                zip_req: zipfile.ZipFile = zipfile.ZipFile(content)
                if pattern is not None:
                    filter_files: list = [f for f in zip_req.namelist() if pattern in f]
                    zip_req.extractall(filter_files, self.save_data_path)
                else:
                    zip_req.extractall(self.save_data_path)
                zip_req.close()

            except zipfile.BadZipFile:
                print(f"Something wrong with {response.url}")
                pass

        elif response.url.__contains__(".tar"):

            # Capture tar/tar.gz mode
            if response.url.endswith("*.gz"):
                enc: str = "r|gz"
            else:
                enc: str = "r"

            try:
                tar: tarfile.TarFile = tarfile.open(fileobj=content, mode=enc)

                if pattern is not None:
                    filter_files: list = [
                        f for f in tar.getnames() if os.path.splitext(f)[1] == pattern
                    ]
                    tar.extractall(members=filter_files, path=self.save_data_path)
                else:
                    tar.extractall(path=self.save_data_path)
                tar.close()

            except tarfile.ReadError:
                print(f"Oops! Something wrong with {response.url}")
                pass

        else:
            warnings.warn(f"Cannot parse/open {response.url}")

        return None

    @property
    def metadata_request(self) -> pd.DataFrame:
        """Make request to metata for a specific list of years

        Execute request to get a table like the one in:
        https://burnseverity.cr.usgs.gov/baer/baer-imagery-support-data-download
        For an specific year. The request will bring all the regions available
        in the BAER dataset and use the class parser to extract the relevant
        metadata

        Args
        ----
            - years (list, int): years to retrieve

        Returns
        -------
            pd.DataFrame with fire metadata
        """

        with requests.Session() as s:
            meta_list: list = []
            for year in self.years:
                params: dict = {"year": year}
                response: requests.Response = s.get(self.base_url, params=params)

                if response.status_code == requests.codes.all_good:
                    response_payload: dict = response.json()
                    df: pd.DataFrame = self.parse_payload(response_payload)
                    meta_list.append(df)
                else:
                    raise RuntimeError(f"Request failed for year: {year}")

                meta_df: pd.DataFrame = pd.concat(meta_list)

        return meta_df

    def parse_payload(self, json_string) -> pd.DataFrame:
        """Parse payload data from the request

        This function takes a dict object comming from the request GET
        formatted as a dictonary. The function filters the metadata and stores
        all the relevant links for processing in other steps.

        Args
        ----
            - json_string (dict): A GET payload from the request

        Returns
        -------
            pd.DataFrame with metadata and links
        """

        # Take all the items from the request
        data_list_items = json_string["data"]["items"]

        region_items = []
        for region in tqdm(data_list_items, desc=f"BAER - Getting metadata [{self.years}]"):
            region_df = pd.DataFrame(region["items"])
            region_items.append(region_df)

        all_items = pd.concat(region_items)

        return all_items

    def make_zip_requests(self) -> None:
        """Download zipped files

        Use class metadata to access to preliminary datasets. This function
        will take the metadata property and get all the relevant files for
        analysis
        """

        df = self.metadata_request

        # We care mainly here about the preliminary data since we want to have
        # access to raw DNBR imagery used to create the final classification
        # fire intensity product.

        with requests.Session() as session_:
            for prelim_zip in tqdm(
                df.preliminary_file_url.tolist(), desc="BAER - Downloading zip data"
            ):
                try:
                    response = session_.get(prelim_zip, headers=self.headers)
                    self.unzip_filter(response)
                except Exception as e:
                    # Grabbing cases where download link is not available
                    print(f"Oops! Problems with {prelim_zip}: {e}")

        return None
