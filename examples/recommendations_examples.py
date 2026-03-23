"""
Examples of using the recommendations generation module.

This file demonstrates practical usage patterns for generating
data-driven financial recommendations with data references.
"""

import asyncio
import json
from src.analysis.recommendations import (
    generate_recommendations,
    generate_recommendations_with_fallback,
)


# Example 1: Basic usage with mock data
async def example_basic_usage():
    """Generate recommendations with sample metrics."""
    
    # Sample financial metrics (in rubles)
    metrics = {
        "revenue": 5_000_000,
        "net_profit": 750_000,
        "total_assets": 10_000_000,
        "equity": 6_000_000,
        "liabilities": 4_000_000,
        "current_assets": 2_500_000,
        "short_term_liabilities": 1_500_000,
    }
    
    # Sample ratios (already calculated)
    ratios = {
        "current_ratio": 1.67,  # 2500000 / 1500000
        "equity_ratio": 0.60,   # 6000000 / 10000000
        "roe": 0.125,           # 750000 / 6000000 = 12.5%
        "roa": 0.075,           # 750000 / 10000000 = 7.5%
        "debt_to_revenue": 0.8,  # 4000000 / 5000000
    }
    
    # NLP analysis results
    nlp_result = {
        "risks": ["increasing competition", "supply chain disruption"],
        "key_factors": ["operational efficiency improvements", "market expansion"],
    }
    
    # Generate recommendations
    recommendations = await generate_recommendations(metrics, ratios, nlp_result)
    
    print("Generated Recommendations:")
    print("-" * 60)
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}\n")
    
    return recommendations


# Example 2: Handling AI unavailability with fallback
async def example_with_fallback():
    """Generate recommendations with fallback handling."""
    
    metrics = {
        "revenue": 1_000_000,
        "net_profit": 100_000,
    }
    
    ratios = {
        "current_ratio": 1.2,
        "roe": 0.1,
    }
    
    nlp_result = {"risks": ["high debt"]}
    
    # Use fallback recommendations if AI fails
    recommendations = await generate_recommendations_with_fallback(
        metrics, ratios, nlp_result, use_fallback=True
    )
    
    print(f"Received {len(recommendations)} recommendations")
    return recommendations


# Example 3: Strict mode without fallback
async def example_strict_mode():
    """Generate recommendations in strict mode (fail fast)."""
    
    metrics = {}  # Empty metrics
    ratios = {}
    nlp_result = {}
    
    # Will return empty list if generation fails (no fallback)
    recommendations = await generate_recommendations_with_fallback(
        metrics, ratios, nlp_result, use_fallback=False
    )
    
    print(f"Strict mode result: {len(recommendations)} recommendations")
    return recommendations


# Example 4: Integration pattern (as used in process_pdf)
async def example_integration_pattern():
    """
    Show how recommendations integrate with PDF processing.
    This mimics the pattern used in src/tasks.py
    """
    
    # These would come from PDF extraction in real usage
    metrics = {
        "revenue": 10_000_000,
        "net_profit": 1_500_000,
        "total_assets": 25_000_000,
        "equity": 15_000_000,
    }
    
    ratios = {
        "current_ratio": 1.5,
        "equity_ratio": 0.6,
        "roe": 0.1,
    }
    
    # From NLP analysis of narrative
    nlp_result = {
        "risks": ["market volatility", "regulatory changes"],
        "key_factors": ["cost reduction initiatives"],
        "recommendations": []  # Will be populated
    }
    
    # Generate recommendations
    try:
        recommendations = await asyncio.wait_for(
            generate_recommendations(metrics, ratios, nlp_result),
            timeout=65.0
        )
        nlp_result["recommendations"] = recommendations
        print(f"Successfully generated {len(recommendations)} recommendations")
        
    except asyncio.TimeoutError:
        print("Recommendation generation timed out")
    except Exception as e:
        print(f"Error: {e}")
    
    # Now nlp_result contains recommendations
    return nlp_result


# Example 5: Detailed inspection of generated recommendations
async def example_inspect_recommendations():
    """Inspect and analyze the structure of generated recommendations."""
    
    metrics = {
        "revenue": 2_000_000,
        "net_profit": 250_000,
    }
    
    ratios = {
        "current_ratio": 1.8,
        "roe": 0.125,
        "debt_to_revenue": 0.4,
    }
    
    nlp_result = {
        "risks": ["working capital management"],
    }
    
    recommendations = await generate_recommendations(metrics, ratios, nlp_result)
    
    print("Recommendation Analysis:")
    print("=" * 70)
    
    for i, rec in enumerate(recommendations, 1):
        print(f"\nRecommendation #{i}:")
        print(f"  Length: {len(rec)} characters")
        print(f"  Contains 'revenue': {'revenue' in rec.lower()}")
        print(f"  Contains 'roe': {'roe' in rec.lower()}")
        print(f"  Contains 'ликвидность': {'ликвидность' in rec.lower()}")
        print(f"  Text: {rec[:100]}...")
    
    return recommendations


# Example 6: Batch processing multiple companies
async def example_batch_processing():
    """Process recommendations for multiple companies."""
    
    companies = [
        {
            "name": "TechCorp",
            "metrics": {"revenue": 5_000_000, "net_profit": 1_000_000},
            "ratios": {"current_ratio": 2.0, "roe": 0.2},
        },
        {
            "name": "ManufactureCo",
            "metrics": {"revenue": 10_000_000, "net_profit": 500_000},
            "ratios": {"current_ratio": 1.0, "roe": 0.05},
        },
        {
            "name": "ServiceInc",
            "metrics": {"revenue": 2_000_000, "net_profit": 400_000},
            "ratios": {"current_ratio": 1.5, "roe": 0.2},
        },
    ]
    
    results = {}
    
    for company in companies:
        nlp_result = {
            "risks": ["market competition"],
            "key_factors": ["operational efficiency"],
        }
        
        recommendations = await generate_recommendations(
            company["metrics"],
            company["ratios"],
            nlp_result
        )
        
        results[company["name"]] = {
            "metrics": company["metrics"],
            "ratios": company["ratios"],
            "recommendations": recommendations,
        }
        
        print(f"\n{company['name']}: Generated {len(recommendations)} recommendations")
    
    return results


# Example 7: Error recovery and logging
async def example_error_recovery():
    """Demonstrate error handling and recovery."""
    
    print("Testing Error Recovery Scenarios:")
    print("=" * 60)
    
    # Scenario 1: Empty metrics
    print("\n1. Empty metrics:")
    result = await generate_recommendations({}, {}, {})
    print(f"   Result: {len(result)} recommendations (fallback used)")
    
    # Scenario 2: Minimal metrics
    print("\n2. Minimal metrics:")
    result = await generate_recommendations(
        {"revenue": 100000},
        {"current_ratio": 1.5},
        {"risks": ["high risk"]}
    )
    print(f"   Result: {len(result)} recommendations")
    
    # Scenario 3: Complete data
    print("\n3. Complete metrics:")
    result = await generate_recommendations(
        {
            "revenue": 5_000_000,
            "net_profit": 750_000,
            "total_assets": 10_000_000,
            "equity": 6_000_000,
            "liabilities": 4_000_000,
        },
        {
            "current_ratio": 1.67,
            "equity_ratio": 0.60,
            "roe": 0.125,
            "roa": 0.075,
            "debt_to_revenue": 0.8,
        },
        {
            "risks": ["competition", "supply chain"],
            "key_factors": ["efficiency", "market"],
        }
    )
    print(f"   Result: {len(result)} recommendations")


# Main runner
async def main():
    """Run all examples."""
    
    print("Recommendations Generation Examples")
    print("=" * 70)
    
    # Example 1
    print("\n[Example 1: Basic Usage]")
    try:
        await example_basic_usage()
    except Exception as e:
        print(f"Example 1 failed: {e}")
    
    # Example 2
    print("\n[Example 2: With Fallback]")
    try:
        await example_with_fallback()
    except Exception as e:
        print(f"Example 2 failed: {e}")
    
    # Example 4
    print("\n[Example 4: Integration Pattern]")
    try:
        await example_integration_pattern()
    except Exception as e:
        print(f"Example 4 failed: {e}")
    
    # Example 7
    print("\n[Example 7: Error Recovery]")
    try:
        await example_error_recovery()
    except Exception as e:
        print(f"Example 7 failed: {e}")
    
    print("\n" + "=" * 70)
    print("Examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
