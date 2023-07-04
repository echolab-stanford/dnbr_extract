"""
Generate pystac collection from a geoparquet 
"""

import numpy as np
import pystac
import geopandas
import pandas as pd
from shapely import wkb, geometry
from typing import Dict, Any


def intersection_percent(item: pystac.Item, aoi: Dict[str, Any]) -> float:
    """The percentage that the Item's geometry intersects the AOI. An Item that
    completely covers the AOI has a value of 100.
    """
    geom_item = geometry.shape(item.geometry)
    geom_aoi = geometry.shape(aoi)

    intersected_geom = geom_aoi.intersection(geom_item)

    intersection_percent = (intersected_geom.area * 100) / geom_aoi.area

    return intersection_percent
