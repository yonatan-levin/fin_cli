import pandas as pd

class Filters:

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df

    def filter_country(self, country: str):
        self.df = self.df[self.df["Country"] != country]
        return self

    def filter_countries(self, countries: list):
        self.df = self.df[~self.df["Country"].isin(countries)]
        return self

    def filter_sector(self, sector: str):
        self.df = self.df[self.df["Sector"] != sector]
        return self

    def filter_price(self, column, price: float, less_than: bool = True):
        if less_than:
            self.df = self.df[self.df[column] < price]
        else:
            self.df = self.df[self.df[column] > price]
        return self
    
    def filter_invalid_data(self, columns: list = [], threshold: float = 0):
        """
        Filter out rows where specified columns have values less than or equal to threshold.
        
        Args:
            columns: List of column names to check. If None, uses default financial columns.
            threshold: Minimum value threshold (default: 0)
        
        Returns:
            Self for method chaining
        """
        if columns == []:
            columns = [
                "Market Cap",
                "Total Assets", 
                "Total Equity",
                "Adjusted Total Assets",
                "Adjusted Total Current Assets"
            ]
        # Create condition: all specified columns must be greater than threshold
        condition = pd.Series([True] * len(self.df), index=self.df.index)
        
        for column in columns:
            if column in self.df.columns:
                condition = condition & (self.df[column] > threshold)
        
        self.df = self.df[condition]
        return self

    def get_data(self) -> pd.DataFrame:
        return self.df
