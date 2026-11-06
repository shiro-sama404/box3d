#!/usr/bin/env python3
"""
tools/run_retest_10k_spinner_junkyard.py
Re-runs the 10,000 bodies benchmarks for:
- spinner (400 steps, SDBVH)
- junkyard (1500 steps, SDBVH)
- junkyard (1500 steps, Native Box3D)
Following the adaptive controller fix and the Dual-Tree SA-guided descent optimization.
"""

import os
import sys
import time
import csv
import subprocess

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

EXE_PATH = os.path.join("build", "bin", "benchmark.exe")
OUT_DIR = os.path.join("benchmark_results", "final_10k_100k")
os.makedirs(OUT_DIR, exist_ok=True)

RUNS = [
    {
        "scene": "spinner",
        "name": "Spinner",
        "bp": "sdbvh",
        "steps": 400,
        "actors": 10000,
        "csv_name": "retest_spinner_10000_sdbvh.csv"
    },
    {
        "scene": "junkyard",
        "name": "Junkyard",
        "bp": "sdbvh",
        "steps": 1500,
        "actors": 10000,
        "csv_name": "retest_junkyard_10000_sdbvh.csv"
    },
    {
        "scene": "junkyard",
        "name": "Junkyard",
        "bp": "native",
        "steps": 1500,
        "actors": 10000,
        "csv_name": "retest_junkyard_10000_native.csv"
    }
]

def parse_csv(csv_path):
    if not os.path.exists(csv_path):
        return None
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    if not rows:
        return None

    def get_list(col):
        return [float(r[col]) for r in rows if col in r and r[col] != ""]

    def avg(lst):
        return sum(lst) / len(lst) if lst else 0.0

    return {
        "step_ms_avg": avg(get_list("step_ms")),
        "pairs_ms_avg": avg(get_list("pairs_ms")),
        "collide_ms_avg": avg(get_list("collide_ms")),
        "solve_ms_avg": avg(get_list("solve_ms")),
        "contacts_avg": avg(get_list("contact_count")),
        "height_max": max([int(r["tree_height"]) for r in rows if "tree_height" in r]) if get_list("tree_height") else 0,
        "height_avg": avg(get_list("tree_height")),
        "count": len(rows)
    }

def main():
    print("=" * 80)
    print("  RE-TEST 10,000 BODIES: SPINNER (400 steps) & JUNKYARD (1500 steps)")
    print("  Target: SDBVH with SA-descent & fixed adaptive controller vs Native")
    print("=" * 80 + "\n")

    summary = []

    for idx, run_cfg in enumerate(RUNS, 1):
        scene = run_cfg["scene"]
        name = run_cfg["name"]
        bp = run_cfg["bp"]
        steps = run_cfg["steps"]
        actors = run_cfg["actors"]
        csv_path = os.path.join(OUT_DIR, run_cfg["csv_name"])

        print(f"[{idx}/{len(RUNS)}] Starting {name} ({scene}) | BP: {bp.upper()} | Steps: {steps} | Actors: {actors}", flush=True)
        print(f"      Output: {csv_path}", flush=True)

        cmd = [
            EXE_PATH,
            f"-b={scene}",
            f"-a={actors}",
            f"--steps={steps}",
            "-r=1",
            "-w=1",
            f"-bp={bp}",
            "-c",
            f"--output-csv={csv_path}"
        ]

        t0 = time.time()
        proc = subprocess.run(cmd)
        elapsed = time.time() - t0

        if proc.returncode != 0:
            print(f"  [ERROR] Exit code {proc.returncode}", flush=True)
            continue

        metrics = parse_csv(csv_path)
        if metrics:
            print(f"  [DONE] Elapsed: {elapsed:.1f}s ({elapsed/60.0:.2f} min)", flush=True)
            print(f"         Pairs: {metrics['pairs_ms_avg']:.2f} ms | Collide: {metrics['collide_ms_avg']:.2f} ms | Solve: {metrics['solve_ms_avg']:.2f} ms | Step: {metrics['step_ms_avg']:.2f} ms", flush=True)
            print(f"         Max Height: {metrics['height_max']} | Contacts Avg: {metrics['contacts_avg']:.1f}", flush=True)
            summary.append({
                "scene": scene,
                "bp": bp,
                "steps": steps,
                "actors": actors,
                "elapsed_s": elapsed,
                **metrics
            })
        print("-" * 80, flush=True)

    print("\n" + "=" * 80)
    print("  EXECUTION COMPLETE - SUMMARY")
    print("=" * 80)
    for s in summary:
        print(f"{s['scene']:<12} | {s['bp']:<6} | Steps: {s['steps']} | Pairs: {s['pairs_ms_avg']:.2f} ms | Collide: {s['collide_ms_avg']:.2f} ms | Step: {s['step_ms_avg']:.2f} ms | H_max: {s['height_max']}")

if __name__ == "__main__":
    main()
