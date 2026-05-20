import os, json, pandas as pd, datetime

pkl = '/Users/Louis-Philippe/Documents/finance_agent/notebooks/price_series.pkl'
js = '/Users/Louis-Philippe/Documents/finance_agent/notebooks/sim_results.json'
info = {}

if os.path.exists(pkl):
    st = os.stat(pkl)
    info['pickle_path'] = pkl
    info['size_bytes'] = st.st_size
    info['modified_at'] = datetime.datetime.fromtimestamp(st.st_mtime).isoformat()
    try:
        df = pd.read_pickle(pkl)
        info['columns'] = list(df.columns)
        info['index_start'] = str(df.index.min())
        info['index_end'] = str(df.index.max())
        info['n_rows'] = int(len(df))
        
        # Convert index to string to avoid Timestamp key error in json.dumps
        df_head = df.head(3).copy()
        df_head.index = df_head.index.astype(str)
        info['sample_head'] = df_head.to_dict()
        
        df_tail = df.tail(3).copy()
        df_tail.index = df_tail.index.astype(str)
        info['sample_tail'] = df_tail.to_dict()
        
    except Exception as e:
        info['pickle_error'] = str(e)
else:
    info['pickle_exists'] = False

if os.path.exists(js):
    with open(js,'r') as f:
        data = json.load(f)
    info['sim_results_source'] = data.get('source')
    info['sim_results_use_synthetic'] = data.get('use_synthetic')
    info['sim_weights'] = data.get('weights')
else:
    info['sim_results_exists'] = False

print(json.dumps(info, indent=2, default=str))
