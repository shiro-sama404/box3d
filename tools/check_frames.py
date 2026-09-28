import csv

for f in ['benchmark_results/results_native_final.csv',
          'benchmark_results/results_dbvh_arearatio_final.csv',
          'benchmark_results/results_dbvh_arearatio_convex_500.csv',
          'benchmark_results/results_dbvh_arearatio_opt_500.csv']:
    try:
        with open(f, 'r', encoding='utf-8') as fp:
            rows = list(csv.DictReader(fp))
            print(f'=== {f} ===')
            for i in [0, 1, 2, 5, 10, 20, 29, 30, 31]:
                if i < len(rows):
                    r = rows[i]
                    frame = r.get('frame')
                    sah_norm = float(r.get('sah_normalized', 0))
                    ideal = float(r.get('ideal_sah_normalized', 0))
                    q_norm = float(r.get('quality_ratio_normalized', 0))
                    height = r.get('tree_height')
                    print(f"Frame {frame:2s}: sah_norm={sah_norm:6.2f}, ideal={ideal:6.2f}, q_norm={q_norm:6.4f}, height={height}")
            print()
    except Exception as e:
        print(f, e)
