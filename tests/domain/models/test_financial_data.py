"""
Unit tests for FinancialData domain models.
"""
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from fundainsight.domain.models.financial_data import (
    FinancialData,
    FinancialDataCollection,
    FinancialMetric,
    FinancialPeriod,
    FinancialStatement
)


class TestFinancialMetric(unittest.TestCase):
    """Test cases for the FinancialMetric class."""

    def test_financial_metric_initialization(self):
        """Test initializing a FinancialMetric with valid data."""
        # Arrange & Act
        metric = FinancialMetric(
            name="Revenue",
            value=Decimal("75300000000"),
            unit="USD"
        )
        
        # Assert
        self.assertEqual(metric.name, "Revenue")
        self.assertEqual(metric.value, Decimal("75300000000"))
        self.assertEqual(metric.unit, "USD")
    
    def test_metric_name_validation(self):
        """Test that FinancialMetric validates the name."""
        # Empty name
        with self.assertRaises(ValueError):
            FinancialMetric(name="", value=Decimal("100"))
        
        # Non-string name
        with self.assertRaises(TypeError):
            FinancialMetric(name=123, value=Decimal("100"))  # type: ignore
    
    def test_metric_value_validation(self):
        """Test that FinancialMetric validates the value."""
        # Non-decimal value
        with self.assertRaises(TypeError):
            FinancialMetric(name="Revenue", value="not a decimal")  # type: ignore
    
    def test_metric_to_dict(self):
        """Test converting a FinancialMetric to a dictionary."""
        # Arrange
        metric = FinancialMetric(
            name="Revenue",
            value=Decimal("75300000000"),
            unit="USD"
        )
        
        # Act
        data = metric.to_dict()
        
        # Assert
        self.assertEqual(data["name"], "Revenue")
        self.assertEqual(data["value"], "75300000000")  # Should be converted to string
        self.assertEqual(data["unit"], "USD")
    
    def test_metric_from_dict(self):
        """Test creating a FinancialMetric from a dictionary."""
        # Arrange
        data = {
            "name": "Revenue",
            "value": "75300000000",
            "unit": "USD"
        }
        
        # Act
        metric = FinancialMetric.from_dict(data)
        
        # Assert
        self.assertEqual(metric.name, "Revenue")
        self.assertEqual(metric.value, Decimal("75300000000"))
        self.assertEqual(metric.unit, "USD")
    
    def test_metric_from_dict_with_numeric_value(self):
        """Test creating a FinancialMetric from a dictionary with numeric value."""
        # Arrange
        data = {
            "name": "Revenue",
            "value": 75300000000,  # Numeric instead of string
            "unit": "USD"
        }
        
        # Act
        metric = FinancialMetric.from_dict(data)
        
        # Assert
        self.assertEqual(metric.value, Decimal("75300000000"))


class TestFinancialStatement(unittest.TestCase):
    """Test cases for the FinancialStatement class."""
    
    def test_financial_statement_initialization(self):
        """Test initializing a FinancialStatement with valid data."""
        # Arrange
        metrics = [
            FinancialMetric(name="Revenue", value=Decimal("75300000000"), unit="USD"),
            FinancialMetric(name="Net Income", value=Decimal("18200000000"), unit="USD"),
            FinancialMetric(name="EPS", value=Decimal("1.15"), unit="USD")
        ]
        
        # Act
        statement = FinancialStatement(
            statement_type="Income Statement",
            metrics=metrics
        )
        
        # Assert
        self.assertEqual(statement.statement_type, "Income Statement")
        self.assertEqual(len(statement.metrics), 3)
        self.assertEqual(statement.metrics[0].name, "Revenue")
        self.assertEqual(statement.metrics[1].name, "Net Income")
        self.assertEqual(statement.metrics[2].name, "EPS")
    
    def test_statement_type_validation(self):
        """Test that FinancialStatement validates the statement_type."""
        # Empty statement_type
        with self.assertRaises(ValueError):
            FinancialStatement(statement_type="", metrics=[])
        
        # Non-string statement_type
        with self.assertRaises(TypeError):
            FinancialStatement(statement_type=123, metrics=[])  # type: ignore
    
    def test_find_metric_by_name(self):
        """Test finding a metric by name."""
        # Arrange
        metrics = [
            FinancialMetric(name="Revenue", value=Decimal("75300000000"), unit="USD"),
            FinancialMetric(name="Net Income", value=Decimal("18200000000"), unit="USD"),
            FinancialMetric(name="EPS", value=Decimal("1.15"), unit="USD")
        ]
        statement = FinancialStatement(
            statement_type="Income Statement",
            metrics=metrics
        )
        
        # Act
        revenue_metric = statement.find_metric_by_name("Revenue")
        net_income_metric = statement.find_metric_by_name("Net Income")
        
        # Assert
        self.assertIsNotNone(revenue_metric)
        self.assertEqual(revenue_metric.value, Decimal("75300000000"))
        self.assertIsNotNone(net_income_metric)
        self.assertEqual(net_income_metric.value, Decimal("18200000000"))
    
    def test_find_metric_by_name_case_insensitive(self):
        """Test that finding a metric by name is case-insensitive."""
        # Arrange
        metrics = [
            FinancialMetric(name="Revenue", value=Decimal("75300000000"), unit="USD")
        ]
        statement = FinancialStatement(
            statement_type="Income Statement",
            metrics=metrics
        )
        
        # Act
        revenue_metric = statement.find_metric_by_name("revenue")
        
        # Assert
        self.assertIsNotNone(revenue_metric)
        self.assertEqual(revenue_metric.value, Decimal("75300000000"))
    
    def test_find_metric_by_name_not_found(self):
        """Test finding a metric by name that doesn't exist."""
        # Arrange
        metrics = [
            FinancialMetric(name="Revenue", value=Decimal("75300000000"), unit="USD")
        ]
        statement = FinancialStatement(
            statement_type="Income Statement",
            metrics=metrics
        )
        
        # Act
        non_existent_metric = statement.find_metric_by_name("Non-existent Metric")
        
        # Assert
        self.assertIsNone(non_existent_metric)
    
    def test_statement_to_dict(self):
        """Test converting a FinancialStatement to a dictionary."""
        # Arrange
        metrics = [
            FinancialMetric(name="Revenue", value=Decimal("75300000000"), unit="USD"),
            FinancialMetric(name="Net Income", value=Decimal("18200000000"), unit="USD")
        ]
        statement = FinancialStatement(
            statement_type="Income Statement",
            metrics=metrics
        )
        
        # Act
        data = statement.to_dict()
        
        # Assert
        self.assertEqual(data["statement_type"], "Income Statement")
        self.assertEqual(len(data["metrics"]), 2)
        self.assertEqual(data["metrics"][0]["name"], "Revenue")
        self.assertEqual(data["metrics"][0]["value"], "75300000000")
        self.assertEqual(data["metrics"][1]["name"], "Net Income")
        self.assertEqual(data["metrics"][1]["value"], "18200000000")
    
    def test_statement_from_dict(self):
        """Test creating a FinancialStatement from a dictionary."""
        # Arrange
        data = {
            "statement_type": "Income Statement",
            "metrics": [
                {
                    "name": "Revenue",
                    "value": "75300000000",
                    "unit": "USD"
                },
                {
                    "name": "Net Income",
                    "value": "18200000000",
                    "unit": "USD"
                }
            ]
        }
        
        # Act
        statement = FinancialStatement.from_dict(data)
        
        # Assert
        self.assertEqual(statement.statement_type, "Income Statement")
        self.assertEqual(len(statement.metrics), 2)
        self.assertEqual(statement.metrics[0].name, "Revenue")
        self.assertEqual(statement.metrics[0].value, Decimal("75300000000"))
        self.assertEqual(statement.metrics[1].name, "Net Income")
        self.assertEqual(statement.metrics[1].value, Decimal("18200000000"))


class TestFinancialPeriod(unittest.TestCase):
    """Test cases for the FinancialPeriod class."""
    
    def test_financial_period_initialization(self):
        """Test initializing a FinancialPeriod with valid data."""
        # Arrange & Act
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2022, 3, 31)
        period = FinancialPeriod(
            period_type="Quarter",
            fiscal_year=2022,
            fiscal_period="Q1",
            start_date=start_date,
            end_date=end_date
        )
        
        # Assert
        self.assertEqual(period.period_type, "Quarter")
        self.assertEqual(period.fiscal_year, 2022)
        self.assertEqual(period.fiscal_period, "Q1")
        self.assertEqual(period.start_date, start_date)
        self.assertEqual(period.end_date, end_date)
    
    def test_period_type_validation(self):
        """Test that FinancialPeriod validates the period_type."""
        # Invalid period_type
        with self.assertRaises(ValueError):
            FinancialPeriod(
                period_type="Invalid",
                fiscal_year=2022,
                fiscal_period="Q1",
                start_date=datetime(2022, 1, 1),
                end_date=datetime(2022, 3, 31)
            )
    
    def test_fiscal_year_validation(self):
        """Test that FinancialPeriod validates the fiscal_year."""
        # Negative fiscal_year
        with self.assertRaises(ValueError):
            FinancialPeriod(
                period_type="Quarter",
                fiscal_year=-2022,
                fiscal_period="Q1",
                start_date=datetime(2022, 1, 1),
                end_date=datetime(2022, 3, 31)
            )
    
    def test_date_validation(self):
        """Test that FinancialPeriod validates the dates."""
        # end_date before start_date
        with self.assertRaises(ValueError):
            FinancialPeriod(
                period_type="Quarter",
                fiscal_year=2022,
                fiscal_period="Q1",
                start_date=datetime(2022, 3, 31),
                end_date=datetime(2022, 1, 1)  # Before start_date
            )
    
    def test_period_to_dict(self):
        """Test converting a FinancialPeriod to a dictionary."""
        # Arrange
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2022, 3, 31)
        period = FinancialPeriod(
            period_type="Quarter",
            fiscal_year=2022,
            fiscal_period="Q1",
            start_date=start_date,
            end_date=end_date
        )
        
        # Act
        data = period.to_dict()
        
        # Assert
        self.assertEqual(data["period_type"], "Quarter")
        self.assertEqual(data["fiscal_year"], 2022)
        self.assertEqual(data["fiscal_period"], "Q1")
        self.assertEqual(data["start_date"], start_date.isoformat())
        self.assertEqual(data["end_date"], end_date.isoformat())
    
    def test_period_from_dict(self):
        """Test creating a FinancialPeriod from a dictionary."""
        # Arrange
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2022, 3, 31)
        data = {
            "period_type": "Quarter",
            "fiscal_year": 2022,
            "fiscal_period": "Q1",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        # Act
        period = FinancialPeriod.from_dict(data)
        
        # Assert
        self.assertEqual(period.period_type, "Quarter")
        self.assertEqual(period.fiscal_year, 2022)
        self.assertEqual(period.fiscal_period, "Q1")
        self.assertEqual(period.start_date, start_date)
        self.assertEqual(period.end_date, end_date)


class TestFinancialData(unittest.TestCase):
    """Test cases for the FinancialData class."""
    
    def setUp(self):
        """Set up test data."""
        self.start_date = datetime(2022, 1, 1)
        self.end_date = datetime(2022, 3, 31)
        self.period = FinancialPeriod(
            period_type="Quarter",
            fiscal_year=2022,
            fiscal_period="Q1",
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        self.income_metrics = [
            FinancialMetric(name="Revenue", value=Decimal("75300000000"), unit="USD"),
            FinancialMetric(name="Net Income", value=Decimal("18200000000"), unit="USD")
        ]
        
        self.balance_metrics = [
            FinancialMetric(name="Total Assets", value=Decimal("350000000000"), unit="USD"),
            FinancialMetric(name="Total Liabilities", value=Decimal("270000000000"), unit="USD")
        ]
        
        self.cash_flow_metrics = [
            FinancialMetric(name="Operating Cash Flow", value=Decimal("25000000000"), unit="USD"),
            FinancialMetric(name="Investing Cash Flow", value=Decimal("-15000000000"), unit="USD")
        ]
        
        self.statements = [
            FinancialStatement(statement_type="Income Statement", metrics=self.income_metrics),
            FinancialStatement(statement_type="Balance Sheet", metrics=self.balance_metrics),
            FinancialStatement(statement_type="Cash Flow", metrics=self.cash_flow_metrics)
        ]
    
    def test_financial_data_initialization(self):
        """Test initializing a FinancialData with valid data."""
        # Act
        financial_data = FinancialData(
            symbol="AAPL",
            period=self.period,
            statements=self.statements,
            currency="USD",
            source="Annual Report"
        )
        
        # Assert
        self.assertEqual(financial_data.symbol, "AAPL")
        self.assertEqual(financial_data.period, self.period)
        self.assertEqual(len(financial_data.statements), 3)
        self.assertEqual(financial_data.currency, "USD")
        self.assertEqual(financial_data.source, "Annual Report")
    
    def test_symbol_validation(self):
        """Test that FinancialData validates the symbol."""
        # Empty symbol
        with self.assertRaises(ValueError):
            FinancialData(
                symbol="",
                period=self.period,
                statements=self.statements
            )
        
        # Non-string symbol
        with self.assertRaises(TypeError):
            FinancialData(
                symbol=123,  # type: ignore
                period=self.period,
                statements=self.statements
            )
    
    def test_uppercase_symbol(self):
        """Test that FinancialData converts the symbol to uppercase."""
        # Arrange & Act
        financial_data = FinancialData(
            symbol="aapl",
            period=self.period,
            statements=self.statements
        )
        
        # Assert
        self.assertEqual(financial_data.symbol, "AAPL")
    
    def test_get_statement_by_type(self):
        """Test getting a statement by type."""
        # Arrange
        financial_data = FinancialData(
            symbol="AAPL",
            period=self.period,
            statements=self.statements
        )
        
        # Act
        income_statement = financial_data.get_statement_by_type("Income Statement")
        balance_sheet = financial_data.get_statement_by_type("Balance Sheet")
        cash_flow = financial_data.get_statement_by_type("Cash Flow")
        
        # Assert
        self.assertIsNotNone(income_statement)
        self.assertEqual(income_statement.statement_type, "Income Statement")
        self.assertIsNotNone(balance_sheet)
        self.assertEqual(balance_sheet.statement_type, "Balance Sheet")
        self.assertIsNotNone(cash_flow)
        self.assertEqual(cash_flow.statement_type, "Cash Flow")
    
    def test_get_statement_by_type_case_insensitive(self):
        """Test that getting a statement by type is case-insensitive."""
        # Arrange
        financial_data = FinancialData(
            symbol="AAPL",
            period=self.period,
            statements=self.statements
        )
        
        # Act
        income_statement = financial_data.get_statement_by_type("income statement")
        
        # Assert
        self.assertIsNotNone(income_statement)
        self.assertEqual(income_statement.statement_type, "Income Statement")
    
    def test_get_statement_by_type_not_found(self):
        """Test getting a statement by type that doesn't exist."""
        # Arrange
        financial_data = FinancialData(
            symbol="AAPL",
            period=self.period,
            statements=self.statements
        )
        
        # Act
        non_existent_statement = financial_data.get_statement_by_type("Non-existent Statement")
        
        # Assert
        self.assertIsNone(non_existent_statement)
    
    def test_get_metric_value(self):
        """Test getting a metric value by statement type and metric name."""
        # Arrange
        financial_data = FinancialData(
            symbol="AAPL",
            period=self.period,
            statements=self.statements
        )
        
        # Act
        revenue = financial_data.get_metric_value("Income Statement", "Revenue")
        total_assets = financial_data.get_metric_value("Balance Sheet", "Total Assets")
        operating_cash_flow = financial_data.get_metric_value("Cash Flow", "Operating Cash Flow")
        
        # Assert
        self.assertEqual(revenue, Decimal("75300000000"))
        self.assertEqual(total_assets, Decimal("350000000000"))
        self.assertEqual(operating_cash_flow, Decimal("25000000000"))
    
    def test_get_metric_value_not_found(self):
        """Test getting a metric value that doesn't exist."""
        # Arrange
        financial_data = FinancialData(
            symbol="AAPL",
            period=self.period,
            statements=self.statements
        )
        
        # Act & Assert
        # Non-existent statement
        self.assertIsNone(financial_data.get_metric_value("Non-existent Statement", "Revenue"))
        
        # Non-existent metric
        self.assertIsNone(financial_data.get_metric_value("Income Statement", "Non-existent Metric"))
    
    def test_financial_data_to_dict(self):
        """Test converting a FinancialData to a dictionary."""
        # Arrange
        financial_data = FinancialData(
            symbol="AAPL",
            period=self.period,
            statements=self.statements,
            currency="USD",
            source="Annual Report"
        )
        
        # Act
        data = financial_data.to_dict()
        
        # Assert
        self.assertEqual(data["symbol"], "AAPL")
        self.assertEqual(data["period"]["fiscal_year"], 2022)
        self.assertEqual(data["period"]["fiscal_period"], "Q1")
        self.assertEqual(len(data["statements"]), 3)
        self.assertEqual(data["statements"][0]["statement_type"], "Income Statement")
        self.assertEqual(data["statements"][1]["statement_type"], "Balance Sheet")
        self.assertEqual(data["statements"][2]["statement_type"], "Cash Flow")
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["source"], "Annual Report")
    
    def test_financial_data_from_dict(self):
        """Test creating a FinancialData from a dictionary."""
        # Arrange
        data = {
            "symbol": "AAPL",
            "period": {
                "period_type": "Quarter",
                "fiscal_year": 2022,
                "fiscal_period": "Q1",
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat()
            },
            "statements": [
                {
                    "statement_type": "Income Statement",
                    "metrics": [
                        {
                            "name": "Revenue",
                            "value": "75300000000",
                            "unit": "USD"
                        },
                        {
                            "name": "Net Income",
                            "value": "18200000000",
                            "unit": "USD"
                        }
                    ]
                },
                {
                    "statement_type": "Balance Sheet",
                    "metrics": [
                        {
                            "name": "Total Assets",
                            "value": "350000000000",
                            "unit": "USD"
                        },
                        {
                            "name": "Total Liabilities",
                            "value": "270000000000",
                            "unit": "USD"
                        }
                    ]
                }
            ],
            "currency": "USD",
            "source": "Annual Report"
        }
        
        # Act
        financial_data = FinancialData.from_dict(data)
        
        # Assert
        self.assertEqual(financial_data.symbol, "AAPL")
        self.assertEqual(financial_data.period.fiscal_year, 2022)
        self.assertEqual(financial_data.period.fiscal_period, "Q1")
        self.assertEqual(len(financial_data.statements), 2)
        self.assertEqual(financial_data.statements[0].statement_type, "Income Statement")
        self.assertEqual(financial_data.statements[1].statement_type, "Balance Sheet")
        self.assertEqual(financial_data.currency, "USD")
        self.assertEqual(financial_data.source, "Annual Report")


class TestFinancialDataCollection(unittest.TestCase):
    """Test cases for the FinancialDataCollection class."""
    
    def setUp(self):
        """Set up test data."""
        # Q1 2022
        q1_start = datetime(2022, 1, 1)
        q1_end = datetime(2022, 3, 31)
        q1_period = FinancialPeriod(
            period_type="Quarter",
            fiscal_year=2022,
            fiscal_period="Q1",
            start_date=q1_start,
            end_date=q1_end
        )
        
        q1_income_metrics = [
            FinancialMetric(name="Revenue", value=Decimal("75300000000"), unit="USD"),
            FinancialMetric(name="Net Income", value=Decimal("18200000000"), unit="USD")
        ]
        
        q1_statements = [
            FinancialStatement(statement_type="Income Statement", metrics=q1_income_metrics)
        ]
        
        self.q1_data = FinancialData(
            symbol="AAPL",
            period=q1_period,
            statements=q1_statements
        )
        
        # Q2 2022
        q2_start = datetime(2022, 4, 1)
        q2_end = datetime(2022, 6, 30)
        q2_period = FinancialPeriod(
            period_type="Quarter",
            fiscal_year=2022,
            fiscal_period="Q2",
            start_date=q2_start,
            end_date=q2_end
        )
        
        q2_income_metrics = [
            FinancialMetric(name="Revenue", value=Decimal("83000000000"), unit="USD"),
            FinancialMetric(name="Net Income", value=Decimal("20500000000"), unit="USD")
        ]
        
        q2_statements = [
            FinancialStatement(statement_type="Income Statement", metrics=q2_income_metrics)
        ]
        
        self.q2_data = FinancialData(
            symbol="AAPL",
            period=q2_period,
            statements=q2_statements
        )
        
        # MSFT Q1 2022
        msft_q1_income_metrics = [
            FinancialMetric(name="Revenue", value=Decimal("49360000000"), unit="USD"),
            FinancialMetric(name="Net Income", value=Decimal("16730000000"), unit="USD")
        ]
        
        msft_q1_statements = [
            FinancialStatement(statement_type="Income Statement", metrics=msft_q1_income_metrics)
        ]
        
        self.msft_q1_data = FinancialData(
            symbol="MSFT",
            period=q1_period,  # Same period as AAPL Q1
            statements=msft_q1_statements
        )
        
        # Create collection
        self.collection = FinancialDataCollection(
            financial_data_list=[self.q1_data, self.q2_data, self.msft_q1_data]
        )
    
    def test_filter_by_symbol(self):
        """Test filtering financial data by symbol."""
        # Act
        aapl_data = self.collection.filter_by_symbol("AAPL")
        msft_data = self.collection.filter_by_symbol("MSFT")
        
        # Assert
        self.assertEqual(len(aapl_data.financial_data_list), 2)
        self.assertEqual(aapl_data.financial_data_list[0].symbol, "AAPL")
        self.assertEqual(aapl_data.financial_data_list[1].symbol, "AAPL")
        
        self.assertEqual(len(msft_data.financial_data_list), 1)
        self.assertEqual(msft_data.financial_data_list[0].symbol, "MSFT")
    
    def test_filter_by_symbol_case_insensitive(self):
        """Test that filtering by symbol is case-insensitive."""
        # Act
        aapl_data = self.collection.filter_by_symbol("aapl")
        
        # Assert
        self.assertEqual(len(aapl_data.financial_data_list), 2)
    
    def test_filter_by_symbol_no_match(self):
        """Test filtering by a symbol with no matches."""
        # Act
        non_existent_data = self.collection.filter_by_symbol("GOOG")
        
        # Assert
        self.assertEqual(len(non_existent_data.financial_data_list), 0)
    
    def test_filter_by_period_type(self):
        """Test filtering financial data by period type."""
        # Act
        quarterly_data = self.collection.filter_by_period_type("Quarter")
        
        # Assert
        self.assertEqual(len(quarterly_data.financial_data_list), 3)
        
        # Test with non-existent period type
        annual_data = self.collection.filter_by_period_type("Annual")
        self.assertEqual(len(annual_data.financial_data_list), 0)
    
    def test_filter_by_fiscal_year(self):
        """Test filtering financial data by fiscal year."""
        # Act
        data_2022 = self.collection.filter_by_fiscal_year(2022)
        
        # Assert
        self.assertEqual(len(data_2022.financial_data_list), 3)
        
        # Test with non-existent fiscal year
        data_2021 = self.collection.filter_by_fiscal_year(2021)
        self.assertEqual(len(data_2021.financial_data_list), 0)
    
    def test_filter_by_fiscal_period(self):
        """Test filtering financial data by fiscal period."""
        # Act
        q1_data = self.collection.filter_by_fiscal_period("Q1")
        q2_data = self.collection.filter_by_fiscal_period("Q2")
        
        # Assert
        self.assertEqual(len(q1_data.financial_data_list), 2)
        self.assertEqual(q1_data.financial_data_list[0].period.fiscal_period, "Q1")
        self.assertEqual(q1_data.financial_data_list[1].period.fiscal_period, "Q1")
        
        self.assertEqual(len(q2_data.financial_data_list), 1)
        self.assertEqual(q2_data.financial_data_list[0].period.fiscal_period, "Q2")
        
        # Test with non-existent fiscal period
        q3_data = self.collection.filter_by_fiscal_period("Q3")
        self.assertEqual(len(q3_data.financial_data_list), 0)
    
    def test_filter_by_date_range(self):
        """Test filtering financial data by date range."""
        # Act
        # Range covering Q1 only
        q1_range_data = self.collection.filter_by_date_range(
            start_date=datetime(2022, 1, 1),
            end_date=datetime(2022, 3, 31)
        )
        
        # Range covering Q1 and Q2
        full_range_data = self.collection.filter_by_date_range(
            start_date=datetime(2022, 1, 1),
            end_date=datetime(2022, 6, 30)
        )
        
        # Range not covering any period
        no_range_data = self.collection.filter_by_date_range(
            start_date=datetime(2021, 1, 1),
            end_date=datetime(2021, 12, 31)
        )
        
        # Assert
        self.assertEqual(len(q1_range_data.financial_data_list), 2)  # AAPL Q1 and MSFT Q1
        self.assertEqual(len(full_range_data.financial_data_list), 3)  # All three
        self.assertEqual(len(no_range_data.financial_data_list), 0)  # None
    
    def test_to_dict_list(self):
        """Test converting the collection to a list of dictionaries."""
        # Act
        dict_list = self.collection.to_dict_list()
        
        # Assert
        self.assertEqual(len(dict_list), 3)
        self.assertEqual(dict_list[0]["symbol"], "AAPL")
        self.assertEqual(dict_list[0]["period"]["fiscal_period"], "Q1")
        self.assertEqual(dict_list[1]["symbol"], "AAPL")
        self.assertEqual(dict_list[1]["period"]["fiscal_period"], "Q2")
        self.assertEqual(dict_list[2]["symbol"], "MSFT")
        self.assertEqual(dict_list[2]["period"]["fiscal_period"], "Q1")


if __name__ == "__main__":
    unittest.main() 