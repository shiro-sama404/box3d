import csv

f1 = 'benchmark_results/results_dbvh_arearatio_convex_500.csv'
f2 = 'benchmark_results/results_dbvh_arearatio_final.csv'

with open(f1, 'r', encoding='utf-8') as fp1, open(f2, 'r', encoding='utf-8') as fp2:
    r1 = list(csv.DictReader(fp1))
    r2 = list(csv.DictReader(fp2))

print(f"Total frames: {len(r1)} vs {len(r2)}")
for i in range(15):
    print(f"Frame {i:2d}: old_sah={float(r1[i]['sah_normalized']):.2f}, new_sah={float(r2[i]['sah_normalized']):.2f} | old_h={r1[i]['tree_height']}, new_h={r2[i]['tree_height']} | old_pairs={float(r1[i]['pairs_ms']):.3f}, new_pairs={float(r2[i]['pairs_ms']):.3f}")
