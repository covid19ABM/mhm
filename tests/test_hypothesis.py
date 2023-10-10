import pandas as pd
import pytest
from unittest.mock import patch
from comma.hypothesis import Hypothesis


class TestHypothesis:

    @pytest.fixture
    def mock_df(self):
        return pd.DataFrame({
            'Version': [2],
            'Date_of_report': ['2022-01-03T09:00:00Z'],
            'Date_of_statistics': ['2022-01-01'],
            'Security_region_code': ['VR01'],
            'Security_region_name': ['Groningen'],
            'Tested_with_result': [976],
            'Tested_positive': [378]
        })

    @pytest.fixture
    def file_list(self):
        return [
            'data-rivm/tests/rivm_daily_2021-01-01.csv.gz',
            'data-rivm/tests/rivm_daily_2021-01-02.csv.gz',
            'data-rivm/tests/rivm_daily_2021-01-15.csv.gz',
            'data-rivm/tests/rivm_daily_2021-01-30.csv.gz',
            'data-rivm/tests/rivm_daily_2021-02-01.csv.gz',
            'data-rivm/tests/rivm_daily_2021-02-15.csv.gz',
            'data-rivm/tests/rivm_daily_2021-02-28.csv.gz'
        ]

    def test_filter_dates_within_range(self, file_list):
        # Test whether function correctly filter out dates
        # that are *clearly* within the bounds of `time_period`
        time_period = ('2021-01-02', '2021-01-30')
        expected_output = [
            'data-rivm/tests/rivm_daily_2021-01-02.csv.gz',
            'data-rivm/tests/rivm_daily_2021-01-15.csv.gz',
            'data-rivm/tests/rivm_daily_2021-01-30.csv.gz'
        ]
        output = Hypothesis.filter_dates(file_list, time_period)
        assert output == expected_output

    def test_filter_dates_on_boundary(self, file_list):
        # Test whether function correctly includes
        # or excludes dates that are exactly on the edge
        time_period = ('2021-01-15', '2021-02-28')
        expected_output = [
            'data-rivm/tests/rivm_daily_2021-01-15.csv.gz',
            'data-rivm/tests/rivm_daily_2021-01-30.csv.gz',
            'data-rivm/tests/rivm_daily_2021-02-01.csv.gz',
            'data-rivm/tests/rivm_daily_2021-02-15.csv.gz',
            'data-rivm/tests/rivm_daily_2021-02-28.csv.gz'
        ]
        output = Hypothesis.filter_dates(file_list, time_period)
        assert output == expected_output

    def test_range_error(self, file_list):
        # Test that values outside the bounds raise an error
        time_period = ('2021-02-01', '2026-03-15')
        with pytest.raises(ValueError,
                           match=r"time_period .* is outside available dates"):
            Hypothesis.filter_dates(file_list, time_period)

    @patch('comma.hypothesis.Hypothesis.get_file_paths')
    @patch('comma.hypothesis.Hypothesis.filter_dates')
    @patch('comma.hypothesis.pd.read_csv')
    # Mock tqdm to just return an iterator
    @patch('comma.hypothesis.tqdm', side_effect=lambda x, *args, **kwargs: x)
    def test_get_covid_data(self, mocked_tqdm,
                            mocked_read_csv, mocked_filter_dates,
                            mocked_get_file_paths, mock_df):
        time_period = ('2022-01-01', '2022-01-3')
        location = "Groningen"

        # mock responses
        mocked_get_file_paths.return_value = ["some_path"]
        mocked_filter_dates.return_value = ["filtered_path"]
        mocked_read_csv.return_value = mock_df

        hypothesis_instance = Hypothesis()
        df = hypothesis_instance.get_covid_data(time_period, location)
        formatted_date = df.iloc[0]['Date_of_statistics'].strftime('%Y-%m-%d')
        assert not df.empty
        assert df.iloc[0]['Version'] == 2
        assert df.iloc[0]['Date_of_report'] == '2022-01-03T09:00:00Z'
        assert formatted_date == '2022-01-01'
        assert df.iloc[0]['Security_region_code'] == 'VR01'
        assert df.iloc[0]['Security_region_name'] == 'Groningen'
        assert df.iloc[0]['Tested_with_result'] == 976
        assert df.iloc[0]['Tested_positive'] == 378

        # assert mock methods
        mocked_get_file_paths.assert_called_once()
        mocked_filter_dates.assert_called_once_with(
            mocked_get_file_paths.return_value, time_period
        )
        mocked_read_csv.assert_called_once_with(
            "https://github.com/mzelst/covid-19/raw/"
            "master/data-rivm/tests/filtered_path",
            compression="gzip", header=0,
            sep=",", quotechar='"'
        )
