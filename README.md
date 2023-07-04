# Calculate burning/fire metrics from Landsat 2 Collection

This repo contains scripts to extract different fire metrics from Landsat imagery. 
The code relies on the [Planetary computer](https://planetarycomputer.microsoft.com/)
and needs a valid API key to work properly.

### Notes

Some of the paralelization is implemented via [Dask](https://www.dask.org/). You will need
a `dask.distributed.Client` to execute this in parallel. This plays nice with Sherlock whithin
one node, for real HPC use in Sherlock, you can use the SLURM API [here](https://jobqueue.dask.org/en/latest/generated/dask_jobqueue.SLURMCluster.html)

## To-do 
 - [ ] Better docs
 - [ ] Maybe some basic unit testing
 - [ ] More general options to work with different datasets
