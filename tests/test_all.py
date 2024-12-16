import pytest
import argparse
from point_eo.scripts import sample_raster, feature_selection, analysis, tpot_train, predict, set_band_description, postprocess_prediction

def get_parser():
    parser = argparse.ArgumentParser(prog="point-eo")
    subparsers = parser.add_subparsers(title="Available commands", dest="script")
    sample_raster.add_args(subparsers)
    feature_selection.add_args(subparsers)
    analysis.add_args(subparsers)
    tpot_train.add_args(subparsers)
    predict.add_args(subparsers)
    set_band_description.add_args(subparsers)
    postprocess_prediction.add_args(subparsers)
    return parser

def test_sample_raster():
    test_args = ["sample_raster",
                 "--input", "data/points_clc.geojson",
                 "--input_raster", "data/s2_2018_lataseno.tif",
                 "--target", "corine",
                 "--out_folder", "test_project/samples"]
    parser = get_parser()
    args = parser.parse_args(test_args)
    sample_raster.main(args)

def test_analysis():
    test_args = ["analysis",
                 "--input", "tests/data/analysis/s2_2018_lataseno__points_clc__corine.csv",
                 "--out_prefix", "demo_rf",
                 "--out_folder", "test_project/analysis",
                 "--separator", ",",
                 "--decimal", ".",
                 "--remove_classes_smaller_than", "6"]
    parser = get_parser()
    args = parser.parse_args(test_args)
    analysis.main(args)

def test_analysis_save_permutation_importance():
    test_args = ["analysis",
                 "--input", "tests/data/analysis/s2_2018_lataseno__points_clc__corine.csv",
                 "--out_prefix", "demo_rf",
                 "--save_permutation_importance",
                 "--out_folder", "test_project/analysis",
                 "--separator", ",",
                 "--decimal", ".",
                 "--remove_classes_smaller_than", "6"]
    parser = get_parser()
    args = parser.parse_args(test_args)
    analysis.main(args)

def test_feature_selection():
    test_args = ["feature_selection",
                 "--input", "tests/data/analysis/s2_2018_lataseno__points_clc__corine.csv",
                 "--out_prefix", "demo_rf",
                 "--out_folder", "test_project/feature_selection",
                 "--separator", ",",
                 "--decimal", ".",
                 "--remove_classes_smaller_than", "6",
                "--sequential_feature_selector",
                "--n_features", "5",
                "--direction", "forward",
                "--logistic_regression_coefficients"]
    parser = get_parser()
    args = parser.parse_args(test_args)
    feature_selection.main(args)

def test_tpot_train():
    test_args = ["tpot_train",
                 "--input", "tests/data/analysis/s2_2018_lataseno__points_clc__corine.csv",
                 "--out_prefix", "tpot_demo",
                 "--out_folder", "test_project/test_tpot",
                 "--generations", "2",
                 "--population_size", "10",
                 "--scoring", "f1_weighted"
    ]
    parser = get_parser()
    args = parser.parse_args(test_args)
    tpot_train.main(args)

def test_tpot_analysis():
    test_args = ["analysis",
                 "--input", "tests/data/analysis/s2_2018_lataseno__points_clc__corine.csv",
                 "--out_prefix", "tpot_demo",
                 "--out_folder", "test_project/test_tpot",
                 "--tpot_model", "tests/data/models/tpot_demo_acc0.6685_241209T171008.py",
                 "--separator", ",",
                 "--decimal", ".",
                 "--remove_classes_smaller_than", "6"]
    parser = get_parser()
    args = parser.parse_args(test_args)
    analysis.main(args)

def test_predict_rf():
    test_args = ["predict",
                 "--model", "tests/data/models/demo_rf__s2_2018_lataseno__points_clc__corine__2024-12-09T17-04-59_model.pkl",
                 "--input_raster", "data/s2_2018_lataseno.tif",
                 "--cell_size", "3000",
                 "--cell_buffer", "2",
                 "--out_folder", "test_project/predictions"
    ]
    parser = get_parser()
    args = parser.parse_args(test_args)
    predict.main(args)

def test_predict_tpot_normal():
    test_args = ["predict",
                "--model", "tests/data/models/tpot_demo__s2_2018_lataseno__points_clc__corine__2024-12-12T10-17-34_model.pkl",
                "--input_raster", "data/s2_2018_lataseno.tif",
                "--cell_size", "3000",
                "--cell_buffer", "2",
                "--out_folder", "test_project/predictions_tpot"
    ]
    parser = get_parser()
    args = parser.parse_args(test_args)
    predict.main(args)

def test_predict_tpot_try_overwrite():
    from pathlib import Path
    dir = Path("test_project/predictions_overwrite/s2_2018_lataseno_patches")
    dir.mkdir(parents=True, exist_ok=True)
    Path(dir, "demo.tif").touch()
    with pytest.raises(SystemExit) as e:
        test_args = ["predict",
                    "--model", "tests/data/models/tpot_demo__s2_2018_lataseno__points_clc__corine__2024-12-12T10-17-34_model.pkl",
                    "--input_raster", "data/s2_2018_lataseno.tif",
                    "--cell_size", "3000",
                    "--cell_buffer", "2",
                    "--out_folder", "test_project/predictions_overwrite"
        ]
        parser = get_parser()
        args = parser.parse_args(test_args)
        predict.main(args)
    assert e.type == SystemExit
    assert e.value.code == 1

def test_set_band_description():
    test_args = ["set_band_description",
                 "--input_raster", "tests/data/predictions/demo.tif",
                 "--label_map", "tests/data/analysis/label_map.txt"
    ]
    parser = get_parser()
    args = parser.parse_args(test_args)
    set_band_description.main(args)

def test_postprocess_prediction():
    test_args = ["postprocess_prediction",
                 "--input_raster", "tests/data/predictions/demo.tif",
                 "--out_folder", "test_project/predictions",
                 "--label_map", "tests/data/analysis/label_map.txt"
    ]
    parser = get_parser()
    args = parser.parse_args(test_args)
    postprocess_prediction.main(args)