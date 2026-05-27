# ESBE

This project contains the files and scripts that were used during the third ESBE Workshop in Lecco, Italy.

The best entry point to understanding this project is looking at the `0*_esbe_analysis.ipynb` which scaffolds out the URBANopt class files activity-by-activity.

## Installation Requirements

* URBANopt CLI 1.2.0
* OpenStudio's PAT
* OpenStudio Analysis Framework (either local or remote)
* Python >3.11
* Ruby (same version as in OpenStudio), 3.2.2



## Running

```
pip install poetry
poetry install

jupyter lab
# or run in VSCode (recommended)
```

### Notebook Output Location

Most notebooks call `setup_notebook_paths(...)` near the top. By default in this repo,
the setup cell uses:

```python
MODEL_OUTPUT_SUBDIR = "../test_activities/esbe_2026"
paths = setup_notebook_paths(analysis_subdir=MODEL_OUTPUT_SUBDIR)
```

This stores generated model/results folders one directory level above `esbe/`.
You can still change it per notebook, for example:

- `"esbe_2026"` to keep outputs inside `esbe/`
- `"../my_models"` for a sibling folder
- `"/absolute/path/to/models"` for a fixed location
