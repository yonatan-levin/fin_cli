"""Simple usage: Screen stocks using Finviz filters.

This example demonstrates the basic two-step workflow:
1. Use finpack.screen() to filter stocks based on criteria
2. Results are returned as a pandas DataFrame

No CLI, no pipeline objects - just straightforward function calls.
"""

from __future__ import annotations

import finpack


def main() -> None:
    """Screen for large-cap stocks and analyze a single symbol."""

    # Step 1: Screen stocks using Finviz
    print("=" * 60)
    print("Step 1: Screening stocks via Finviz")
    print("=" * 60)
    
    try:
        df = finpack.screen(
            scrape_link="https://finviz.com/screener.ashx?v=111&f=cap_large"
        )
        print(f"Found {len(df)} large-cap stocks")
        print(df.head())
    except Exception as e:
        print(f"Screening skipped (network error): {e}")

    # Step 2: Analyze fundamental ratios for specific symbols
    print("\n" + "=" * 60)
    print("Step 2: Analyzing fundamentals for AAPL")
    print("=" * 60)
    
    try:
        analysis_df = finpack.analyze(["AAPL"])
        print(analysis_df.T)  # Transpose for better readability
    except Exception as e:
        print(f"Analysis skipped (data fetch error): {e}")


if __name__ == "__main__":
    main()
