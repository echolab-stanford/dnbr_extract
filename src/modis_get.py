import os
import tqdm
import urllib
import requests
import datetime
import pandas as pd

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.exceptions import HTTPError
from tenacity import retry, wait_fixed, wait_random, stop_after_attempt


class GetMODIS:
    def __init__(self, iso, product, save_dir):
        self.iso = iso
        self.save_dir = save_dir

        if product == "both":
            self.product = ",".join(["MOD04_L2", "MYD04_L2"])
        elif product == "terra":
            self.product = "MOD04_L2"
        elif product == "aqua":
            self.product = "MYD04_L2"

        self.session = requests.Session()

    @property
    def tile_map(self):
        """
        Using Sinusoidal tiles: https://modis-land.gsfc.nasa.gov/MODLAND_grid.html
        For every new country, follow US template of tile coverage based on image
        """
        tile_map = {"us": {"v": [4, 5, 6], "h": [8, 9, 10, 11, 12]}}
        return tile_map

    @property
    def headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36"
        }

    @retry(wait=wait_fixed(5) + wait_random(0, 5), stop=stop_after_attempt(10))
    def base_request(self, url, headers):
        r = self.session.get(url, headers=headers)
        if r.status_code == requests.codes.ok:
            return r
        else:
            raise HTTPError

    def base_url_creation(self, endpoint, params):
        base_url = f"http://modwebsrv.modaps.eosdis.nasa.gov/axis2/services/MODAPSservices/{endpoint}/?"
        request_url = base_url + urllib.parse.urlencode(params).replace("%2C", ",")
        params.update({"url": request_url})

    def base_response_parsing(self, r):
        soup = BeautifulSoup(r.content)
        results = [link.contents[0] for link in soup.findAll("return")]
        return results

    def create_image_search_urls(self, start_date, end_date):
        tiles = self.tile_map[self.iso]
        tile_pairs = [(v, h) for v in tiles["v"] for h in tiles["h"]]

        time_range = pd.date_range(
            start_date.replace(month=1, day=1), end_date, freq="YS"
        )
        if len(time_range) == 1:
            time_range = [(start_date, end_date)]
        else:
            time_range = list(time_range)
            time_range[0] = start_date
            time_range[-1] = end_date
            time_range = [
                (time_range[i], time_range[i + 1]) for i in range(len(time_range) - 1)
            ]

        self.search_urls = []
        for time_tup in time_range:
            for tile_tup in tile_pairs:
                tile_v = tile_tup[0]
                tile_h = tile_tup[1]

                # chunk dates into years
                param_start_date = time_tup[0]
                if end_date != time_tup[1]:
                    param_end_date = time_tup[1] - datetime.timedelta(days=1)
                else:
                    param_end_date = end_date

                params = {
                    "start": param_start_date.strftime("%Y-%m-%d"),
                    "stop": param_end_date.strftime("%Y-%m-%d"),
                    "product": self.product,
                    "north": tile_v,
                    "south": tile_v - 1,
                    "west": tile_h + 1,
                    "east": tile_h,
                    "coordsOrTiles": "tiles",
                    "dayNightBoth": "DNB",
                }
                self.base_url_creation(endpoint="searchForFiles", params=params)
                self.search_urls.append(params)

    def get_image_ids_for_urls(self):
        self.api_df = []
        for request_dict in tqdm.tqdm(
            self.search_urls,
            desc=f"MODIS - {self.iso} - {self.product} - get_image_ids_for_urls",
        ):
            url = request_dict["url"]
            params = {k: v for k, v in request_dict.items() if k != "url"}

            r = self.base_request(url, self.headers)
            results = self.base_response_parsing(r)
            if len(results) == 6000:
                print(
                    f"Request exceeded search limit for date and space. Info: {start_date} - {index}"
                )
            else:
                params.update(
                    {
                        "url": url,
                        "image_search_id": results,
                    }
                )
                self.api_df.append(pd.DataFrame(params))

        self.api_df = pd.concat(self.api_df)

    def create_image_orders(self):
        image_ids = list(set(self.api_df.image_search_id.values))
        chunk_size = 500
        chunk_ids = [
            image_ids[i : i + chunk_size] for i in range(0, len(image_ids), chunk_size)
        ]

        self.order_urls = []
        for chunk_image_ids in chunk_ids:
            params = {
                "email": os.environ["MODIS_EMAIL"],
                "fileIds": ",".join(chunk_image_ids),
                "subsetDataLayer": f"{self.product}___AOD_550_Dark_Target_Deep_Blue_Combined",
                #                 'reprojectionName': 'ALBERS',
                "reformatType": "geotiff",
            }
            self.base_url_creation(endpoint="orderFiles", params=params)
            self.order_urls.append(params)

    def send_image_orders(self):
        self.order_dict = {}
        for request_dict in tqdm.tqdm(
            self.order_urls,
            desc=f"MODIS - {self.iso} - {self.product} - send_image_orders",
        ):
            url = request_dict["url"]
            params = {k: v for k, v in request_dict.items() if k != "url"}

            r = self.base_request(url, self.headers)
            results = self.base_response_parsing(r)
            results = results[0] if len(results) == 1 else results
            for image_id in params["fileIds"].split(","):
                self.order_dict[image_id] = {
                    "order_id": results,
                    "date_requested": datetime.datetime.now(),
                }

        self.api_df["order_id"] = self.api_df["image_search_id"].map(
            lambda x: self.order_dict[x]["order_id"]
        )
        self.api_df["date_requested"] = self.api_df["image_search_id"].map(
            lambda x: self.order_dict[x]["date_requested"]
        )

    @retry(
        wait=wait_fixed(60 * 5) + wait_random(0, 60 * 5), stop=stop_after_attempt(10)
    )
    def get_order_status(self):

        # send each order id individually in order to get status
        order_status = {str(idx): "" for idx in list(self.api_df["order_id"].unique())}
        for order_id in order_status.keys():
            params = {"orderId": order_id}
            self.base_url_creation(endpoint="getOrderStatus", params=params)

            r = self.base_request(params["url"], self.headers)
            results = self.base_response_parsing(r)

            for i, idx in enumerate(params["orderId"].split(",")):
                order_status[idx] = results[i]

        # check that all order statuses are available before continuing code
        self.api_df["order_status"] = self.api_df["order_id"].replace(order_status)

        if self.api_df["order_status"].unique() != "Available":
            raise Exception("Not all orders have been completed")

    def create_order_urls(self):
        order_ids = [str(idx) for idx in list(self.api_df["order_id"].unique())]

        self.download_urls = []
        for order_id in order_ids:
            params = {
                "orderId": order_id,
            }
            self.base_url_creation(endpoint="getOrderUrl", params=params)
            self.download_urls.append(params)

    def get_order_urls(self):
        self.completed_order_urls = {}
        for request_dict in tqdm.tqdm(
            self.download_urls,
            desc=f"MODIS - {self.iso} - {self.product} - get_order_urls",
        ):
            url = request_dict["url"]
            params = {k: v for k, v in request_dict.items() if k != "url"}

            r = self.base_request(url, self.headers)
            results = self.base_response_parsing(r)
            results = results[0] if len(results) == 1 else results
            for order_id in params["orderId"].split(","):
                self.completed_order_urls[order_id] = {"url": results}

        self.api_df["download_url"] = self.api_df["order_id"].map(
            lambda x: self.completed_order_urls[x]["url"]
        )

    def get_image_urls(self):
        download_links = self.api_df["download_url"].unique()

        headers = {"Authorization": f"Bearer {os.environ['MODIS_TOKEN']}"}

        self.file_links = {}
        for link in tqdm.tqdm(
            download_links, desc=f"MODIS - {self.iso} - {self.product} - get_image_urls"
        ):
            order_id = link.split("/")[-2]
            r = self.base_request(link[:-1] + ".json", headers=headers)
            base_url = (
                f"https://ladsweb.modaps.eosdis.nasa.gov/archive/orders/{order_id}/"
            )
            self.file_links[order_id] = [
                base_url + d["name"] for d in r.json() if ".tif" in d["name"]
            ]

    def get_image_data(self):

        headers = {"Authorization": f"Bearer {os.environ['MODIS_TOKEN']}"}
        headers.update(self.headers)

        image_links = [
            item for sublist in list(self.file_links.values()) for item in sublist
        ]
        for link in tqdm.tqdm(
            image_links, desc=f"MODIS - {self.iso} - {self.product} - get_image_data"
        ):
            r = self.base_request(link, headers=headers)

            file_name = r.url.split("/")[-1]
            with open(os.path.join(self.save_dir, file_name), mode="wb") as file:
                file.write(r.content)

    def delete_all_orders(self):

        # get all orders for user
        params = {"email": os.environ["MODIS_EMAIL"]}
        self.base_url_creation(endpoint="getAllOrders", params=params)
        order_resp = self.base_request(params["url"], headers=self.headers)
        order_ids = self.base_response_parsing(order_resp)

        # release all orders
        self.release_codes = {}
        for oid in tqdm.tqdm(
            order_ids,
            desc=f"MODIS - {self.iso} - {self.product}  delete_orders",
            total=len(order_ids),
        ):
            params = {"orderId": oid, "email": os.environ["MODIS_EMAIL"]}
            self.base_url_creation(endpoint="releaseOrder", params=params)
            release_resp = self.base_request(params["url"], headers=self.headers)
            release_code = self.base_response_parsing(release_resp)
            self.release_codes[oid] = release_code[0]

    def download_modis_data(self, start_date, end_date):

        # find the unique ids for the time and geography needed
        self.create_image_search_urls(start_date, end_date)
        self.get_image_ids_for_urls()

        # submit orders for those unique ids for LAADS server to create files
        self.create_image_orders()
        self.send_image_orders()
        self.get_order_status()

        # get the individual image links to download the data from the orders submitted
        self.create_order_urls()
        self.get_order_urls()
        self.get_image_urls()
        self.get_image_data()


if __name__ == "__main__":
    load_dotenv()

    m = GetMODIS(
        iso="us", product="terra", save_dir="/scratch/midway2/daisylu/data/modis/raw"
    )
    y = 2000
    m.download_modis_data(datetime.datetime(y, 1, 1), datetime.datetime(y, 12, 31))
