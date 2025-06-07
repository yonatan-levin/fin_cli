import numpy as np
from pandas import DataFrame
import cProfile
from concurrent.futures import ThreadPoolExecutor

from shared.infrastructure.config import get_config
from ..calculators.equity_calc import get_financial_data, calculate_price_to_data, ratio_between_two_values
from ..calculators.filters import Filters
from logger import logger


def add_new_columns(df: DataFrame):
    df["price_by_assets"] = df.apply(
        lambda x: calculate_price_to_data(x, 'Adjusted Total Assets'), axis=1)
    df["price_by_current_assets"] = df.apply(
        lambda x: calculate_price_to_data(x, 'Adjusted Total Current Assets'), axis=1)
    df["price/price_to_current_assets_ratio"] = df.apply(lambda x: ratio_between_two_values(
        x["Average Price in Last 30 Days"], x["price_by_current_assets"]), axis=1)
    df["price/price_to_assets_ratio"] = df.apply(lambda x: ratio_between_two_values(
        x["Average Price in Last 30 Days"], x["price_by_assets"]), axis=1)
    return df


def picker(df: DataFrame | None):

    if df is None:
        return

    logger.info(f"Getting Financial Data --->")

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(get_financial_data, df["Symbol"]))

        valid_results = [res for res in results if res is not None]
        df_fundamentals = DataFrame(valid_results)

    # df_fundamentals = DataFrame([get_financial_data(ticker) for ticker in df["Symbol"]])

    assign_old_df_to_new_df(df, df_fundamentals, "Ticker")
    assign_old_df_to_new_df(df, df_fundamentals, "Sector")
    assign_old_df_to_new_df(df, df_fundamentals, "Industry")
    assign_old_df_to_new_df(df, df_fundamentals, "Country")

    logger.info(f"Calculating the price to assets ratio",
                "Calculating the price to assets ratio --->")

    df_fundamentals = add_new_columns(df_fundamentals)
    # Filter columns
    columns_to_retain = [
        'Ticker',
        'Sector',
        'Industry',
        'Country',
        'Market Cap',
        'Average Price in Last 30 Days',
        'price_by_assets',
        'price_by_current_assets',
        'price/price_to_current_assets_ratio',
        'price/price_to_assets_ratio'
    ]

    df_fundamentals = df_fundamentals[columns_to_retain]

    file_path = get_config().file_path("funda_insight_result_unfiltered")
    df_fundamentals.to_csv(file_path, index=False)

    df_fundamentals = Filters(df_fundamentals).filter_countries(["Brazil", "Chile", "India", "Bermuda", "China"]).filter_sector(
        "Energy").filter_price("price/price_to_current_assets_ratio", 1).get_data()

    return df_fundamentals


def assign_old_df_to_new_df(old_df: DataFrame, new_df: DataFrame, colum: str):
    if len(new_df) == len(old_df[colum]):
        new_df[colum] = old_df[colum].values
    else:
        min_length = min(len(new_df), len(old_df[colum]))
        new_df[colum] = old_df[colum].values[:min_length]
        # Optionally, fill the remaining values with NaN or another placeholder
        if len(new_df) > min_length:
            new_df[colum][min_length:] = np.nan
    return new_df


if __name__ == "__main__":
    # Sample DataFrame for testing
    df_sample = DataFrame({"Symbol": ["AAPL", "MSFT", "GOOGL"], "Ticker": [
                          "AAPL", "MSFT", "GOOGL"]})  # Add more tickers if needed

    profiler = cProfile.Profile()
    profiler.enable()

    picker(df_sample)

    profiler.disable()
    profiler.dump_stats("profile_results.pstat")
