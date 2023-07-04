import os
import geopandas as gpd

from src.landsat_get import Landsat

if __name__ == "__main__":
    # Load geometry and subset to wildfires only
    path_to_geom = "/oak/stanford/schools/ees/mburke/prescribed_data/data/mtbs_perims_DD/mtbs_perims_DD.shp"
    mtbs = gpd.read_file(path_to_geom)
    wildfires = mtbs[mtbs.Incid_Type == "Wildfire"]

    print("Start class and start extraction")
    # Start class and start retrieving files to path
    ls = Landsat(
        aoi_path=wildfires,
        cloud_coverage=50,
        save_path="/scratch/users/ihigueme",
        date_window=(90, 90),
    )

    print("Save AOI/Landsat overlap as GeoJSON")
    ls.filter_aoi_data.to_file(f"{ls.save_path}/aoi_filtered_data.geojson")

    print("Start downloading process -- tqdm.tqdm should start soon")
    ls.apply_processing_rasters()
