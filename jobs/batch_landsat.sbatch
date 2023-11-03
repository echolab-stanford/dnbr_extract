#!/usr/bin/bash
#SBATCH --job-name=ls_download
#SBATCH --output=ls_download.out
#SBATCH --error=ls_download.err
#SBATCH --time=05:00:00
#SBATCH -p serc
#SBATCH --nodes 1
#SBATCH --mem 8GB
#SBATCH -c 4
#SBATCH --mail-user=ihigueme@stanford.edu
#SBATCH --mail-type=ALL

module load physics gdal/3.5.2
module load python/3.9.0


source /home/groups/mburke/python_envs/prescribed/bin/activate
echo "Transforming data"

python landsat_download.py \
    --path_to_shape /oak/stanford/groups/mburke/prescribed_data/geoms/mtbs_perims_DD \
    --path_to_save /oak/stanford/groups/mburke/prescribed_data/raw/landsat-c2-l2-post-large-buf \
    --cloud_coverage 30 \
    --buffer 10000 \
    --post



