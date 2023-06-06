"""
Performs inference on a geotiff, outputs a classification map and confidences
"""

import argparse
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
import dask
from dask.diagnostics import ProgressBar

from rioxarray.exceptions import NoDataInBounds

new_3d_xda = lambda c, d: xr.DataArray(
    c,
    name="classification",
    coords={"class": np.arange(c.shape[0]), "y": d.y, "x": d.x},
    dims=("class", "y", "x"),
)
new_2d_xda = lambda c, d: xr.DataArray(c, coords={"y": d.y, "x": d.x}, dims=("y", "x"))


def save_raster(x, name, crs):
    if not da.all(x == da.zeros_like(x)):
        x.rio.to_raster(name, compress="LZW", crs=crs, tiled=True, windowed=True)


# def process_xarray(Ax, tf):
#     T = torch.Tensor(da.asarray(Ax).compute())
#     T = tf(T)
#     return T

# def img2batch(sample, k):
#     pad = k//2
#     C,H,W = sample.shape

#     unfold = torch.nn.Unfold(kernel_size=(k,k), padding=pad)
#     UF = unfold(sample.unsqueeze(0))
#     B = torch.stack([UF[0,:,i].reshape((C,k,k)) for i in range(UF.shape[2])])

#     return B


def batch2img(sample, shape):
    H, W = shape
    return sample.reshape(H, W, sample.shape[1]).permute(2, 0, 1)


# def classify_block(T, model, k):
#     device = 'cuda' if torch.cuda.is_available() else 'cpu'
#     C,H,W = T.shape
#     B = img2batch(T, k=k)
#     B = B.to(device)

#     with torch.no_grad():
#         out = model(B).softmax(1)
#     outimg = batch2img(out, (H,W))
#     return outimg


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


def add_args(subparser):
    parser = subparser.add_parser("predict")
    parser.add_argument(
        "--model", type=str, required=True, help="Location of pickled model"
    )

    parser.add_argument("--input_raster", type=str, required=True)

    parser.add_argument("--cell_size", type=int)

    parser.add_argument("--block_buffer", type=int, help="block buffer in meters")

    parser.add_argument("--bit_depth", type=int, default=8)

    parser.add_argument("--extent", type=str, required=False)
    parser.add_argument("--out_folder", type=str, required=True)
    parser.add_argument(
        "--start_index", type=int, help="Starts processing from here in case of a crash"
    )
    parser.add_argument(
        "--crs", type=str, required=False, default="EPSG:3067", help="CRS for outputs"
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

    # Make grid
    xmin = Fx.x.min()
    ymin = Fx.y.min()
    xmax = Fx.x.max()
    ymax = Fx.y.max()

    cell_size = args.cell_size
    # projection of the grid
    crs = "EPSG:3067"
    # create the cells in a loop
    grid_cells = []
    for x0 in np.arange(xmin, xmax + cell_size, cell_size):
        for y0 in np.arange(ymin, ymax + cell_size, cell_size):
            # bounds
            x1 = x0 - cell_size
            y1 = y0 + cell_size
            grid_cells.append(shapely.geometry.box(x0, y0, x1, y1))
    cell = gpd.GeoDataFrame(grid_cells, columns=["geometry"], crs=crs)
    cell = cell.buffer(args.block_buffer, cap_style=3, join_style=2)

    cell.to_file(out_final / "cell_grid.geojson")

    # set start index
    if not args.start_index:
        si = -1
    else:
        si = args.start_index

    # If an extent shp is provided, it is used
    if args.extent:
        extent = gpd.read_file(args.extent)
        calc_cells = cell.geometry.apply(lambda x: extent.intersects(x).any()).values
    else:
        # otherwise find empty cells in parallel
        try:
            # If the empty cells have been calculated they are cached
            calc_cells = np.load(out_folder / "empty_index.npy")
            print("found existing cell index")
        except FileNotFoundError:
            list_of_delayed_functions = []

            def check_cell(Fx, cell):
                try:
                    Ax = Fx.rio.clip([cell], from_disk=True)
                    return not da.all(Ax == da.zeros_like(Ax)).compute()
                except NoDataInBounds:
                    return False
                except ValueError:
                    return False

            print("Checking empty cells...")
            for i, c in enumerate(cell):
                list_of_delayed_functions.append(dask.delayed(check_cell)(Fx, c))

            with ProgressBar():
                calc_cells = dask.compute(*list_of_delayed_functions)

            calc_cells = [x for x in calc_cells]
            np.save(out_folder / "empty_index.npy", calc_cells)

    for i, c in enumerate(tqdm(cell.iloc[calc_cells])):
        if i < si:  # start index
            pass
        else:
            try:
                Ax = Fx.rio.clip([c], from_disk=True)
                if not da.all(Ax == da.zeros_like(Ax)).compute():
                    C_arr = full_inference_numpy(np.asarray(Ax.compute()), model)

                    out_C_buf = new_3d_xda(C_arr, Ax)
                    out_C_buf = out_C_buf.rio.write_crs(args.crs)

                    clipper = c.buffer(-args.block_buffer, cap_style=3, join_style=2)

                    out_C = out_C_buf.rio.clip([clipper])

                    out_C = (out_C * (2**args.bit_depth - 1)).astype("uint16")

                    out_fname = Path(out_folder) / f"C_{i:04d}.tif"
                    save_raster(out_C, out_fname, crs=args.crs)
                    print(f"SAVED {i}")
                else:
                    print(f"Skip empty {i}")

            except NoDataInBounds:
                print(f"Error in {i}")
            except ValueError:
                print(f"Error in {i}")

    # Merge to a vrt file
    filelist = list(out_folder.glob("*.tif"))
    filelist = [str(x.resolve()) + "\n" for x in filelist]
    with open(out_folder / "filelist.txt", "w") as f:
        f.writelines(filelist)

    print("Writing .vrt file...")
    subprocess.run(
        [
            "gdalbuildvrt",
            "-input_file_list",
            out_folder / "filelist.txt",
            "-a_srs",
            args.crs,
            out_final / f"{input_file.stem}__{model_file.stem}_C.vrt",
        ]
    )


if __name__ == "__main__":
    main()
    exit()
