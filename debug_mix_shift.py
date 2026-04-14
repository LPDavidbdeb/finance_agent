import pandas as pd
from datetime import timedelta
from accounting.analysis.causal import CausalAnalyzer

# Create P12M: 90% at MerchantA, 10% at MerchantB (9:1 ratio)
p12m_txns = []
day_counter = 0
for month in range(12):
    # 9 purchases at MerchantA (90%)
    for i in range(9):
        p12m_txns.append({
            'date': pd.Timestamp('2024-01-01') + timedelta(days=day_counter),
            'amount': 50.0,
            'merchant_name': 'MerchantA'
        })
        day_counter += 1
    # 1 purchase at MerchantB (10%)
    p12m_txns.append({
        'date': pd.Timestamp('2024-01-01') + timedelta(days=day_counter),
        'amount': 50.0,
        'merchant_name': 'MerchantB'
    })
    day_counter += 1

# Create L12M: 10% at MerchantA, 90% at MerchantB (flipped)
l12m_txns = []
day_counter = 0
for month in range(12):
    # 1 purchase at MerchantA (10%)
    l12m_txns.append({
        'date': pd.Timestamp('2025-01-01') + timedelta(days=day_counter),
        'amount': 50.0,
        'merchant_name': 'MerchantA'
    })
    day_counter += 1
    # 9 purchases at MerchantB (90%)
    for i in range(9):
        l12m_txns.append({
            'date': pd.Timestamp('2025-01-01') + timedelta(days=day_counter),
            'amount': 50.0,
            'merchant_name': 'MerchantB'
        })
        day_counter += 1

df = pd.DataFrame(p12m_txns + l12m_txns)
print('Date range:', df['date'].min(), 'to', df['date'].max())
print('Total transactions:', len(df))
print('P12M transactions:', len(df[df['date'].dt.year == 2024]))
print('L12M transactions:', len(df[df['date'].dt.year == 2025]))

# Now test what the analyzer does
reference_date = pd.Timestamp('2025-12-31')
l12m_end = reference_date
l12m_start = l12m_end - pd.DateOffset(months=12)
p12m_end = l12m_start - pd.DateOffset(days=1)
p12m_start = p12m_end - pd.DateOffset(months=12)

print('\nWindow calculation:')
print('L12M window:', l12m_start, 'to', l12m_end)
print('P12M window:', p12m_start, 'to', p12m_end)

l12m_df = df[(df['date'] >= l12m_start) & (df['date'] <= l12m_end)]
p12m_df = df[(df['date'] >= p12m_start) & (df['date'] <= p12m_end)]

print('\nFiltered data:')
print('L12M filtered txns:', len(l12m_df))
print('P12M filtered txns:', len(p12m_df))

if len(l12m_df) > 0:
    print('\nL12M merchant split:')
    print(l12m_df.groupby('merchant_name')['amount'].sum())
    merchant_totals = l12m_df.groupby('merchant_name')['amount'].sum()
    top = merchant_totals.max()
    total = merchant_totals.sum()
    print(f'Top merchant share: {top/total*100:.1f}%')

if len(p12m_df) > 0:
    print('\nP12M merchant split:')
    print(p12m_df.groupby('merchant_name')['amount'].sum())
    merchant_totals = p12m_df.groupby('merchant_name')['amount'].sum()
    top = merchant_totals.max()
    total = merchant_totals.sum()
    print(f'Top merchant share: {top/total*100:.1f}%')

# Now run actual analyzer
analyzer = CausalAnalyzer(mix_shift_threshold_pct=10.0)
result = analyzer.analyze(df, reference_date=reference_date)

print('\n=== ANALYSIS RESULT ===')
print('P12M top merchant share:', result.p12m_top_merchant_share)
print('L12M top merchant share:', result.l12m_top_merchant_share)
print('Difference:', abs(result.l12m_top_merchant_share - result.p12m_top_merchant_share))
print('Mix shift detected:', result.mix_shift_detected)

