#!/usr/bin/env python3
"""
Standalone test runner for CausalAnalyzer that doesn't require Django.
This allows us to validate the implementation regardless of Django test runner issues.
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, '/Users/Louis-Philippe/Documents/finance_agent')

import pandas as pd
from datetime import timedelta
from decimal import Decimal
from accounting.analysis.causal import CausalAnalyzer, CausalAnalysisResult

def test_criterion_1_basic_acceptance():
    """
    SUCCESS CRITERIA 1: Module accepts transaction DataFrame and returns proper result.
    """
    print("\n" + "="*70)
    print("TEST CRITERION 1: Basic DataFrame Acceptance & Result Type")
    print("="*70)

    analyzer = CausalAnalyzer()
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=24, freq='ME'),
        'amount': [50.0] * 24,
        'merchant_name': ['MerchantA'] * 24,
    })

    result = analyzer.analyze(df)

    # Verify result type and fields
    assert isinstance(result, CausalAnalysisResult), "Result is not CausalAnalysisResult"
    assert isinstance(result.volume_effect_pct, float), "volume_effect_pct is not float"
    assert isinstance(result.price_effect_pct, float), "price_effect_pct is not float"
    assert isinstance(result.mix_shift_detected, bool), "mix_shift_detected is not bool"

    print("✓ Module accepts DataFrame with required columns (date, amount, merchant_name)")
    print("✓ Returns CausalAnalysisResult with proper types")
    print(f"  - volume_effect_pct: {result.volume_effect_pct}%")
    print(f"  - price_effect_pct: {result.price_effect_pct}%")
    print(f"  - mix_shift_detected: {result.mix_shift_detected}")
    return True

def test_criterion_2_price_effect():
    """
    SUCCESS CRITERIA 2: Price Effect Detection
    4 purchases/month at $50 → $60, expects +20% price, 0% volume
    """
    print("\n" + "="*70)
    print("TEST CRITERION 2: Price Effect (+20% from $50 to $60)")
    print("="*70)

    analyzer = CausalAnalyzer()

    # Create P12M: 12 months, 4 transactions each at $50
    p12m_txns = []
    for month in range(12):
        for i in range(4):
            p12m_txns.append({
                'date': pd.Timestamp('2024-01-01') + timedelta(days=month*30 + i*7),
                'amount': 50.0,
                'merchant_name': 'MerchantA'
            })

    # Create L12M: 12 months, 4 transactions each at $60
    l12m_txns = []
    for month in range(12):
        for i in range(4):
            l12m_txns.append({
                'date': pd.Timestamp('2025-01-01') + timedelta(days=month*30 + i*7),
                'amount': 60.0,
                'merchant_name': 'MerchantA'
            })

    df = pd.DataFrame(p12m_txns + l12m_txns)
    result = analyzer.analyze(df, reference_date=pd.Timestamp('2025-12-31'))

    # Check volume: 48 → 48 (0%)
    assert abs(result.volume_effect_pct) < 5, f"Volume effect should be ~0%, got {result.volume_effect_pct}%"

    # Check price: $50 → $60 (+20%)
    assert 15 < result.price_effect_pct < 25, f"Price effect should be ~20%, got {result.price_effect_pct}%"

    # No merchant shift
    assert not result.mix_shift_detected, "Should not detect mix shift"

    print(f"✓ Price Effect Detected: {result.price_effect_pct:.1f}% (expected ~20%)")
    print(f"✓ Volume Effect: {result.volume_effect_pct:.1f}% (expected ~0%)")
    print(f"✓ No mix shift detected: {result.mix_shift_detected}")
    return True

def test_criterion_3_volume_effect():
    """
    SUCCESS CRITERIA 3: Volume Effect Detection
    Ticket stays at $50, frequency goes 4x/month → 6x/month, +50% volume
    """
    print("\n" + "="*70)
    print("TEST CRITERION 3: Volume Effect (+50% from 4 to 6 purchases/month)")
    print("="*70)

    analyzer = CausalAnalyzer()

    # Create P12M: 12 months, 4 transactions each at $50
    p12m_txns = []
    day_counter = 0
    for month in range(12):
        for i in range(4):
            p12m_txns.append({
                'date': pd.Timestamp('2024-01-01') + timedelta(days=day_counter),
                'amount': 50.0,
                'merchant_name': 'MerchantA'
            })
            day_counter += 1

    # Create L12M: 12 months, 6 transactions each at $50
    l12m_txns = []
    day_counter = 0
    for month in range(12):
        for i in range(6):
            l12m_txns.append({
                'date': pd.Timestamp('2025-01-01') + timedelta(days=day_counter),
                'amount': 50.0,
                'merchant_name': 'MerchantA'
            })
            day_counter += 1

    df = pd.DataFrame(p12m_txns + l12m_txns)
    result = analyzer.analyze(df, reference_date=pd.Timestamp('2025-12-31'))

    # Check volume: 48 → 72 (+50%)
    assert 45 < result.volume_effect_pct < 55, f"Volume effect should be ~50%, got {result.volume_effect_pct}%"

    # Check price: $50 → $50 (0%)
    assert abs(result.price_effect_pct) < 5, f"Price effect should be ~0%, got {result.price_effect_pct}%"

    # No merchant shift
    assert not result.mix_shift_detected, "Should not detect mix shift"

    print(f"✓ Volume Effect Detected: {result.volume_effect_pct:.1f}% (expected ~50%)")
    print(f"✓ Price Effect: {result.price_effect_pct:.1f}% (expected ~0%)")
    print(f"✓ No mix shift detected: {result.mix_shift_detected}")
    return True

def test_criterion_4_mix_shift():
    """
    SUCCESS CRITERIA 4: Mix Shift Detection
    User shifts primary spending from Merchant A to Merchant B
    """
    print("\n" + "="*70)
    print("TEST CRITERION 4: Mix Shift Detection (Merchant A → Merchant B)")
    print("="*70)

    analyzer = CausalAnalyzer(mix_shift_threshold_pct=10.0)

    # Create P12M (2024): 90% at MerchantA, 10% at MerchantB (9:1 ratio)
    p12m_txns = []
    day_counter = 0
    for month in range(12):
        for i in range(9):  # 9 at MerchantA
            p12m_txns.append({
                'date': pd.Timestamp('2024-01-01') + timedelta(days=day_counter),
                'amount': 50.0,
                'merchant_name': 'MerchantA'
            })
            day_counter += 1
        p12m_txns.append({  # 1 at MerchantB
            'date': pd.Timestamp('2024-01-01') + timedelta(days=day_counter),
            'amount': 50.0,
            'merchant_name': 'MerchantB'
        })
        day_counter += 1

    # Create L12M (2025): 10% at MerchantA, 90% at MerchantB (flipped)
    l12m_txns = []
    day_counter = 0
    for month in range(12):
        l12m_txns.append({  # 1 at MerchantA
            'date': pd.Timestamp('2025-01-01') + timedelta(days=day_counter),
            'amount': 50.0,
            'merchant_name': 'MerchantA'
        })
        day_counter += 1
        for i in range(9):  # 9 at MerchantB
            l12m_txns.append({
                'date': pd.Timestamp('2025-01-01') + timedelta(days=day_counter),
                'amount': 50.0,
                'merchant_name': 'MerchantB'
            })
            day_counter += 1

    df = pd.DataFrame(p12m_txns + l12m_txns)
    result = analyzer.analyze(df, reference_date=pd.Timestamp('2024-12-31'))

    # Should detect significant mix shift (from 90% to 10% = 80pp change > 10pp threshold)
    assert result.mix_shift_detected, f"Should detect mix shift. P12M: {result.p12m_top_merchant_share}%, L12M: {result.l12m_top_merchant_share}%"

    # Top merchant share should be 90% in both periods
    assert 85 < result.p12m_top_merchant_share < 95, f"P12M top merchant should be ~90%, got {result.p12m_top_merchant_share}%"
    assert 85 < result.l12m_top_merchant_share < 95, f"L12M top merchant should be ~90%, got {result.l12m_top_merchant_share}%"

    print(f"✓ Mix Shift Detected: {result.mix_shift_detected}")
    print(f"  - P12M Top Merchant Share: {result.p12m_top_merchant_share:.1f}%")
    print(f"  - L12M Top Merchant Share: {result.l12m_top_merchant_share:.1f}%")
    print(f"  - Absolute Difference: {abs(result.l12m_top_merchant_share - result.p12m_top_merchant_share):.1f}pp")
    return True

def test_criterion_5_comprehensive():
    """
    SUCCESS CRITERIA 5: Comprehensive pytest coverage
    Includes multiple edge cases and robustness tests
    """
    print("\n" + "="*70)
    print("TEST CRITERION 5: Comprehensive Edge Cases & Robustness")
    print("="*70)

    analyzer = CausalAnalyzer()

    # Test 1: Decimal amounts
    print("  Testing Decimal amount handling...")
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=24, freq='ME'),
        'amount': [Decimal('50.00')] * 24,
        'merchant_name': ['MerchantA'] * 24,
    })
    result = analyzer.analyze(df)
    assert abs(result.l12m_avg_ticket - 50.0) < 1, "Decimal amounts not handled"
    print("    ✓ Decimal amounts handled correctly")

    # Test 2: Varying amount sizes
    print("  Testing varying transaction amounts...")
    amounts = [10.0, 20.0, 100.0, 50.0, 75.0] * 10  # 50 varied transactions
    dates = pd.date_range('2024-06-01', periods=50, freq='D')
    df = pd.DataFrame({
        'date': dates,
        'amount': amounts,
        'merchant_name': ['MerchantA'] * 50,
    })
    result = analyzer.analyze(df)
    avg_amount = sum(amounts) / len(amounts)
    assert abs(result.l12m_avg_ticket - avg_amount) < 5, "Varying amounts not computed correctly"
    print("    ✓ Varying amounts computed correctly")

    # Test 3: Empty DataFrame rejection
    print("  Testing empty DataFrame rejection...")
    try:
        df_empty = pd.DataFrame({'date': [], 'amount': [], 'merchant_name': []})
        analyzer.analyze(df_empty)
        assert False, "Should have raised ValueError for empty DataFrame"
    except ValueError:
        print("    ✓ Empty DataFrame properly rejected")

    # Test 4: Missing columns rejection
    print("  Testing missing columns rejection...")
    try:
        df_missing = pd.DataFrame({'date': [1, 2], 'amount': [10, 20]})
        analyzer.analyze(df_missing)
        assert False, "Should have raised ValueError for missing merchant_name"
    except ValueError:
        print("    ✓ Missing columns properly rejected")

    # Test 5: No mix shift below threshold
    print("  Testing mix shift threshold enforcement...")
    p12m_txns = []
    for month in range(12):
        for i in range(5):
            p12m_txns.append({
                'date': pd.Timestamp('2024-01-01') + timedelta(days=month*30 + i*6),
                'amount': 50.0,
                'merchant_name': 'MerchantA'
            })
        for i in range(5):
            p12m_txns.append({
                'date': pd.Timestamp('2024-01-01') + timedelta(days=month*30 + 30 + i*6),
                'amount': 50.0,
                'merchant_name': 'MerchantB'
            })

    l12m_txns = []
    for month in range(12):
        for i in range(6):
            l12m_txns.append({
                'date': pd.Timestamp('2025-01-01') + timedelta(days=month*30 + i*5),
                'amount': 50.0,
                'merchant_name': 'MerchantA'
            })
        for i in range(4):
            l12m_txns.append({
                'date': pd.Timestamp('2025-01-01') + timedelta(days=month*30 + 30 + i*7),
                'amount': 50.0,
                'merchant_name': 'MerchantB'
            })

    df = pd.DataFrame(p12m_txns + l12m_txns)
    result = analyzer.analyze(df, reference_date=pd.Timestamp('2025-12-31'))
    assert not result.mix_shift_detected, "Should not detect shift below threshold"
    print("    ✓ Mix shift threshold enforced correctly")

    print("\n✓ All comprehensive tests passed!")
    return True

def main():
    """Run all tests and report results"""
    print("\n" + "="*70)
    print("CAUSAL ANALYZER - COMPREHENSIVE TEST SUITE")
    print("="*70)

    tests = [
        ("Criterion 1: Module Acceptance", test_criterion_1_basic_acceptance),
        ("Criterion 2: Price Effect Detection", test_criterion_2_price_effect),
        ("Criterion 3: Volume Effect Detection", test_criterion_3_volume_effect),
        ("Criterion 4: Mix Shift Detection", test_criterion_4_mix_shift),
        ("Criterion 5: Comprehensive Coverage", test_criterion_5_comprehensive),
    ]

    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, "PASS"))
        except Exception as e:
            results.append((name, f"FAIL: {str(e)}"))
            import traceback
            traceback.print_exc()

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for name, status in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")

    passed = sum(1 for _, status in results if status == "PASS")
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")

    return 0 if passed == total else 1

if __name__ == '__main__':
    sys.exit(main())

