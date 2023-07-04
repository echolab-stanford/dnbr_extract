#!/usr/bin/bash
#SBATCH --job-name=ls_dnbr_process
#SBATCH --output=processed_landsat.out
#SBATCH --error=processed_landsat.err
#SBATCH --time=2:00:00
#SBATCH -p serc
#SBATCH --nodes 1
#SBATCH --mem 32GB
#SBATCH -c 12
#SBATCH --mail-user=ihigueme@stanford.edu
#SBATCH --mail-type=ALL

mamba activate fire
python calculate_dnbr.py


