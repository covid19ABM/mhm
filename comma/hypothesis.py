"""Hypothesis class definition"""

from datetime import datetime
import json
import os
import pandas as pd
import re
import requests
from typing import List, Tuple, Set, Dict
from tqdm import tqdm

PARAMS_INDIVIDUAL = 'params_individual.json'
PARAMS_IPF_WEIGHTS = "ipf_weights.csv"


class Hypothesis:
    """
    The Hypothesis class is responsible for managing and validating
    hypotheses specified by the user.

    Methods:
        _get_one_hot_encoded_features():
            One-hot encodes categorical features
        create_empty_hypotheses():
            Creates empty CSV files for storing hypotheses
        validate_param_file():
            Validates the files in the parameter folder

    Usage:
        Hypothesis.create_empty_hypotheses("/path/to/dir_params")
        Hypothesis.validate_param_file("/path/to/dir_params")
    """
    _required_params = ['size', 'steps', 'actions', 'status',
                        'lockdown_policies', 'lockdown']

    lockdown_policies = [
        'absent',
        'easy',
        'medium',
        'hard'
    ]

    individual_status = [
        'mh'
    ]

    all_possible_features = [
        'age_group__1',
        'age_group__2',
        'age_group__3',
        'age_group__4',
        'gender_f',
        'gender_m',
        'education_high',
        'education_low',
        'education_medium',
        'unemployed_no',
        'unemployed_yes',
        'have_partner_no',
        'have_partner_yes',
        'depressed_no',
        'depressed_yes',
        'children_presence_no',
        'children_presence_yes',
        'housing_financial_difficulties_no',
        'housing_financial_difficulties_yes',
        'selfrated_health_average',
        'selfrated_health_good',
        'selfrated_health_poor',
        'critical_job_no',
        'critical_job_yes'
    ]

    all_possible_actions = [
        'work_from_home',
        'maintain_physical_distance',
        'stay_at_home',
        'exercise',
        'socialise',
        'travel',
        'seek_help',
        'negative_coping',
        'positive_coping',
        'socialise_online'
    ]

    @staticmethod
    def get_file_paths(url: str) -> List:
        """
        Extract file paths from url

        Args:
        url (str): website

        Returns:
        file_paths (list): list of '.csv.gz' file paths
        """

        response = requests.get(url)
        # Will raise an HTTPError
        # if the HTTP request was unsuccessful
        response.raise_for_status()
        data = response.json()
        # extract '.csv.gz' file paths
        file_paths = [
            item['path'] for item in data['payload']['tree']['items']
        ]

        return file_paths

    @staticmethod
    def filter_dates(file_list: List,
                     time_period: Tuple[str, str]) -> List[str]:
        """
        Select dates within the interval defined by `time_period`

        Args:

        file_list (List): list of file paths
        time_period (Tuple): time interval of the time t0 -> t1

        Returns:
        filtered_paths (List): list of filtered paths

        Raises:
        ValueError: if the time_period is not within the
        range of dates in the file
        """
        start = datetime.strptime(time_period[0], '%Y-%m-%d')
        end = datetime.strptime(time_period[1], '%Y-%m-%d')

        # regular expression to extract dates from string
        pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')

        all_dates = []

        for file in file_list:
            match = pattern.search(file)
            if match:
                date = datetime.strptime(match.group(1), '%Y-%m-%d')
                all_dates.append(date)

        if not all_dates:
            raise ValueError("Dates provided are not within the list")

        min_date = min(all_dates)
        max_date = max(all_dates)

        if start < min_date or end > max_date:
            raise ValueError(
                f"time_period ({time_period[0]} - {time_period[1]}) "
                f"is outside available dates that go from "
                f"({min_date} to {max_date})"
            )

        # Filtering the dates now that we know they're within the range
        filtered_paths = [
            file for file in file_list
            if start <= datetime.strptime(
                pattern.search(file).group(1), '%Y-%m-%d'
            ) <= end
        ]

        return filtered_paths

    def get_covid_data(self, time_period: Tuple[str, str],
                       location: str) -> pd.DataFrame:
        """
        Download and filter COVID-19 test data from the RIVM website.

        Args:
        time_period (tuple): Start and end date ('YYYY-MM-DD', 'YYYY-MM-DD').
        location (str): Security region name. This is the name of the city.

        Returns:
        df_filtered (pandas.DataFrame): Filtered data.
        """

        furl_tests = ("https://github.com/mzelst/covid-19/raw/"
                      "master/data-rivm/tests/")

        dates = self.get_file_paths(furl_tests)
        filtered_dates = self.filter_dates(dates, time_period)

        df_gzip = []

        for date in tqdm(filtered_dates, desc="Downloading data"):
            full_url = furl_tests + date.split('/')[-1]
            df = pd.read_csv(full_url, compression="gzip",
                             header=0, sep=",", quotechar='"')
            if not isinstance(df, pd.DataFrame):
                raise ValueError(
                    f"Data retrieved from {furl_tests}"
                    f" is not a DataFrame but a {type(df)}"
                )
            df_gzip.append(df)

        df_tests = pd.concat(df_gzip, ignore_index=True)

        df_tests['Date_of_statistics'] = pd.to_datetime(
            df_tests['Date_of_statistics']
        )

        mask = (df_tests['Date_of_statistics'] >= time_period[0]) & \
               (df_tests['Date_of_statistics'] <= time_period[1]) & \
               (df_tests['Security_region_name'] == location)
        df_filtered = df_tests.loc[mask].reset_index(drop=True)

        return df_filtered

    @classmethod
    def read_hypotheses(cls, dir_params: str, policies: Set[str],
                        data_type: str) -> Dict[str, pd.DataFrame]:
        """
        Read in CSV matrices for either actions or lockdowns.

        Args:
            dir_params (str): path of the parameters folder
            policies (set): set object of either actions or lockdown list
            data_type (str): either 'actions' or 'lockdown'

        Returns:
            data_dfs (dict): A dictionary where the key is either an action
                             effect or lockdown policy, and the value is a
                             processed dataframe.
        """

        # Ensure valid data type
        if data_type not in ['actions', 'lockdown']:
            raise ValueError("data_type should be either"
                             "'actions' or 'lockdown'.")

        file_patterns = {
            'actions': 'actions_effects_on_mh_%s.csv',
            'lockdown': 'lockdown_%s.csv'
        }

        data_dfs = {}

        for policy in policies:
            fpath_params = os.path.join(
                dir_params, file_patterns[data_type] % policy
            )

            df = pd.read_csv(fpath_params, delimiter=';', decimal=".")

            for col in df.columns:
                if col != "actions":
                    df[col] = df[col].astype(float)

            # sort rows
            df['actions'] = df['actions'].astype('category')
            df['actions'] = df['actions']\
                .cat.set_categories(cls.all_possible_actions)
            df = df.sort_values(by='actions', ignore_index=True)

            # Convert dataframe column names and cols to lowercase
            df.columns = df.columns.str.lower()
            cols = [col.lower() for col in cls.all_possible_features]
            cols.insert(0, "baseline")

            # get and sort desired columns
            df = df[cols]

            data_dfs[policy] = df

        return data_dfs

    @staticmethod
    def _get_one_hot_encoded_features(fpath_params_individual: str) -> List:
        """
        One-hot encode categorical features in the
        `params_individual.json` file and return the
        feature list.

        Args:
            fpath_params_individual (str): Path to the
            individual parameters JSON file.

        Returns:
            features (list): List of one-hot encoded features.

        """
        with open(fpath_params_individual) as f:
            params_individual = json.load(f)

        features = []
        for key, value in params_individual.items():
            if isinstance(value[0][0], str):
                features += [key + '_' + v for v in value[0]]
            else:
                features += [key]
        return features

    @classmethod
    def create_empty_hypotheses(cls, dir_params: str) -> None:
        """
        Create empty CSV files for storing hypotheses on
        the impact of actions and lockdown policies on different agent statuses

        Args:
            dir_params (str): The directory of the folder that contains
            the agent and model parameter files.
        Returns:
            None: This function does not return anything
            as it creates empty csv files int the specified directory
        """
        fpath_params_individual = os.path.join(dir_params, PARAMS_INDIVIDUAL)

        # Check if the files exist
        if not os.path.exists(fpath_params_individual):
            raise FileNotFoundError(f"'{PARAMS_INDIVIDUAL}' \
            file is missing in the directory '{dir_params}'")

        actions = cls.all_possible_actions
        lockdown_policies = cls.lockdown_policies
        status = cls.individual_status
        columns = ['actions', 'baseline']
        columns += cls._get_one_hot_encoded_features(fpath_params_individual)
        df = pd.DataFrame(0, index=range(len(actions)), columns=columns)
        df['actions'] = actions

        output_fpaths = ['lockdown_%s.csv' % lockdown for
                         lockdown in lockdown_policies]
        output_fpaths += ['actions_effects_on_%s.csv' % s for s in status]
        output_fpaths = [os.path.join(dir_params, fp) for fp in output_fpaths]
        for fp in output_fpaths:
            df.to_csv(fp, sep=';', index=False)

    @classmethod
    def validate_param_file(cls, dir_params: str) -> None:
        """Validate files in the parameter folder.

        Args:
            dir_params (str): dir to the folder containing
            hypothesis and parameter files.

        Raises:
            ValueError: If any validation checks fail.
        """
        # check if parameter files exist
        path_individual = os.path.join(dir_params, PARAMS_INDIVIDUAL)

        # check if all hypothesis files exist
        fnames = ["actions_effects_on_%s_%s.csv" % (status, policy)
                  for status in Hypothesis.individual_status
                  for policy in Hypothesis.lockdown_policies]
        fnames += ["lockdown_%s.csv" %
                   lockdown for lockdown in cls.lockdown_policies]
        fpaths = [os.path.join(dir_params, fn) for fn in fnames]
        fexist = [os.path.isfile(fp) for fp in fpaths]
        if not all(fexist):
            raise ValueError("Hypothesis file(s) not found: %s." % ", ".join(
                [fnames[i] for i in range(len(fnames)) if not fexist[i]]
            ))

        # check if all hypothesis files contain all the required agent features
        required_features = ["actions", "baseline"]
        required_features += cls._get_one_hot_encoded_features(path_individual)
        hypothesis_data = [pd.read_csv(fp, sep=";", decimal=",")
                           for fp in fpaths]
        missing_features = []
        for hd in hypothesis_data:
            # lower case labels
            missing_features.append(set([f.lower() for f in required_features])
                                    - set([c.lower() for c in hd.columns]))

        if any(missing_features):
            raise ValueError("Missing features:\n%s" % "\n".join(
                ["%s - %s" % (fnames[i], ", ".join(missing_features[i]))
                 for i in range(len(fnames)) if missing_features[i]]
            ))

        # check if all hypothesis files contain hypotheses of all actions
        required_actions = cls.all_possible_actions
        missing_actions = [set(required_actions) - set(hd["actions"])
                           for hd in hypothesis_data]
        if any(missing_actions):
            raise ValueError("Missing actions:\n%s" % "\n".join(
                ["%s - %s" % (fnames[i], ", ".join(missing_actions[i]))
                 for i in range(len(fnames)) if missing_actions[i]]
            ))
