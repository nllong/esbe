# ESBE

This project contains the files and scripts that were used during the third ESBE Workshop in Lecco, Italy.

The best entry point to understanding this project is looking at the `esbe_analysis.ipynb` which scaffolds out the URBANopt class files activity-by-activity.

## Installation Requirements

* URBANopt CLI 1.2.0
* OpenStudio's PAT
* OpenStudio Analysis Framework (either local or remote)
* Python >3.11
* Ruby (same version as in OpenStudio), 3.2.2


## Issues

```
file /Applications/URBANoptCLI_1.1.0/Ruby/bin/ruby
file /Applications/URBANoptCLI_1.1.0/ruby/bin/ruby
file /Applications/URBANoptCLI_1.1.0/OpenStudio/Ruby/openstudio.bundle

file /Applications/URBANoptCLI_1.2.0/Ruby/bin/ruby
file /Applications/URBANoptCLI_1.2.0/ruby/bin/ruby
file /Applications/URBANoptCLI_1.2.0/OpenStudio/Ruby/openstudio.bundle
```


Looks like it is installing x86_64
```
/Applications/URBANoptCLI_1.1.0/Ruby/bin/ruby: Mach-O 64-bit executable x86_64
/Applications/URBANoptCLI_1.1.0/ruby/bin/ruby: Mach-O 64-bit executable x86_64
/Applications/URBANoptCLI_1.1.0/OpenStudio/Ruby/openstudio.bundle: Mach-O 64-bit bundle x86_64

/Applications/URBANoptCLI_1.2.0/Ruby/bin/ruby: Mach-O 64-bit executable arm64
/Applications/URBANoptCLI_1.2.0/ruby/bin/ruby: Mach-O 64-bit executable arm64
/Applications/URBANoptCLI_1.2.0/OpenStudio/Ruby/openstudio.bundle: Mach-O 64-bit bundle x86_64
```

Need to fix `base_workflow.osw` to
1. Remove story_multiplier

```
"measure_dir_name": "create_bar_from_building_type_ratios",
      "arguments": {
        "__SKIP__": true,
        "bldg_type_a": null,
        "bldg_type_a_num_units": 0,
        "bldg_type_b": "SmallOffice",
        "bldg_type_b_fract_bldg_area": 0,
        "bldg_type_b_num_units": 0,
        "bldg_type_c": "SmallOffice",
        "bldg_type_c_fract_bldg_area": 0,
        "bldg_type_c_num_units": 0,
        "bldg_type_d": "SmallOffice",
        "bldg_type_d_fract_bldg_area": 0,
        "bldg_type_d_num_units": 0,
        "single_floor_area": null,
        "floor_height": 0,
        "num_stories_above_grade": null,
        "num_stories_below_grade": null,
        "building_rotation": 0,
        "template": "90.1-2004",
        "ns_to_ew_ratio": 0,
        "wwr": 0,
        "party_wall_fraction": 0,
        "story_multiplier": "None",
        ^---
 ```

2. Replace this measure
{
      "measure_dir_name": "generic_qaqc",
      "arguments": {
        "template": "90.1-2004",
        "eui_reasonableness": true,
        "end_use_by_category": true,
        "mechanical_system_part_load_efficiency": true,
        "simultaneous_heating_and_cooling": true,
        "internal_loads": true,
        "schedules": true,
        "envelope_r_value": true,
        "mechanical_system_efficiency": true,
        "check_mech_sys_type": false,
        "supply_and_zone_air_temperature": true,
        "__SKIP__": true
      }
    }

## Running

```
pip install poetry
poetry install

jupyter lab
# or run in VSCode (which is recommended)

### Notebook Output Location

Most notebooks call `setup_notebook_paths(...)` near the top. By default in this repo,
the setup cell uses:

```python
MODEL_OUTPUT_SUBDIR = "../esbe_2026"
paths = setup_notebook_paths(analysis_subdir=MODEL_OUTPUT_SUBDIR)
```

This stores generated model/results folders one directory level above `esbe/`.
You can still change it per notebook, for example:

- `"esbe_2026"` to keep outputs inside `esbe/`
- `"../my_models"` for a sibling folder
- `"/absolute/path/to/models"` for a fixed location
