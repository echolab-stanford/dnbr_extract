""" Download BAER data to disk
"""

from src.baer import BAERData

if __name__ == "__main__":

    for year in range(2006, 2022):
        baer = BAERData(save_data_path=f'data/baer_data/{year}',
                        years=[year],
                        pattern=".tif"
                        )
        baer.make_zip_requests()
