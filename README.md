# Calculate burning/fire metrics from Landsat 2 Collection

This repo will help you get the  [Differenced Normalized Burn Ratio][1]
($\Delta NBR$) for a set of fires. The pipeline includes storing Landsat Level-2
collection data in NetCDF format and using different methods to calculate the
fire severity indexes from these data. 

We rely on the [Planetary computer][2] to get imagery. The PC allow us to 
lazy download STAC elements and snap them on-the-fly to avoid storing complete
Landsat scenes, but only the boundary of the selected geometries. 

We offer two main scripts. The first one to get data: `landsat_download.py`

```{bash}
usage: landsat_download.py [-h] [--path_to_shape PATH_TO_SHAPE] [--path_to_save PATH_TO_SAVE] [--cloud_coverage CLOUD_COVERAGE] [--buffer BUFFER] [--post | --no-post]

options:
  -h, --help            show this help message and exit
  --path_to_shape PATH_TO_SHAPE
                        Path to extration shape
  --path_to_save PATH_TO_SAVE
                        Path to save data
  --cloud_coverage CLOUD_COVERAGE
                        Cloud coverage treshold
  --buffer BUFFER       Geometry buffer to calculate offsets. Default is 180 meters
  --post, --no-post     Get post-fire data
```

and a second to process it: `calculate_dnbr.py`

```{bash}
usage: calculate_dnbr.py [-h] [--path_to_pre PATH_TO_PRE] [--path_to_post PATH_TO_POST] [--path_to_geom PATH_TO_GEOM] [--path_to_save PATH_TO_SAVE] [--buffer BUFFER] [--offset | --no-offset]

options:
  -h, --help            show this help message and exit
  --path_to_pre PATH_TO_PRE
                        Path to pre-event images
  --path_to_post PATH_TO_POST
                        Path to post-event images
  --path_to_geom PATH_TO_GEOM
                        Path to shapefile with events
  --path_to_save PATH_TO_SAVE
                        Path to save dNBR rasters
  --buffer BUFFER       Buffer size in meters for offset. Default is 180m
  --offset, --no-offset
                        Calculate dNBR with offset
```

The defaults on these functions will follow the [Parks, et.al. (2018)][3] $\Delta NBR$ calculation. 



### Notes

Some of the paralelization is implemented via [Dask](https://www.dask.org/). You will need
a `dask.distributed.Client` to execute this in parallel. This plays nice with Sherlock whithin
one node, for real HPC use in Sherlock, you can use the SLURM API [here](https://jobqueue.dask.org/en/latest/generated/dask_jobqueue.SLURMCluster.html)

## To-do 
 - [ ] Better docs
 - [ ] Maybe some basic unit testing
 - [ ] More general options to work with non-MTBS datasets
 - [ ] Actually to the `setup.py` to install this as a package


 [1]: https://un-spider.org/advisory-support/recommended-practices/recommended-practice-burn-severity/in-detail/normalized-burn-ratio
 [2]: https://planetarycomputer.microsoft.com/
 [3]: https://www.mdpi.com/2072-4292/10/6/879
