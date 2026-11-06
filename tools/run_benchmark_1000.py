#!/usr/bin/env python3
"""
tools/run_benchmark_1000.py
Runs the 5 canonical benchmark scenes with 1000 objects:
- convex_pile (1000 steps)
- spinner (400 steps)
- ragdoll_pile (400 steps)
- many_pyramids (100 steps)
- junkyard (1500 steps)

Compares Native Box3D (b3DynamicTree) vs SDBVH with closed-loop adaptive controller.
Executes sequentially to avoid CPU cache/thread contention.
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
OUTPUT_DIR = os.path.join("benchmark_results", "2026-11-05_canonical_suite_1000")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SCENES = [
    {"id": "convex_pile", "name": "Convex Pile", "steps": 1000},
    {"id": "many_pyramids", "name": "Many Pyramids", "steps": 100},
    {"id": "spinner", "name": "Spinner", "steps": 400},
    {"id": "junkyard", "name": "Junkyard", "steps": 1500},
    {"id": "ragdoll_pile", "name": "Ragdoll Pile", "steps": 400}
]

ACTORS = 1000
WORKERS = 1

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
        "height_avg": avg(get_list("tree_height")),
        "sah_norm_avg": avg(get_list("sah_normalized"))
    }

def run_cmd(cmd):
    t0 = time.time()
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"Error (code {res.returncode}): {res.stderr or res.stdout}")
        return False, elapsed
    return True, elapsed

def main():
    print(f"================================================================================")
    print(f"  BENCHMARK SUITE: 5 SCENES @ 1000 OBJECTS (ADAPTIVE STEP RUNS, {WORKERS} WORKER)")
    print(f"  Comparing: Native Box3D vs SDBVH (Closed-Loop Adaptive)")
    print(f"================================================================================\n")

    results = []

    for scene in SCENES:
        sid = scene["id"]
        sname = scene["name"]
        steps = scene["steps"]
        print(f"--> Scene: {sname} ({sid}) | Steps: {steps}")

        csv_native = os.path.join(OUTPUT_DIR, f"bench1000_{sid}_native.csv")
        csv_sdbvh = os.path.join(OUTPUT_DIR, f"bench1000_{sid}_sdbvh.csv")

        cmd_native = [
            EXE_PATH,
            f"-b={sid}",
            f"-a={ACTORS}",
            f"--steps={steps}",
            "-r=1",
            f"-w={WORKERS}",
            "-bp=native",
            "-c",
            f"--output-csv={csv_native}"
        ]

        cmd_sdbvh = [
            EXE_PATH,
            f"-b={sid}",
            f"-a={ACTORS}",
            f"--steps={steps}",
            "-r=1",
            f"-w={WORKERS}",
            "-bp=sdbvh",
            "-c",
            "-m=area_ratio",
            "--threshold=1.80",
            "--fattening=off",
            "--predictive=off",
            "--rotations=off",
            "--adaptive=on",
            "--max-subtree-leaves=1024",
            f"--output-csv={csv_sdbvh}"
        ]

        # 1. Run Native
        print(f"    [1/2] Running Native...", end="", flush=True)
        ok_nat, time_nat = run_cmd(cmd_native)
        if ok_nat:
            print(f" Done ({time_nat:.1f}s)")
        else:
            print(f" Failed!")

        # 2. Run SDBVH
        print(f"    [2/2] Running SDBVH...", end="", flush=True)
        ok_sdbvh, time_sdbvh = run_cmd(cmd_sdbvh)
        if ok_sdbvh:
            print(f" Done ({time_sdbvh:.1f}s)")
        else:
            print(f" Failed!")

        d_nat = parse_csv(csv_native)
        d_sdbvh = parse_csv(csv_sdbvh)

        if d_nat and d_sdbvh:
            bp_speedup = d_nat["pairs_ms_avg"] / d_sdbvh["pairs_ms_avg"] if d_sdbvh["pairs_ms_avg"] > 0 else 1.0
            step_speedup = d_nat["step_ms_avg"] / d_sdbvh["step_ms_avg"] if d_sdbvh["step_ms_avg"] > 0 else 1.0

            row = {
                "scene": sname,
                "steps": steps,
                "nat_pairs": round(d_nat["pairs_ms_avg"], 4),
                "sdbvh_pairs": round(d_sdbvh["pairs_ms_avg"], 4),
                "bp_speedup": round(bp_speedup, 2),
                "nat_collide": round(d_nat["collide_ms_avg"], 3),
                "sdbvh_collide": round(d_sdbvh["collide_ms_avg"], 3),
                "nat_solve": round(d_nat["solve_ms_avg"], 3),
                "sdbvh_solve": round(d_sdbvh["solve_ms_avg"], 3),
                "nat_step": round(d_nat["step_ms_avg"], 3),
                "sdbvh_step": round(d_sdbvh["step_ms_avg"], 3),
                "step_speedup": round(step_speedup, 2),
                "nat_h": round(d_nat["height_avg"], 1),
                "sdbvh_h": round(d_sdbvh["height_avg"], 1),
                "nat_sah": round(d_nat["sah_norm_avg"], 2),
                "sdbvh_sah": round(d_sdbvh["sah_norm_avg"], 2),
                "nat_contacts": round(d_nat["contacts_avg"], 1),
                "sdbvh_contacts": round(d_sdbvh["contacts_avg"], 1),
            }
            results.append(row)

            print(f"    Results for {sname} ({steps} steps):")
            print(f"      - BroadPhase (pairs_ms): Native = {row['nat_pairs']:.3f} ms | SDBVH = {row['sdbvh_pairs']:.3f} ms (Speedup: {row['bp_speedup']:.2f}x)")
            print(f"      - Collide    (collide_ms):Native = {row['nat_collide']:.3f} ms | SDBVH = {row['sdbvh_collide']:.3f} ms")
            print(f"      - Solver     (solve_ms):  Native = {row['nat_solve']:.3f} ms | SDBVH = {row['sdbvh_solve']:.3f} ms")
            print(f"      - Step Time  (step_ms):   Native = {row['nat_step']:.3f} ms | SDBVH = {row['sdbvh_step']:.3f} ms (Speedup: {row['step_speedup']:.2f}x)")
            print(f"      - Tree Height:            Native = {row['nat_h']:.1f} | SDBVH = {row['sdbvh_h']:.1f}")
            print(f"      - SAH Norm:               Native = {row['nat_sah']:.2f} | SDBVH = {row['sdbvh_sah']:.2f}")
            print(f"      - Contacts Avg:           Native = {row['nat_contacts']:.1f} | SDBVH = {row['sdbvh_contacts']:.1f}\n")
        else:
            print(f"    Failed to collect data for {sname}\n")

    # Final Summary Table
    print(f"==========================================================================================================")
    print(f"  FINAL SUMMARY (1000 OBJECTS, CALIBRATED STEPS)")
    print(f"==========================================================================================================")
    header = f"{'Scene':<15} | {'Steps':>5} | {'Pairs Nat':>9} | {'Pairs SD':>8} | {'BP Spd':>6} | {'Step Nat':>8} | {'Step SD':>7} | {'Step Spd':>8} | {'H Nat':>5} | {'H SD':>4} | {'SAH Nat':>7} | {'SAH SD':>6}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['scene']:<15} | {r['steps']:>5} | {r['nat_pairs']:>8.3f}m | {r['sdbvh_pairs']:>7.3f}m | {r['bp_speedup']:>5.2f}x | {r['nat_step']:>7.2f}m | {r['sdbvh_step']:>6.2f}m | {r['step_speedup']:>7.2f}x | {r['nat_h']:>5.1f} | {r['sdbvh_h']:>4.1f} | {r['nat_sah']:>7.2f} | {r['sdbvh_sah']:>6.2f}")
    print(f"==========================================================================================================")

    # Save summary CSV
    summary_path = os.path.join(OUTPUT_DIR, "summary_1000_objects_5scenes.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"\nSummary CSV saved to: {summary_path}")

if __name__ == "__main__":
    main()
