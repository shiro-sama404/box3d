import csv

files = [
    ('Native (Box3D)', 'benchmark_results/results_native_final.csv'),
    ('DBVH (Area Ratio)', 'benchmark_results/results_dbvh_arearatio_final.csv'),
    ('DBVH (Subtree SAH)', 'benchmark_results/results_dbvh_subtreesah_final.csv'),
]

for name, path in files:
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    def mean(col):
        vals = [float(r[col]) for r in rows if col in r and r[col] != '']
        return sum(vals) / len(vals) if vals else 0.0

    print(f"=== {name} ===")
    print(f"Step Medio:    {mean('step_ms'):.4f} ms")
    print(f"Pairs Medio:   {mean('pairs_ms'):.4f} ms")
    print(f"Collide Medio: {mean('collide_ms'):.4f} ms")
    print(f"Solve Medio:   {mean('solve_ms'):.4f} ms")
    print(f"Altura Media:  {mean('tree_height'):.2f} (Final: {rows[-1].get('tree_height', 'N/A')})")
    if 'quality_ratio_normalized' in rows[0]:
        print(f"Q_norm Medio:  {mean('quality_ratio_normalized'):.4f} (Final: {float(rows[-1]['quality_ratio_normalized']):.4f})")
    print()
