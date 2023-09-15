## 0.0.2:

- Fixed error handling for `FileNotFoundError: [WinError 206] The filename or extension is too long: 'E:\\anaconda\\anaconda3\\envs\\point-eo'`. This is caused most likely by file handles running out when the cell size is small and there are a lot of cells to process.

- Default verbosity is now `1`, meaning that only the progress bar is printed.

- Searching for empty cells to speed up calculations used Dask previously. This caused some memory errors in combination with `rasterio.clip`. Parallelization was changed to use `joblib` instead.

- Added printing of array sizes to make it easier to choose `--cell_size`