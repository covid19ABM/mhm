import os
import pandas as pd
from pathlib import Path


# This test ensures that the column names across the lockdown and
# action files are the same, and in the same order.
# This is important for the subsequent matrix
# multiplications done in the model.


def test_input_example_matrices():
    directory = Path("parameters/")

    csv_files = [f for f in os.listdir(directory) if
                 (f.endswith('.csv') and
                  (f.startswith('lockdown') or
                   f.startswith('actions')))
                 ]

    if not list(directory.glob("lockdown*.csv")) + \
            list(directory.glob("actions*.csv")):
        raise ValueError(f"No CSV files found in the directory '"
                         f"{str(directory.absolute())}'.")
    # Load the file
    first_df = pd.read_csv(os.path.join(directory, csv_files[0]), sep=";")

    # Get the column names, number of columns and rows,
    # data types, and unique entries in "actions" column
    column_names = first_df.columns.str.lower()
    num_columns = len(column_names)
    num_rows = len(first_df)
    actions = set(first_df['actions'].unique())

    for file in csv_files[1:]:
        df = pd.read_csv(os.path.join(directory, file), sep=";")
        df.columns = df.columns.str.lower()
        # Check for the same number of columns
        assert len(df.columns) == num_columns, \
            f"{file} has a different number of columns."

        # Check for the same number of rows
        assert len(df) == num_rows, \
            f"{file} has a different number of rows."

        # Check for the same column names
        if set(df.columns) != set(column_names):
            missing = set(column_names).difference(df.columns)
            additional = set(df.columns).difference(column_names)
            raise AssertionError(
                f"{file} has different column names. "
                f"Missing: {missing}. Additional: {additional}"
            )

        # Check for the same column order
        if list(df.columns) != list(column_names):
            diff_order = [i for i, (col_df, col_base) in
                          enumerate(zip(df.columns, column_names)) if
                          col_df != col_base]
            raise AssertionError(
                f"{file} has different column order at indices: {diff_order}."
            )

        # Check for the same "actions" entries
        assert set(df['actions'].unique()) == actions, \
            f"{file} has different 'actions' entries."
