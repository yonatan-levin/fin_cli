"""Advanced usage: Two-step workflow with enrichment.

This example demonstrates:
1. Screening stocks with Finviz filters
2. Analyzing fundamentals for multiple symbols
3. Enriching screen results with fundamental analysis

The two-step API replaces the old pipeline approach with explicit, simple function calls.
"""

from __future__ import annotations

import finpack


def main() -> None:
    """Demonstrate two-step workflow: screen → analyze → enrich."""

    # Step 1: Screen stocks with specific criteria
    print("=" * 60)
    print("Step 1: Screening mid-cap+ stocks with P/E < 40")
    print("=" * 60)
    
    filters = [
        ("cap", "midover"),  # Mid-cap or larger
        ("fa_pe", "u40"),    # P/E under 40
    ]
    
    try:
        screen_df = finpack.screen(filters=filters)
        print(f"Found {len(screen_df)} stocks matching criteria")
        print(screen_df[["Symbol", "Company", "Sector", "Market Cap", "P/E", "Price"]].head())
    except Exception as e:
        print(f"Screening failed: {e}")
        return

    # Step 2: Analyze fundamentals for a subset of symbols
    print("\n" + "=" * 60)
    print("Step 2: Analyzing fundamentals for specific symbols")
    print("=" * 60)
    
    symbols = ["AAPL", "MSFT", "GOOGL", "DECK"]
    
    try:
        analysis_df = finpack.analyze(symbols)
        print(f"Analyzed {len(analysis_df)} symbols")
        print(
            analysis_df[[
                "Ticker",
                "Sector", 
                "Average Price in Last 30 Days",
                "price_by_assets",
                "price/price_to_assets_ratio"
            ]]
        )
    except Exception as e:
        print(f"Analysis failed: {e}")

    # Step 3 (Optional): Enrich screening results with fundamental analysis
    print("\n" + "=" * 60)
    print("Step 3: Enriching screen results with analysis (optional)")
    print("=" * 60)
    
    try:
        # This merges screen and analyze results on Symbol
        enriched_df = finpack.enrich(screen_df)
        print(f"Enriched {len(enriched_df)} stocks with fundamental ratios")
        print(
            enriched_df[[
                "Symbol",
                "Company",
                "Sector",
                "price_by_assets",
                "price/price_to_assets_ratio"
            ]].head()
        )
        
        # Optionally persist enriched results
        # enriched_df.to_csv("./workspace_output/enriched_results.csv", index=False)
        
    except Exception as e:
        print(f"Enrichment failed: {e}")


if __name__ == "__main__":
    main()
