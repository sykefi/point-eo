"""
Performs inference on a geotiff, outputs a classification map and confidences
"""

from pathlib import Path
import subprocess

import pickle
import numpy as np
import shapely
import rioxarray
import xarray as xr
import geopandas as gpd
from tqdm import tqdm
import dask.array as da
from joblib import Parallel, delayed

from rioxarray.exceptions import NoDataInBounds


def new_3d_xda(c, d):
    return xr.DataArray(
        c,
        name="classification",
        coords={"class": np.arange(c.shape[0]), "y": d.y, "x": d.x},
        dims=("class", "y", "x"),
    )


def new_2d_xda(c, d):
    return xr.DataArray(c, coords={"y": d.y, "x": d.x}, dims=("y", "x"))


def save_raster(x, name, crs):
    if not da.all(x == da.zeros_like(x)):
        x.rio.to_raster(name, compress="LZW", crs=crs, tiled=True, windowed=True)


def batch2img(sample, shape):
    H, W = shape
    return sample.reshape(H, W, sample.shape[1]).permute(2, 0, 1)


def full_inference_numpy(A, clf):
    # Reshaping
    A0 = np.moveaxis(A, 0, 2)
    ny, nx, chan = A0.shape
    a = A0.reshape(ny * nx, chan)

    # Classification
    c = clf.predict_proba(a)

    # Inverse reshaping
    C = c.reshape(ny, nx, -1)
    C = np.moveaxis(C, 2, 0)

    return C


def create_cell_grid(
    Fx,
    cell_size,
):
    # Make grid
    xmin = Fx.x.min()
    ymin = Fx.y.min()
    xmax = Fx.x.max()
    ymax = Fx.y.max()

    # projection of the grid
    # create the cells in a loop
    grid_cells = []
    for x0 in np.arange(xmin, xmax + cell_size, cell_size):
        for y0 in np.arange(ymin, ymax + cell_size, cell_size):
            # bounds
            x1 = x0 - cell_size
            y1 = y0 + cell_size
            grid_cells.append(shapely.geometry.box(x0, y0, x1, y1))

    return grid_cells

def clip_arr(C_arr, c, Ax, clip_buffer, crs):
    out_C_buf = new_3d_xda(C_arr, Ax)
    out_C_buf = out_C_buf.rio.write_crs(crs)

    clipper = c.buffer(-clip_buffer, cap_style=3, join_style=2)

    return out_C_buf.rio.clip([clipper])


def check_cell(Fx, cell):
    try:
        Ax = Fx.rio.clip([cell], from_disk=True)
        return not da.all(Ax == da.zeros_like(Ax)).compute()
    except NoDataInBounds:
        return False
    except ValueError:
        return False
    except np.core._exceptions._ArrayMemoryError:
        print("ArrayMemoryError. Setting cell as True")
        return True


def calculate(
    model,
    Fx,
    cell_list,
    start_index=0,
    global_index = 0,
    clip_buffer=0,
    bit_depth=8,
    crs="EPSG:3067",
    out_folder="predict_output",
    verbose=2,
    pbar = None
):
    si = start_index
    i = global_index
    out_folder = Path(out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)


    for c in cell_list:
        if i < si:
            i += 1
            if pbar:
                pbar.update(1)
        else:
            try:
                Ax = Fx.rio.clip([c], from_disk=True)
                if not da.all(Ax == da.zeros_like(Ax)).compute():
                    C_arr = full_inference_numpy(np.asarray(Ax.compute()), model)

                    try:
                        out_C = clip_arr(C_arr, c, Ax, clip_buffer, crs)
                    except FileNotFoundError: 
                        raise Exception("Running out of file handles. You can try continuing the run " \
                            f"by restarting the script with the parameter --start_index {i-1}." \
                                "However, it is recommended to make --cell_size larger, deleting the patch folder " 
                                "and restarting the script."
                        )

                    out_C = (out_C * (2**bit_depth - 1)).astype("uint16")

                    out_fname = Path(out_folder) / f"C_{i:04d}.tif"
                    save_raster(out_C, out_fname, crs=crs)
                    if verbose == 2:
                        print(f"SAVED {i}")
                else:
                    if verbose == 2:
                        print(f"Skip empty {i}")

            except NoDataInBounds:
                if verbose == 2:
                    print(f"NoDataInBounds in {i}")
            except ValueError:
                if verbose == 2:
                    print(f"ValueError in {i}")
            if pbar:
                pbar.update(1)
            i += 1
    return i


def merge_folder(folder, output, crs="EPSG:3067"):
    folder = Path(folder)

    filelist = list(folder.glob("*.tif"))
    filelist = [str(x.resolve()) + "\n" for x in filelist]
    with open(folder / "filelist.txt", "w") as f:
        f.writelines(filelist)

    print("Writing .vrt file...")
    subprocess.run(
        [
            "gdalbuildvrt",
            "-input_file_list",
            folder / "filelist.txt",
            "-a_srs",
            crs,
            output,
        ]
    )


def add_args(subparser):
    parser = subparser.add_parser("predict")
    parser.add_argument(
        "--model", type=str, required=True, help="Location of pickled model"
    )

    parser.add_argument(
        "--input_raster",
        type=str,
        required=True,
        help="The input raster to be classified",
    )

    parser.add_argument(
        "--cell_size",
        type=int,
        required=True,
        help="The raster is split up to smaller blocks of cell_size X "
        "cell_size. Use as large value as your memory permits.",
    )

    parser.add_argument(
        "--cell_buffer",
        "--block_buffer",
        type=int,
        required=True,
        help="Buffers each cell this much in meters",
    )

    parser.add_argument(
        "--bit_depth",
        type=int,
        required=False,
        default=8,
        help="Output confidence raster is quantized to this range. "
        "If bit depth is 8, values range from 0-255.",
    )

    parser.add_argument(
        "--extent",
        type=str,
        required=False,
        help="Providing an extent geometry makes processing faster as "
        "areas outside extent are not calculated. If not provided, "
        "calculation starts by finding empty cells.",
    )
    parser.add_argument(
        "--calculate_empty",
        action="store_true",
        help="Passing this argument calculates all empty cells. "
        "Useful ff extent is not provided and the raster is not rectangular",
    )

    parser.add_argument("--out_folder", type=str, required=True, help="Output folder")

    parser.add_argument(
        "--start_index",
        type=int,
        required=False,
        help="Starts processing from here in case of a crash.",
    )
    parser.add_argument(
        "--crs", type=str, required=False, default="EPSG:3067", help="CRS for outputs"
    )

    parser.add_argument(
        "--verbose", type=int, default=1, help="Set to 2 if you want everything to be printed. Default 1"
    )


def main(args):
    input_file = Path(args.input_raster)
    model_file = Path(args.model)
    out_folder = Path(args.out_folder) / f"{input_file.stem}_patches"
    out_folder.mkdir(exist_ok=True, parents=True)
    out_final = Path(args.out_folder)

    # Model
    print(f"Using model {args.model}")
    with open(args.model, "rb") as f:
        model = pickle.load(f)

    print(model)

    # Raster
    chunk_s = 2**10
    Fx = rioxarray.open_rasterio(
        args.input_raster,
        chunks={"band": -1, "x": chunk_s, "y": chunk_s},
        lock=False,
        parallel=True,
    )

    # if args.extent:
    #     # Clip the raster to the maximum bounds of the extent file
    #     extent = gpd.read_file(args.extent)
    #     bounds_geometry = shapely.geometry.box(*extent.total_bounds)
    #     Fx = Fx.rio.clip([bounds_geometry], from_disk=True)

    grid_cells = create_cell_grid(Fx, args.cell_size)
    cell = gpd.GeoDataFrame(grid_cells, columns=["geometry"], crs=args.crs)
    cell = cell.buffer(args.cell_buffer, cap_style=3, join_style=2)
    cell.to_file(out_final / "cell_grid.geojson")

    # Print cell size
    Ax_first = Fx.rio.clip([cell[len(cell)//2]], from_disk=True) # Take a cell from the middle of array
    print(f"Cell size in pixels is: {Ax_first.shape}" \
          f"\nCell size in MB is: {Ax_first.nbytes / (1024*1024):.4f}" \
           "\nAdjust cell_size if a larger array fits to memory")

    # set start index
    if not args.start_index:
        si = -1
    else:
        si = args.start_index

    # If an extent shp is provided, it is used
    if args.extent:
        extent = gpd.read_file(args.extent)
        calc_cells = cell.geometry.apply(lambda x: extent.intersects(x).any()).values
        if calc_cells.sum() == 0:
            raise Exception("Zero cells to be calculated! Check the extent and its CRS.")
    elif args.calculate_empty:
        # otherwise find empty cells in parallel if calculate_empty is assigned
        try:
            # If the empty cells have been calculated they are cached
            calc_cells = np.load(out_folder / "empty_index.npy")
            print("found existing cell index")
        except FileNotFoundError:
            list_of_delayed_functions = []

            print("Checking empty cells...")
            calc_cells = Parallel(n_jobs=-1)(delayed(check_cell)(Fx, c) for c in tqdm(cell))

            calc_cells = [x for x in calc_cells]
            np.save(out_folder / "empty_index.npy", calc_cells)
    else:
        calc_cells = np.full(len(grid_cells), True)

    # Actual calculation and saving of cells
    # Cell list is split into lists of 1000 to solve memory issues and file handles running out
    full_cell_list = cell.iloc[calc_cells]

    if (args.verbose == 1) or (args.verbose == 2):
        pbar = tqdm(total=len(full_cell_list))
    else:
        pbar = None

    global_index = 0
    for cell_list in np.array_split(full_cell_list, 1000):
        global_index = calculate(
            model=model,
            Fx=Fx,
            cell_list=cell_list,
            start_index=si,
            global_index=global_index,
            clip_buffer=args.cell_buffer,
            bit_depth=args.bit_depth,
            crs=args.crs,
            out_folder=out_folder,
            verbose=args.verbose,
            pbar=pbar
        )

    # Merge to a vrt file
    merge_folder(
        out_folder,
        crs=args.crs,
        output=out_final / f"{input_file.stem}__{model_file.stem}_C.vrt",
    )


if __name__ == "__main__":
    main()
    exit()
