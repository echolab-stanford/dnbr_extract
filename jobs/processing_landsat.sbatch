#!/usr/bin/bash
#SBATCH --job-name=ls_dnbr_process
#SBATCH --output=processed_landsat.out
#SBATCH --error=processed_landsat.err
#SBATCH --time=2:00:00
#SBATCH -p serc
#SBATCH --nodes 1
#SBATCH --mem 10GB
#SBATCH -c 12
#SBATCH --mail-user=ihigueme@stanford.edu
#SBATCH --mail-type=ALL


CONTAINER_PATH=${GROUP_HOME}/singularity_images/pangeo-notebook_latest.sif

echo "Transform data in container!"

singularity run ${CONTAINER_PATH} python calculate_dnbr.py \
    --path_to_pre ${OAK}/prescribed_data/raw/landsat-c2-l2-pre-buf \
    --path_to_post ${OAK}/prescribed_data/raw/landsat-c2-l2-post-buf \
    --path_to_geom ${OAK}/prescribed_data/geoms/mtbs_perims_DD \
    --path_to_save ${OAK}/prescribed_data/processed/dnbr_landsat_c2_l2_large_buf \
    --buffer 180 \
    --offset
