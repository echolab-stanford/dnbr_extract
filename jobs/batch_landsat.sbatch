#!/usr/bin/bash
#SBATCH --job-name=ls_download
#SBATCH --output=ls_download.out
#SBATCH --error=ls_download.err
#SBATCH --time=12:00:00
#SBATCH -p serc
#SBATCH --nodes 1
#SBATCH --mem 32GB
#SBATCH -c 8
#SBATCH --mail-user=ihigueme@stanford.edu
#SBATCH --mail-type=ALL

module load physics gdal/3.5.2
module load python/3.9.0

source /home/groups/mburke/python_envs/prescribed/bin/activate
echo "Transforming data"

python3 landsat_download.py



