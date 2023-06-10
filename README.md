# ESBE

This project contains the files and scripts that were used during the third ESBE Workshop in Lecco, Italy. 

The best entry point to understanding this project is looking at the `esbe_analysis.ipynb` which scaffolds out the URBANopt class files activity-by-activity.

## Installation Requirements

* URBANopt CLI 0.9.2
* OpenStudio's PAT
* OpenStudio Analysis Framework (either local or remote)
* Python >3.10
* Ruby (same version as in OpenStudio)


## Running

```
pip install poetry
poetry install

jupyter lab 
# or run in VSCode (which is recommended)