from datetime import datetime
from pathlib import Path
import logging
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from sklearn.feature_selection import SequentialFeatureSelector
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegressionCV
from sklearn.inspection import permutation_importance
from sklearn.model_selection import cross_val_score

def add_args(subparser):
    parser = subparser.add_parser(
        name="feature_selection",
        description="This program runs different algorithms for comparing feature "
        "importances. "
        "It takes a csv-file as an input, where the first column "
        "must be the target variable."
    )

    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="The csv-file containing the training data",
    )
    parser.add_argument(
        "--out_folder",
        type=str,
        required=False,
        default="model_fitting",
        help="The output folder",
    )
    parser.add_argument(
        "--out_prefix",
        type=str,
        required=True,
        help="The prefix that is added to saved files and figures",
    )
    parser.add_argument(
        "--separator",
        type=str,
        required=False,
        default=";",
        help="The csv separator character. Default ';'",
    )
    parser.add_argument(
        "--decimal",
        type=str,
        required=False,
        default=",",
        help="The csv decimal character. Default ','",
    )
    parser.add_argument(
        "--remove_classes_smaller_than",
        type=int,
        required=False,
        default=None,
        help="Classes smaller than this value are removed. Default None",
    )
    parser.add_argument(
        "--random_seed",
        type=int,
        required=False,
        default=None,
        help="Random seed. Set a value for deterministic output.",
    )
    
    parser.add_argument(
        "--sequential_feature_selector",
        action="store_true",
        required=False,
        default=False,
        help="Runs the SequentialFeatureSelector from sklearn. "
        "Set --direction and --n_features_to_select"
    )
    parser.add_argument(
        "--n_features_to_select",
        type=int,
        required=False,
        default=None,
        help="parameter n_features_to_select for SequentialFeatureSelector"
    )
    parser.add_argument(
        "--direction",
        choices=["forward", "backward"],
        default="forward",
        required=False,
        help="parameter direction for SequentialFeatureSelector"
    )

    parser.add_argument(
        "--logistic_regression_coefficients",
        action="store_true",
        required=False,
        default=False,
        help="Fits a logistic regression model to the data and saves the "
        "coefficients for evaluating feature correlation on classification odds"
    )


def main(args):
    uid = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


    # Logging
    input_stem = Path(args.input).stem

    out_folder = Path(args.out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)
    out_stem = Path(f"{args.out_prefix}__{input_stem}__{uid}")

    logging.basicConfig(
        filename=out_folder / out_stem.with_suffix(".log"),
        filemode="w",
        format="%(message)s",
        level=logging.INFO,
    )
    logging.getLogger().addHandler(logging.StreamHandler())

    # strings for colored output
    if sys.platform == "win32":
        green = red = blue = bold = RESET = ""
    else:
        green = "\033[92m"
        red = "\033[91m"
        blue = "\033[94m"
        bold = "\x1B[1m"
        RESET = "\x1b[0m"

    # Read the csv
    logging.info(f"Input csv: {args.input}")

    if Path(args.input).suffix == ".shp":
        raise Exception("You are trying to pass a shp file as input")

    df = pd.read_csv(args.input, sep=args.separator, decimal=args.decimal)

    dfX = df.iloc[:, 1:]
    dfY = df.iloc[:, 0]
    feature_names = dfX.columns

    # Print column info
    logging.info("\n\n### Data info ###\n")
    logging.info(bold + green + "Columns. First one is chosen as target" + RESET)
    logging.info("Index\t\tColumn")
    logging.info(green + f"{0}\t\t{dfY.name}")
    for i, col in enumerate(df.columns[1:]):
        logging.info(blue + f"{i+1}\t\t{col}" + RESET)
    logging.info("\n")
    logging.info(f"Shape of data table:\nrows: {df.shape[0]}\ncolumns: {df.shape[1]}")

    # If argument 'remove_small_classes' is set as 'True', remove classes smaller than the value

    if args.remove_classes_smaller_than:
        logging.info(
            bold
            + red
            + f"\nREMOVING CLASSES SMALLER THAN {args.remove_classes_smaller_than} SAMPLES"
            + RESET
        )
        drop_classes = dfY.value_counts()[
            dfY.value_counts() < args.remove_classes_smaller_than
        ].index.values
        drop_series = ~dfY.isin(drop_classes)
        logging.info(drop_classes)

        dfY = dfY.loc[drop_series]
        dfX = dfX.loc[drop_series, :]

    logging.info(bold + green + "\nTarget class distribution" + RESET)
    logging.info("label\tcount")
    logging.info(dfY.value_counts())
    logging.info("\n")

    # Convert to numpy arrays for processing
    X = dfX.to_numpy()
    y = dfY.astype("category")

    y_true = []
    y_pred = []
    model = RandomForestClassifier()
    logging.info("Fitting baseline Random Forest classifier with 5 cross validation folds")
    scores = cross_val_score(model, X, y, cv=5, scoring="f1_weighted")
    logging.info("%0.2f f1_weighted with a standard deviation of %0.2f" % (scores.mean(), scores.std()))

    model.fit(X,y)

    pi_results = permutation_importance(
        model,
        X,
        y,
        n_repeats=10,
        random_state=42,
        n_jobs=-1,
        scoring="f1_weighted",
    )
    pi_results = pd.DataFrame({"feature": feature_names, "importance": pi_results["importances_mean"]})
    pi_results = pi_results.sort_values("importance", ascending=False)
    logging.info("REFERENCE PERMUTATION IMPORTANCE")
    logging.info("Mean over 10 repetitions")
    logging.info(pi_results)


    if args.sequential_feature_selector:
        logging.info("\n\n### SEQUENTIAL FEATURE SELECTION ###")
        n_features = args.n_features_to_select
        direction = args.direction
        logging.info("SequentialFeatureSelector with %s features. Direction: '%s'", n_features, direction)
        print("Fitting selector...")
        sfs = SequentialFeatureSelector(model, direction=direction, n_features_to_select=n_features)
        sfs.fit(X, y)
        print("Done.")
        selected_features = feature_names[sfs.get_support()]
        logging.info("Selected features:")
        for i, feature in enumerate(selected_features):
            logging.info(f"{i+1}\t{feature}")


    if args.logistic_regression_coefficients:
        logging.info("\n\n### LOGISTIC REGRESSION (MAXENT) ###")
        logging.info("!!! This is an experimental feature !!!")
        model = LogisticRegressionCV(solver="liblinear")
        logging.info("Fitting Logistic Regression (MaxEnt) classifier with 5 cross validation folds")
        logging.info("The classifier is an one-vs-rest classifier")
        scores = cross_val_score(model, X, y, cv=5, scoring="f1_weighted")
        logging.info("%0.2f f1_weighted with a standard deviation of %0.2f" % (scores.mean(), scores.std()))

        model.fit((X - X.mean())/X.std(), y)

        B = model.coef_
        fig, ax = plt.subplots(figsize=(len(y.cat.categories)*1.2, len(feature_names)*0.4))
        sns.heatmap(B.T,
                    ax=ax,
                    xticklabels=y.cat.categories,
                    yticklabels=feature_names,
                    annot=True,
                    cmap=sns.color_palette("vlag", as_cmap=True))
        plt.title(f"Name: {args.out_prefix}\nDataset: {args.input} \nTimestamp: {uid}\nModel mean f1: {scores.mean():.2f}")
        outname = out_folder / f"{out_stem}_logreg_coefficients"
        df_logreg = pd.DataFrame(data=B.T, columns=y.cat.categories, index=feature_names)
        df_logreg.index.name = "feature"
        df_logreg.to_csv(f"{outname}.csv")
        plt.tight_layout()
        fig.savefig(f"{outname}.png")
        logging.info(green + f"Saved coefficients to {outname}.png and {outname}.csv" + RESET)