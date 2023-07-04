import pdb
import os
import rioxarray
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
from pathlib import Path
from src.dnbr import calculate_dnbr
from dask.distributed import Client


def main():
    """Run the whole enchilada."""
    # Set up the I/O
    path = "/mnt/sherlock/oak/mburke/prescribed_data"
    dir_save = "dnbr_landsat_c2_l2"
    path_save = os.path.join(path, "processed", dir_save)

    # Create saving dir if not exists
    if not os.path.exists(path_save):
        os.makedirs(path_save)

    mtbs = gpd.read_file(os.path.join(path, "geoms", "mtbs_perims_DD"))

    # Transform to datetime to make comparisons faster
    mtbs["Ig_Date"] = pd.to_datetime(mtbs["Ig_Date"])
    mtbs_ca = mtbs[(mtbs.Event_ID.str.contains("CA")) & (mtbs.Incid_Type == "Wildfire")]

    # List processed files to avoid repetition
    file_list = list(Path(path_save).rglob("*.tif"))
    file_list_events = [file.stem.split("_")[0] for file in file_list]

    for idx, event in tqdm(
        mtbs_ca.iterrows(),
        total=mtbs_ca.shape[0],
        desc="Processing dnbr for events in MTBS",
    ):
        print(f"Working on {event['Event_ID']}")

        if not event["Event_ID"] in file_list_events:
            path_to_file = os.path.join(
                path, "raw", "landsat-c2-l2", f"{event['Event_ID']}.nc4"
            )

            try:
                dnbr = calculate_dnbr(
                    array_data=path_to_file,
                    date_comparison=event["Ig_Date"],
                    bad_pixel_tresh=0.10,
                    optimal_distance=True,
                    apply_qa_bitmask=True,
                )

                # Set saving path using optimal distance dates
                list_dates = dnbr["date_combination"].to_series().str.split("/").iloc[0]
                str_dates = [d.replace("-", "") for d in list_dates]

                start_date, end_date = tuple(str_dates)

                file_name = f"{event['Event_ID']}_{start_date}_{end_date}.tif"
                save_path = os.path.join(path_save, file_name)

                # Save file COG using rioxarray
                dnbr.rio.to_raster(save_path, tiled=True, windowed=True)

            except OSError as e:
                print(f"File for {event['Event_ID']} not found!: {e}")
                pass

            except IndexError as e:
                print(f"{e}: {event['Event_ID']} it out of the collection date range")
                pass

            except ValueError as e:
                print("{e}: {event['Event_ID'] does not have data (?)}")
                pass

        else:
            print(f"{event['Event_ID']} is already processed!")


if __name__ == "__main__":
    client = Client()
    main()
    client.close()
