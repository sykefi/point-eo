# point-eo

Python library and module for training machine learning models on point-based data and large rasters.

Features:

- Sampling features from a raster using point geometries
- Model training with sklearn and AutoML with TPOT
- Model performance metrics
- Prediction on large rasters

See the [demo](docs/demo.md) for more details on features and a guide on running point-eo on the command line.
See the [demo notebook](docs/demo_notebook.ipynb) for a demo of the Python API.

## Overview

![Overview](docs/images/point-eo-overview.png)

## Installation

You have to have [miniforge](https://conda-forge.org/download/) installed. `point-eo` will depends on `gdal` and must be installed in a conda environment.

```cmd
conda create -n pointeo python=3.10 -y
conda activate pointeo
conda install gdal xgboost geopandas rasterio rioxarray -c conda-forge -y

pip install git+https://github.com/sykefi/point-eo
```

Now `point-eo` should be available on the command line. Running

```cmd
point-eo --help
```

shows available commands. You can find documentation of each command by running the command name and `--help`, for example:

```cmd
point-eo analysis --help
```
