#!/usr/bin/env python3
"""
tools/run_scale_sweep.py
Unified Automated Scale Sweep Benchmark Suite for Box3D & SDBVH.

Supports:
  - Single-thread execution (-w 1) and Multithread execution (-w 8, etc.)
  - 5 canonical scenes: convex_pile, ragdoll_pile, junkyard, spinner, many_pyramids
  - Geometric scaling: 64 to 1024 bodies (60 to 1020 for ragdoll_pile)
  - Configurable repeats (default 5) and calibrated steps per scene
  - Full metrics: broadphase pairs_ms, step_ms, collide_ms, solve_ms, height, SAH, parity
  - Automated CSV metrics summary and multi-scale aggregation
"""

import os
import sys
import csv
import time
import argparse
import subprocess
import statistics
from datetime import datetime

# UTF-8 console setup for Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DEFAULT_SCENES = ["convex_pile", "ragdoll_pile", "junkyard", "spinner", "many_pyramids"]
STANDARD_SIZES = [64, 128, 256, 512, 1024]
RAGDOLL_SIZES  = [60, 120, 252, 504, 1020]

SCENE_STEPS = {
    "convex_pile": 1000,
    "many_pyramids": 100,
    "spinner": 400,
    "junkyard": 1500,
    "ragdoll_pile": 400,
}

BROADPHASES = ["native", "sdbvh"]

def mean_or_zero(lst):
    return statistics.mean(lst) if lst else 0.0

def stdev_or_zero(lst):
    return statistics.stdev(lst) if len(lst) > 1 else 0.0

def find_executable():
    candidates = [
        os.path.join("build", "bin", "benchmark.exe"),
        os.path.join("build", "bin", "benchmark"),
        os.path.join("bin", "benchmark.exe"),
        os.path.join("bin", "benchmark")
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def parse_args():
    parser = argparse.ArgumentParser(description="Unified Scale Sweep Benchmark Suite (Box3D vs SDBVH)")
    parser.add_argument("-w", "--workers", default="1",
                        help="Thread/worker count (e.g. '1', '8', or '1,8' for both). Default: 1")
    parser.add_argument("-r", "--repeats", type=int, default=5,
                        help="Number of repeats per test configuration. Default: 5")
    parser.add_argument("-s", "--scenes", default=",".join(DEFAULT_SCENES),
                        help="Comma-separated list of scenes. Default: all 5 scenes")
    parser.add_argument("-o", "--output-dir", default=None,
                        help="Output directory. Default: benchmark_results/<date>/results")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print test configurations without running the benchmark executable")
    return parser.parse_args()

def run_suite_for_workers(exe_path, workers, scenes, repeats, out_dir, dry_run=False):
    is_multi = (workers > 1)
    worker_label = f"{workers}T"
    tag = "multithread" if is_multi else "monothread"
    summary_filename = f"summary_scale_{tag}.csv"
    detailed_filename = f"detailed_scale_{tag}.csv"

    summary_csv = os.path.join(out_dir, summary_filename)
    detailed_csv = os.path.join(out_dir, detailed_filename)
    temp_csv = os.path.join(out_dir, f"_temp_sweep_{workers}w")

    print("\n" + "=" * 80)
    print(f"STARTING SCALE SWEEP ({workers} WORKER{'S' if is_multi else ''})")
    print(f"Scenes:  {scenes}")
    print(f"Repeats: {repeats} per configuration")
    print(f"Output:  {summary_csv}")
    print("=" * 80 + "\n", flush=True)

    summary_rows = []
    detailed_rows = []
    start_time = time.time()
    total_configs = len(scenes) * 5 * 2 * repeats
    current_run = 0

    for scene in scenes:
        sizes = RAGDOLL_SIZES if scene == "ragdoll_pile" else STANDARD_SIZES
        steps = SCENE_STEPS.get(scene, 500)

        for n in sizes:
            print(f">>> Scene: {scene:<13s} | N: {n:4d} | Steps: {steps:4d} | Workers: {workers}", flush=True)
            bp_stats = {}

            for bp in BROADPHASES:
                run_pairs = []
                run_steps = []
                run_collides = []
                run_solves = []
                run_contacts = []
                run_heights = []
                run_sahs = []

                for r in range(1, repeats + 1):
                    current_run += 1
                    pct = (current_run / total_configs) * 100.0

                    if dry_run:
                        print(f"  [{pct:5.1f}%] (DRY-RUN) {scene} N={n} {bp} w={workers} r={r}")
                        continue

                    cmd = [
                        exe_path,
                        f"-b={scene}",
                        f"-a={n}",
                        f"--steps={steps}",
                        f"-w={workers}",
                        "-r=1",
                        f"-bp={bp}",
                        "-c",
                        f"-o={temp_csv}"
                    ]

                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if res.returncode != 0:
                        print(f"\n[ERROR] Command failed (exit {res.returncode}): {' '.join(cmd)}")
                        print(res.stderr)
                        continue

                    csv_file = temp_csv if os.path.exists(temp_csv) else temp_csv + ".csv"
                    if not os.path.exists(csv_file):
                        candidates = [
                            os.path.join("benchmark_results", temp_csv),
                            os.path.join("benchmark_results", temp_csv + ".csv"),
                            os.path.join(out_dir, os.path.basename(temp_csv)),
                            os.path.join(out_dir, os.path.basename(temp_csv) + ".csv")
                        ]
                        for c in candidates:
                            if os.path.exists(c):
                                csv_file = c
                                break

                    pair_vals = []
                    step_vals = []
                    collide_vals = []
                    solve_vals = []
                    contact_vals = []
                    sah_vals = []
                    height_val = 0

                    if os.path.exists(csv_file):
                        with open(csv_file, mode="r", encoding="utf-8") as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                if "pairs_ms" in row and row["pairs_ms"]:
                                    pair_vals.append(float(row["pairs_ms"]))
                                if "step_ms" in row and row["step_ms"]:
                                    step_vals.append(float(row["step_ms"]))
                                if "collide_ms" in row and row["collide_ms"]:
                                    collide_vals.append(float(row["collide_ms"]))
                                if "solve_ms" in row and row["solve_ms"]:
                                    solve_vals.append(float(row["solve_ms"]))
                                if "contacts" in row and row["contacts"]:
                                    contact_vals.append(float(row["contacts"]))
                                if "tree_height" in row and row["tree_height"]:
                                    height_val = int(row["tree_height"])
                                if "sah_normalized" in row and row["sah_normalized"]:
                                    sah_vals.append(float(row["sah_normalized"]))
                        try:
                            os.remove(csv_file)
                        except OSError:
                            pass

                    m_pair = mean_or_zero(pair_vals)
                    m_step = mean_or_zero(step_vals)
                    m_collide = mean_or_zero(collide_vals)
                    m_solve = mean_or_zero(solve_vals)
                    m_contact = mean_or_zero(contact_vals)
                    m_sah = mean_or_zero(sah_vals)

                    run_pairs.append(m_pair)
                    run_steps.append(m_step)
                    run_collides.append(m_collide)
                    run_solves.append(m_solve)
                    run_contacts.append(m_contact)
                    run_heights.append(height_val)
                    run_sahs.append(m_sah)

                    detailed_rows.append({
                        "scene": scene,
                        "n": n,
                        "steps": steps,
                        "workers": workers,
                        "broadphase": bp,
                        "repeat": r,
                        "pairs_ms": m_pair,
                        "step_ms": m_step,
                        "collide_ms": m_collide,
                        "solve_ms": m_solve,
                        "contacts": m_contact,
                        "tree_height": height_val,
                        "sah_normalized": m_sah
                    })

                if not dry_run:
                    bp_stats[bp] = {
                        "pairs_mean": mean_or_zero(run_pairs),
                        "pairs_std": stdev_or_zero(run_pairs),
                        "step_mean": mean_or_zero(run_steps),
                        "step_std": stdev_or_zero(run_steps),
                        "collide_mean": mean_or_zero(run_collides),
                        "collide_std": stdev_or_zero(run_collides),
                        "solve_mean": mean_or_zero(run_solves),
                        "solve_std": stdev_or_zero(run_solves),
                        "contacts_mean": mean_or_zero(run_contacts),
                        "height_final": run_heights[-1] if run_heights else 0,
                        "sah_mean": mean_or_zero(run_sahs)
                    }

                    print(f"    {bp.upper():6s} -> Pairs: {bp_stats[bp]['pairs_mean']:7.4f} +/- {bp_stats[bp]['pairs_std']:6.4f} ms | "
                          f"Step: {bp_stats[bp]['step_mean']:7.3f} +/- {bp_stats[bp]['step_std']:6.3f} ms | "
                          f"Height: {bp_stats[bp]['height_final']:2d} | SA: {bp_stats[bp]['sah_mean']:5.2f}", flush=True)

            if not dry_run and "native" in bp_stats and "sdbvh" in bp_stats:
                nat = bp_stats["native"]
                sdb = bp_stats["sdbvh"]

                speedup_pairs = (nat["pairs_mean"] / sdb["pairs_mean"]) if sdb["pairs_mean"] > 0 else 0.0
                speedup_step = (nat["step_mean"] / sdb["step_mean"]) if sdb["step_mean"] > 0 else 0.0
                contact_parity = (sdb["contacts_mean"] / nat["contacts_mean"]) if nat["contacts_mean"] > 0 else 1.0

                print(f"    ==> SPEEDUP BROAD: {speedup_pairs:6.2f}x | SPEEDUP STEP: {speedup_step:6.2f}x | "
                      f"PARITY: {contact_parity*100:6.2f}% | HEIGHT: {nat['height_final']} vs {sdb['height_final']} | "
                      f"SA: {nat['sah_mean']:5.2f} vs {sdb['sah_mean']:5.2f}\n", flush=True)

                summary_rows.append({
                    "scene": scene,
                    "n": n,
                    "steps": steps,
                    "workers": workers,
                    "native_pairs_ms": round(nat["pairs_mean"], 4),
                    "native_pairs_std": round(nat["pairs_std"], 4),
                    "sdbvh_pairs_ms": round(sdb["pairs_mean"], 4),
                    "sdbvh_pairs_std": round(sdb["pairs_std"], 4),
                    "speedup_broadphase": round(speedup_pairs, 2),
                    "native_collide_ms": round(nat["collide_mean"], 4),
                    "native_collide_std": round(nat["collide_std"], 4),
                    "sdbvh_collide_ms": round(sdb["collide_mean"], 4),
                    "sdbvh_collide_std": round(sdb["collide_std"], 4),
                    "native_solve_ms": round(nat["solve_mean"], 4),
                    "native_solve_std": round(nat["solve_std"], 4),
                    "sdbvh_solve_ms": round(sdb["solve_mean"], 4),
                    "sdbvh_solve_std": round(sdb["solve_std"], 4),
                    "native_step_ms": round(nat["step_mean"], 3),
                    "native_step_std": round(nat["step_std"], 3),
                    "sdbvh_step_ms": round(sdb["step_mean"], 3),
                    "sdbvh_step_std": round(sdb["step_std"], 3),
                    "speedup_step": round(speedup_step, 2),
                    "native_height": nat["height_final"],
                    "sdbvh_height": sdb["height_final"],
                    "native_sah": round(nat["sah_mean"], 2),
                    "sdbvh_sah": round(sdb["sah_mean"], 2),
                    "native_contacts": round(nat["contacts_mean"], 1),
                    "sdbvh_contacts": round(sdb["contacts_mean"], 1),
                    "contact_parity": round(contact_parity, 4)
                })

                with open(summary_csv, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(summary_rows)

                with open(detailed_csv, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=detailed_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(detailed_rows)

    if not dry_run:
        elapsed = time.time() - start_time
        print("=" * 80)
        print(f"SCALE SWEEP ({workers}W) COMPLETED in {elapsed / 60:.1f} minutes!")
        print(f"Summary written to: {summary_csv}")
        print(f"Detailed written to: {detailed_csv}")
        print("=" * 80 + "\n", flush=True)

def main():
    args = parse_args()

    exe_path = find_executable()
    if not exe_path and not args.dry_run:
        print("[ERROR] Benchmark executable not found in build/bin or bin. Build the project first.")
        sys.exit(1)

    today_str = datetime.now().strftime("%d-%m-%Y")
    out_dir = args.output_dir or os.path.join("benchmark_results", today_str, "results")
    os.makedirs(out_dir, exist_ok=True)

    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]

    # Parse worker options
    if "," in args.workers:
        worker_list = [int(w.strip()) for w in args.workers.split(",") if w.strip()]
    elif args.workers.lower() == "both":
        worker_list = [1, 8]
    else:
        worker_list = [int(args.workers)]

    for w in worker_list:
        run_suite_for_workers(exe_path, w, scenes, args.repeats, out_dir, args.dry_run)

if __name__ == "__main__":
    main()
