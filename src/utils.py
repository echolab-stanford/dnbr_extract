import os
from math import sqrt
from typing import Any, Dict

import geopandas
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio import features
import pyproj
import pystac
from tqdm import tqdm
from shapely import geometry, wkb
from shapely.geometry import Point
from shapely.ops import transform
from datetime import datetime, date, timedelta


def num_day_to_datetime(day_num, year) -> datetime:
    """Transformd from day of the year to datetime object

    Take a day number and return it as a datetime object for an specific year

    Args:
        - day_num (int): An integer representing the day of the year
        - year (int): year for date

    Returns:
        datetime
    """

    start_date = date(year, 1, 1)

    resolved_time = start_date + timedelta(days=int(day_num) - 1)

    return resolved_time


def buffer_bounding_box(bounds, buf=10000) -> tuple:
    """Create a buffer around a bounding box object

    Taking the coordinates of a polygon boundary, this function calculates a
    buffer in meters and return it in the same CRS that the input boundaries.

    Args:
        - bounds (tuple): A bounds coordinates object. In a geometry you can
          use: geometry.bounds
        - buf (int): buffer size in meters
    """

    buffer_width_m = (distance_km * 1000) / sqrt(2)
    (p_lat, p_long) = point_lat_long

    # create Shapely Point object, coodrinates as x,y
    wgs84_pt = Point(p_long, p_lat)
    # set up projections WGS84 (lat/long coordinates) for input and
    # UTM to measure distance
    # https://epsg.io/4326
    wgs84 = pyproj.CRS("EPSG:4326")
    # sample point in France - UTM zone 31N
    # Between 0°E and 6°E, northern hemisphere between equator and 84°N
    # https://epsg.io/32631
    utm = pyproj.CRS("EPSG:32631")

    # transformers:
    project_wgs84_to_utm = pyproj.Transformer.from_crs(
        wgs84, utm, always_xy=True
    ).transform
    project_utm_to_wgs84 = pyproj.Transformer.from_crs(
        utm, wgs84, always_xy=True
    ).transform

    # tranform Point to UTM
    utm_pt = transform(project_wgs84_to_utm, wgs84_pt)
    # create square buffer (cap_style = 3) around the Point
    utm_buffer = utm_pt.buffer(buffer_width_m, cap_style=3)

    return wgs84_bounds


def intersection_percent(item: pystac.Item, aoi: Dict[str, Any]) -> float:
    """The percentage that the Item's geometry intersects the AOI. An Item that
    completely covers the AOI has a value of 100.
    """
    geom_item = geometry.shape(item.geometry)
    geom_aoi = geometry.shape(aoi)

    intersected_geom = geom_aoi.intersection(geom_item)

    intersection_percent = (intersected_geom.area * 100) / geom_aoi.area

    return intersection_percent

def create_fire_rasters(shape,
                        id,
                        date_var,
                        template_path,
                        save_path_dir="./",
                        cummulative=False,
                        out_file_stem="shape_rasterization"
                       ):
    """ Create rasterized versions of a shape cumulative (or not) by year

    This function rasterizes a shapefile using rasterio's features.rasterize 
    function. The shapefile is divided by date (year by default) and a raster
    is created per each year, but including all the other shapes for years
    less or equal to the present year. The output will be saved a GeoTIFF 
    with LZW compression and with an integer as a dtype to save some space.

    Args:
        - shape (gpd.GeoDataFrame): A data frame with geometric data with dates
        - id (str): A string variable that identifies each geometry
        - date_var (str): a string with the name of the data column in the dataset
        - template_path (str): template for rasterization
        - cummulative (bool): Should we include all the shapes up to that 
        date (i.e. cummulative)
        - save_path_dir (str): Path for saving files
        - out_file_stem (str): seed for name files

    Returns:
    --------
        Saves fies to save_path_dir. Function returns None
    """

    # Check projection in meters, otherwise transform
    if shape.crs != 3857:
        shape = shape.to_crs("EPSG:3857")

    # For each year get all the shapes with a date less or equal to
    # year.
    yearly_cum_shapes = []
    for year in tqdm(shape[date_var].dt.year.unique(), 
                     desc="Year "):

        if cummulative:
            shape_year = shape[shape[date_var].dt.year <= year]
        else:
            shape_year = shape[shape[date_var].dt.year == year]

        # Densify the segments to have a point every meter
        boundaries = shape_year.boundary.segmentize(1)
        data_to_burn = shape_year[id].astype(float).to_list()
        # Create raster using template
        with rasterio.open(template_path) as src:
            meta = src.meta.copy()
            meta.update({"compress": "lzw", "dtype": np.float64})

            save_path = os.path.join(save_path_dir, f"{out_file_stem}_{year}.tif")
            
            with rasterio.open(save_path, 'w+', **meta) as out:
                out_arr = out.read(1)
            
                # this is where we create a generator of geom, value pairs to use in rasterizing
                shapes = ((geom,value) for geom, value in zip(boundaries, data_to_burn))
                #shapes = ((geom) for geom in boundaries)
            
                burned = features.rasterize(shapes=shapes,
                                            fill=0,
                                            out=out_arr,
                                            default_value=1,
                                            all_touched=True,
                                            transform=out.transform)
                out.write_band(1, burned)

    return None
