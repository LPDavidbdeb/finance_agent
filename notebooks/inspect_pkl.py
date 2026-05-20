import os, json, pandas as pd, datetime
pkl = '/Users/Louis-Philippe/Documents/finance_agent/notebooks/price_series.pkl'
info = {}
if os.path.exists(pkl):
    st = os.stat(pkl)
    info['path'] = pkl
    info['size_bytes'] = st.st_size
    info['modified_at'] = datetime.datetime.fromtimestamp(st.st_mtime).isoformat()
    try:
        df = pd.read_pickle(pkl)
        info['columns'] = list(df.columns)
        info['index_start'] = str(df.index.min())
        info['index_end'] = str(df.index.max())
        info['n_rows'] = int(len(df))
    except Exception as e:
        info['error'] = str(e)
else:
    info['error'] = 'file not found'
print(json.dumps(info, indent=2))
