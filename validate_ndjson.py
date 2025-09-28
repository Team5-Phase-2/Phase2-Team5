# python3 validate_ndjson.py < output.txt
import json, sys
ok = True
for i, line in enumerate(sys.stdin, 1):
    line = line.rstrip('\n')
    if not line:
        print(f'Line {i}: blank line in NDJSON', file=sys.stderr); ok=False; continue
    try:
        obj = json.loads(line)
    except Exception as e:
        print(f'Line {i}: not valid JSON: {e}', file=sys.stderr); ok=False; continue

    # Minimal schema sanity (expand as needed)
    req_float = ['net_score','ramp_up_time','bus_factor','performance_claims',
                 'license','dataset_and_code_score','dataset_quality','code_quality']
    req_int   = ['net_score_latency','ramp_up_time_latency','bus_factor_latency',
                 'performance_claims_latency','license_latency','size_score_latency',
                 'dataset_and_code_score_latency','dataset_quality_latency','code_quality_latency']
    req_other = ['name','category','size_score']

    for k in req_float:
        if not isinstance(obj.get(k), (int,float)):
            print(f'Line {i}: {k} must be number', file=sys.stderr); ok=False
    for k in req_int:
        if not isinstance(obj.get(k), int):
            print(f'Line {i}: {k} must be int ms', file=sys.stderr); ok=False
    if obj.get('category') not in ('MODEL','DATASET','CODE'):
        print(f"Line {i}: category invalid", file=sys.stderr); ok=False
    if not isinstance(obj.get('size_score'), dict):
        print(f"Line {i}: size_score must be object", file=sys.stderr); ok=False
print('OK' if ok else 'FAIL')
