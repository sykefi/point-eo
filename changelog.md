## 0.1.dev

- Fixed a unnecessary null raster check in `postprocess_prediction.py`
- `predict` checks now the bounds of the `--extent` file and calculates the cell grid based on this. Allows for large rasters to be processed with smaller extents.
- Calculated cells are split to lists of 1000, which should fix the `FileNotFoundError: [WinError 206] The filename or extension is too long` - error.
- Demo extent file and command.

## 0.0.2:

- Fixed error handling for `FileNotFoundError: [WinError 206] The filename or extension is too long: 'E:\\anaconda\\anaconda3\\envs\\point-eo'`. This is caused most likely by file handles running out when the cell size is small and there are a lot of cells to process.

- Default verbosity is now `1`, meaning that only the progress bar is printed.

- Searching for empty cells to speed up calculations used Dask previously. This caused some memory errors in combination with `rasterio.clip`. Parallelization was changed to use `joblib` instead.

- Added printing of array sizes to make it easier to choose `--cell_size`

## 0.1.0:

- Tests
- Moved the project to use pyproject.toml in place of setup.py
- `analysis` has the option for saving the dataframe that produces the permutation importance figure
- `analysis` now saves the predictions into a csv file. This and the update above make it easier to create publication-ready figures.
- NEW `feature_selection` script. Feature importance evaluation with `sklearn` `SequentialFeatureSelector` and linear regression coefficients is implemented.