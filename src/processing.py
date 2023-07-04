from math import sqrt
import numbers
import os
from pathlib import Path
import pdb

import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import ImageGrid
import numpy as np
from tqdm import tqdm

import geopandas as gpd
import pandas as pd
import rasterio
import rasterio.mask
from rasterio.plot import show
import rioxarray as rxr
from sklearn.preprocessing import MaxAbsScaler

def get_dimensions(n):
    """Get optimal dimensions for grid if not prime

    Source:
    https://stackoverflow.com/questions/16907526/how-to-maximize-grid-dimensions-given-the-number-of-elements
    """
    tempSqrt = sqrt(n)
    divisors = []
    currentDiv = 1
    for currentDiv in range(n):
        if n % float(currentDiv + 1) == 0:
            divisors.append(currentDiv + 1)
    # print divisors this is to ensure that we're choosing well
    hIndex = min(range(len(divisors)), key=lambda i: abs(divisors[i] - sqrt(n)))

    if divisors[hIndex] * divisors[hIndex] == n:
        return divisors[hIndex], divisors[hIndex]
    else:
        wIndex = hIndex + 1
        return divisors[hIndex], divisors[wIndex]


def calculate_nbr(path, landsat_sat="LANDSAT_8"):
    """Calculate Normalized Burn Ratio from image

    Calculates the NBR for a set of images and filtering out bad candidates
    such as:
        - Images where nan are predominant values in the array
        - Landsat 7 images or just images with thermal/SWIR band collusion.
    The NBR calculation uses the two NIR and SWIR data. Sensibility to water bodies
    has to be addressed.

    Args:
        - path (str): Path to raster file
        - landsat_sat (str): Landsat product name. Default is `LANDSAT_8`
    Returns:
        np.array Array with NBR for input image
    """
    bands = [f"B{i}" for i in range(1, 8)]

    with rasterio.open(path) as src:
        data = src.read()

        # Calculate nans and return none if exceeds 50%
        values, counts = np.unique(np.isnan(data), return_counts=True)

        if len(counts.shape) > 1:
            nan_coverage = counts[1] / np.sum(counts)
        elif values == False:
            nan_coverage = 0
        elif values == True:
            nan_coverage = 1
        else:
            raise ValueError("Something is weird in here!")

        if nan_coverage < 0.5:

            # Take it to a list
            list_bands = np.split(data, data.shape[0], axis=0)
            bands_dict = {k: v.squeeze() for k, v in zip(bands, list_bands)}

            try:
                if landsat_sat == "LANDSAT_8":
                    nbr_pre = (bands_dict["B5"] - bands_dict["B7"]) / (
                        bands_dict["B5"] + bands_dict["B7"]
                    )
                elif landsat_sat in ["LANDSAT_5", "LANDSAT_4"]:
                    nbr_pre = (bands_dict["B4"] - bands_dict["B7"]) / (
                        bands_dict["B4"] + bands_dict["B7"]
                    )
            except:
                nbr_pre = None
                print(f"{landsat_sat} has incomplete bands. Skiping...")
                pass
        else:
            # Data quality is no good to calcualte NBR
            nbr_pre = None

    return (nbr_pre, src.transform)


def plot_nbr_timeline(fire_id, dataset, path_to_files):
    """Plot timeline of NBR for each fire"""

    subset_data = dataset[dataset["Event_ID"] == fire_id]
    paths_to_scenes = list(Path(path_to_files).rglob("*.tif"))

    # Clean bad scenes
    paths_to_scenes_clean = [
        p for p in paths_to_scenes if p.parts[-2] in subset_data.SCENE_ID.unique()
    ]

    # Create dict of events with paths
    dict_events = {fire_id: [p for p in paths_to_scenes_clean if fire_id in p.name]}

    # Apply NBR function
    list_arr = []
    for image in tqdm(dict_events[fire_id], desc="Apply NBR function to scene"):
        nbr_array = calculate_nbr(str(image))
        list_arr.append(nbr_array)

    # Read in data after removing empty files
    arr_clean = [
        (p, arr)
        for arr, p in zip(list_arr, dict_events[fire_id])
        if (arr is not None) and (np.nanmean(arr) != np.nan)
    ]
    arr_clean.sort(key=lambda x: x[0].name)

    # Plot all dates using a grid
    dims = get_dimensions(len(arr_clean))

    plt.style.use("dark_background")
    fig = plt.figure(figsize=(20, 80))
    grid = ImageGrid(
        fig,
        111,
        nrows_ncols=dims,
        axes_pad=0.5,
        label_mode="L",
    )

    for idx, ax in enumerate(grid):
        ax.imshow(arr_clean[idx][1])
        ax.set_title("-".join(arr_clean[idx][0].parts[-1].split("_")[1:4]))
    plt.show()

    return (dict_events, arr_clean)


def process_nbr(aoi_df, path_to_files, save_path, aoi_id="Event_ID"):
    """Process and save NBR data

    This function will take a dataframe and will process each of the files and save
    the output as a GeoTIFF. During this process it will read all the files and remove
    all possible scenes where we had noise or only `np.nan` values during calculation.

    Once the array is ready, it will be saved using the same file structure.

    Args:
    -----
        - aoi_df (gpd.DataFrame or pd.DataFrame): Dataset with the AOIs to be processed
          the data for this AOI should be in the `path_to_files` directory.
        - path_to_files (str): A path to all Landsat scenes.
        - aoi_id (str): AOI identifier column in the dataset
        - save_path (str): A path to save the output data

    Returns:
        Saves to the file system. Function returs None
    """

    # Apply NBR function
    grouped_df = aoi_df.groupby(aoi_id)

    for group_id, df in tqdm(
        grouped_df, total=aoi_df[aoi_id].unique().shape[0], desc="Apply NBR to each AOI"
    ):
        for idx, row in df.iterrows():

            try:
                # Build path to raw landsat file
                date_format = row["DATE_ACQUIRED"].strftime("%Y_%m_%d")
                filename = f"{row[aoi_id]}_{date_format}.tif"
                path_file = os.path.join(path_to_files, row["SCENE_ID"], filename)

                nbr_array, affine = calculate_nbr(
                    path_file, landsat_sat=row["SPACECRAFT_ID"]
                )

                if (nbr_array is not None) and (np.nanmean(nbr_array) != np.nan):
                    h, w = nbr_array.shape
                    with rasterio.open(
                        os.path.join(save_path, filename),
                        "w",
                        driver="GTiff",
                        height=h,
                        width=w,
                        count=1,
                        dtype=nbr_array.dtype,
                        crs="EPSG:4326",
                        transform=affine,
                    ) as dst:
                        dst.write(nbr_array, 1)
                else:
                    print(f"All nans file: {row[aoi_id]}")
            except Exception as e:
                print(f"Something very wrong: {e}")
                pass

    return None


def extract_data(path):
    """ Extract data fast on different scenes using coordinates
    """

    with rasterio.open(path) as src:
        data_array = src.read(1)

        mean_data = np.nanmean(data_array)

        if not np.isnan(mean_data):

            # Clean arrays with bad divisions
            data_array[data_array == np.inf] = np.nan
            data_array[data_array == -np.inf] = np.nan

            # Scale data to -1 to 1
            scaler = MaxAbsScaler().fit(data_array)
            data_array_nona = scaler.transform(data_array)

            # Extract coordinate data using trasnform
            height = data_array_nona.shape[0]
            width = data_array_nona.shape[1]

            cols, rows = np.meshgrid(np.arange(width), np.arange(height))
            xs, ys = rasterio.transform.xy(src.transform, rows, cols)

            lons= np.array(xs)
            lats = np.array(ys)

            # Subset all coordinates without data and create tuples
            # for coordinates
            array_coords =  np.vstack(([lats.T], [lons.T])).T

            # Subset only coordinates with data
            data_coords = array_coords[~np.isnan(data_array_nona)]
            no_miss_data = data_array_nona[~np.isnan(data_array_nona)]

            # Save as dataframe
            test_df = pd.DataFrame(
                {
                    'lat': data_coords[:,0],
                    'lon': data_coords[:,1],
                    'data': no_miss_data
                }
            )

        return test_df
