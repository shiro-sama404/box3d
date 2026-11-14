#!/usr/bin/env python3
"""
tools/run_benchmarks.py
Runner and analysis tool for Box3D and SDBVH benchmarks.

Features:
  - Set test parameters: scenes, actors, steps, repeats, workers, and broadphase types.
  - Set SDBVH options: threshold, metric, partition, fattening, prediction, and rotations.
  - Run standard test suites: canonical-1000, scale-sweep, stress-10k, and stress-100k.
  - Save test data to CSV files.
  - Calculate summary values, variance, and comparison tables.
  - Read one CSV file with --analyze.
  - Compare two CSV files side by side with --compare.

Usage examples:
  python tools/run_benchmarks.py --preset canonical-1000
  python tools/run_benchmarks.py -s convex_pile,spinner -a 1000 -r 3 --threshold 1.5
  python tools/run_benchmarks.py --preset scale-sweep
  python tools/run_benchmarks.py --analyze benchmark_results/test.csv
  python tools/run_benchmarks.py --compare run_native.csv run_sdbvh.csv
"""

import os
import sys
import time
import csv
import math
import argparse
import subprocess
import statistics
from datetime import datetime

# Set UTF-8 encoding on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Default benchmark scenes
CANONICAL_SCENES = [
    "convex_pile",
    "many_pyramids",
    "spinner",
    "junkyard",
    "ragdoll_pile"
]

# Default step count for each scene
CALIBRATED_STEPS = {
    "convex_pile": 1000,
    "many_pyramids": 100,
    "spinner": 400,
    "spinner2": 400,
    "junkyard": 1500,
    "ragdoll_pile": 400
}

# Actor counts for the scale sweep suite
DEFAULT_SCALE_SWEEP_ACTORS = [64, 128, 256, 512, 1024]


def find_executable(custom_path=None):
    """Find the benchmark executable on the file system."""
    candidates = []
    if custom_path:
        candidates.append(custom_path)
    candidates.extend([
        os.path.join("build", "bin", "benchmark.exe"),
        os.path.join("build", "bin", "benchmark"),
        os.path.join("build", "Release", "bin", "benchmark.exe"),
        os.path.join("build", "Release", "bin", "benchmark"),
    ])
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def parse_csv(csv_path):
    """Read a CSV file and calculate average values."""
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
        return statistics.mean(lst) if lst else 0.0

    def std(lst):
        return statistics.stdev(lst) if len(lst) > 1 else 0.0

    step_times = get_list("step_ms")
    pairs_times = get_list("pairs_ms")
    collide_times = get_list("collide_ms")
    solve_times = get_list("solve_ms")
    contacts = get_list("contact_count")
    heights = [int(float(h)) for h in get_list("tree_height")] if get_list("tree_height") else [0]
    sah_norm = get_list("sah_normalized") if "sah_normalized" in rows[0] else []

    return {
        "count": len(rows),
        "step_ms_avg": avg(step_times),
        "step_ms_std": std(step_times),
        "pairs_ms_avg": avg(pairs_times),
        "pairs_ms_std": std(pairs_times),
        "collide_ms_avg": avg(collide_times),
        "solve_ms_avg": avg(solve_times),
        "contacts_avg": avg(contacts),
        "height_max": max(heights) if heights else 0,
        "height_avg": avg(heights),
        "sah_norm_avg": avg(sah_norm) if sah_norm else None
    }


def analyze_csv_command(csv_path):
    """Read and show metrics from one CSV file."""
    metrics = parse_csv(csv_path)
    if not metrics:
        print(f"[ERROR] Cannot read CSV file: {csv_path}")
        return 1

    print("=" * 70)
    print(f"  BENCHMARK METRICS REPORT: {os.path.basename(csv_path)}")
    print(f"  Path: {csv_path} | Total Frames: {metrics['count']}")
    print("=" * 70)
    print(f"  Step Time (ms):     {metrics['step_ms_avg']:9.4f}  (std: {metrics['step_ms_std']:.4f})")
    print(f"  Broad-Phase (ms):   {metrics['pairs_ms_avg']:9.4f}  (std: {metrics['pairs_ms_std']:.4f})")
    print(f"  Narrow-Phase (ms):  {metrics['collide_ms_avg']:9.4f}")
    print(f"  Solver Time (ms):   {metrics['solve_ms_avg']:9.4f}")
    print(f"  Average Contacts:   {metrics['contacts_avg']:9.1f}")
    print(f"  Tree Height:        avg={metrics['height_avg']:.2f}, max={metrics['height_max']}")
    if metrics['sah_norm_avg'] is not None:
        print(f"  Normalized SAH:     {metrics['sah_norm_avg']:9.4f}")
    print("=" * 70)
    return 0


def compare_csv_command(csv1, csv2):
    """Compare metrics between two CSV files."""
    m1 = parse_csv(csv1)
    m2 = parse_csv(csv2)
    if not m1 or not m2:
        print(f"[ERROR] Cannot read one or both CSV files: {csv1}, {csv2}")
        return 1

    lbl1 = os.path.basename(csv1)
    lbl2 = os.path.basename(csv2)
    sp_bp = (m1['pairs_ms_avg'] / m2['pairs_ms_avg']) if m2['pairs_ms_avg'] > 0 else 0.0
    sp_step = (m1['step_ms_avg'] / m2['step_ms_avg']) if m2['step_ms_avg'] > 0 else 0.0

    print("=" * 80)
    print(f"  SIDE-BY-SIDE COMPARISON: {lbl1} vs {lbl2}")
    print("=" * 80)
    header = f"{'Metric':<25} | {lbl1:<22} | {lbl2:<22} | {'Ratio (1/2)':<10}"
    print(header)
    print("-" * len(header))
    print(f"{'Broad-Phase (ms)':<25} | {m1['pairs_ms_avg']:<22.4f} | {m2['pairs_ms_avg']:<22.4f} | {sp_bp:.2f}x")
    print(f"{'Narrow-Phase (ms)':<25} | {m1['collide_ms_avg']:<22.4f} | {m2['collide_ms_avg']:<22.4f} | {(m1['collide_ms_avg']/m2['collide_ms_avg'] if m2['collide_ms_avg']>0 else 0.0):.2f}x")
    print(f"{'Constraint Solver (ms)':<25} | {m1['solve_ms_avg']:<22.4f} | {m2['solve_ms_avg']:<22.4f} | {(m1['solve_ms_avg']/m2['solve_ms_avg'] if m2['solve_ms_avg']>0 else 0.0):.2f}x")
    print(f"{'Total Step (ms)':<25} | {m1['step_ms_avg']:<22.4f} | {m2['step_ms_avg']:<22.4f} | {sp_step:.2f}x")
    print(f"{'Max Tree Height (H)':<25} | {m1['height_max']:<22} | {m2['height_max']:<22} | {m1['height_max'] - m2['height_max']:+d}")
    print(f"{'Average Contacts':<25} | {m1['contacts_avg']:<22.1f} | {m2['contacts_avg']:<22.1f} | {(m2['contacts_avg']/m1['contacts_avg'] if m1['contacts_avg']>0 else 1.0):.4f}")
    print("=" * 80)
    return 0


def build_command(exe, scene, actors, steps, repeats, workers, bp, sdbvh_opts, out_csv):
    """Build the command-line argument list for the benchmark process."""
    cmd = [
        exe,
        f"-b={scene}",
        f"-a={actors}",
        f"--steps={steps}",
        f"-r={repeats}",
        f"-w={workers}",
        f"-bp={bp}",
        "-c",
        f"--output-csv={out_csv}"
    ]

    if bp == "sdbvh":
        if sdbvh_opts.get("threshold") is not None:
            cmd.append(f"-th={sdbvh_opts['threshold']}")
        if sdbvh_opts.get("metric") is not None:
            cmd.append(f"-m={sdbvh_opts['metric']}")
        if sdbvh_opts.get("partition") is not None:
            cmd.append(f"-p={sdbvh_opts['partition']}")
        if sdbvh_opts.get("fattening") is not None:
            cmd.append(f"--fattening={sdbvh_opts['fattening']}")
        if sdbvh_opts.get("predictive") is not None:
            cmd.append(f"--predictive={sdbvh_opts['predictive']}")
        if sdbvh_opts.get("rotations") is not None:
            cmd.append(f"--rotations={sdbvh_opts['rotations']}")
        if sdbvh_opts.get("rebuild") is not None:
            cmd.append(f"--rebuild={sdbvh_opts['rebuild']}")
        if sdbvh_opts.get("ground_truth"):
            cmd.append("-gt")

    return cmd


def run_benchmark_suite(args):
    """Run the benchmark matrix and write summary results."""
    exe = find_executable(args.exe)
    if not exe:
        print("[ERROR] Benchmark executable not found. Build the project first.")
        return 1

    # Apply standard presets
    scenes = args.scenes
    actors_list = args.actors
    steps_override = args.steps
    repeats = args.repeats
    workers = args.workers
    broadphases = args.broadphases
    output_dir = args.output_dir
    today_str = datetime.now().strftime("%d-%m-%Y")

    if args.preset == "canonical-1000":
        scenes = CANONICAL_SCENES
        actors_list = [1000]
        repeats = 1
        workers = 1
        broadphases = ["native", "sdbvh"]
        if not output_dir:
            output_dir = os.path.join("benchmark_results", today_str, "results")

    elif args.preset == "scale-sweep":
        scenes = CANONICAL_SCENES
        actors_list = DEFAULT_SCALE_SWEEP_ACTORS
        steps_override = 500
        repeats = 5
        workers = 1
        broadphases = ["native", "sdbvh"]
        if not output_dir:
            output_dir = os.path.join("benchmark_results", today_str, "results")

    elif args.preset == "stress-10k":
        scenes = CANONICAL_SCENES
        actors_list = [10000]
        repeats = 1
        workers = 1
        broadphases = ["native", "sdbvh"]
        if not output_dir:
            output_dir = os.path.join("benchmark_results", today_str, "results")

    elif args.preset == "stress-100k":
        scenes = ["convex_pile", "many_pyramids", "spinner", "junkyard"]
        actors_list = [100000]
        steps_override = 5
        repeats = 1
        workers = 1
        broadphases = ["native", "sdbvh"]
        if not output_dir:
            output_dir = os.path.join("benchmark_results", today_str, "results")

    if not output_dir:
        output_dir = os.path.join("benchmark_results", today_str, "results")

    os.makedirs(output_dir, exist_ok=True)

    # Set SDBVH options
    sdbvh_opts = {
        "threshold": args.threshold,
        "metric": args.metric,
        "partition": args.partition,
        "fattening": args.fattening,
        "predictive": args.predictive,
        "rotations": args.rotations,
        "rebuild": args.rebuild,
        "ground_truth": args.ground_truth
    }

    # Build the test run list
    runs = []
    for scene in scenes:
        if steps_override is not None:
            s_steps = steps_override
        else:
            s_steps = CALIBRATED_STEPS.get(scene, 500)

        for actors in actors_list:
            # Skip ragdoll when actor count is more than 10000
            if scene == "ragdoll_pile" and actors > 10000:
                continue

            runs.append({
                "scene": scene,
                "actors": actors,
                "steps": s_steps
            })

    total_configs = len(runs)
    total_executions = total_configs * len(broadphases)

    print("=" * 80)
    print("  BOX3D / SDBVH BENCHMARK RUNNER")
    print(f"  Total Configurations: {total_configs} | Total Executions: {total_executions}")
    print(f"  Broadphases: {', '.join(broadphases)} | Workers: {workers} | Repeats: {repeats}")
    print(f"  Output Directory: {output_dir}")
    print("=" * 80 + "\n")

    summary_records = []
    exec_idx = 0

    # Run the test matrix
    for r_cfg in runs:
        scene = r_cfg["scene"]
        actors = r_cfg["actors"]
        steps = r_cfg["steps"]

        results_by_bp = {}

        for bp in broadphases:
            exec_idx += 1
            csv_filename = f"bench_{scene}_{steps}_{bp}.csv"
            csv_path = os.path.join(output_dir, csv_filename)

            print(f"[{exec_idx}/{total_executions}] Scene: {scene} | Actors: {actors} | Steps: {steps} | BP: {bp.upper()}", flush=True)

            cmd = build_command(exe, scene, actors, steps, repeats, workers, bp, sdbvh_opts, csv_path)

            t0 = time.time()
            proc = subprocess.run(cmd)
            elapsed = time.time() - t0

            if proc.returncode != 0:
                print(f"  [ERROR] Process exited with code {proc.returncode}", flush=True)
                continue

            metrics = parse_csv(csv_path)
            if metrics:
                results_by_bp[bp] = metrics
                print(f"  -> Done in {elapsed:.1f}s | Pairs: {metrics['pairs_ms_avg']:.3f} ms | Step: {metrics['step_ms_avg']:.3f} ms | H: {metrics['height_max']}", flush=True)

        # Calculate comparison data when both broadphase types ran
        rec = {
            "scene": scene,
            "actors": actors,
            "steps": steps,
            "repeats": repeats,
            "workers": workers
        }

        if "native" in results_by_bp and "sdbvh" in results_by_bp:
            nat = results_by_bp["native"]
            sd = results_by_bp["sdbvh"]
            sp_bp = nat["pairs_ms_avg"] / sd["pairs_ms_avg"] if sd["pairs_ms_avg"] > 0 else 0.0
            sp_step = nat["step_ms_avg"] / sd["step_ms_avg"] if sd["step_ms_avg"] > 0 else 0.0
            parity = sd["contacts_avg"] / nat["contacts_avg"] if nat["contacts_avg"] > 0 else 1.0

            rec.update({
                "native_pairs_ms": nat["pairs_ms_avg"],
                "sdbvh_pairs_ms": sd["pairs_ms_avg"],
                "speedup_broadphase": round(sp_bp, 2),
                "native_collide_ms": nat["collide_ms_avg"],
                "sdbvh_collide_ms": sd["collide_ms_avg"],
                "native_solve_ms": nat["solve_ms_avg"],
                "sdbvh_solve_ms": sd["solve_ms_avg"],
                "native_step_ms": nat["step_ms_avg"],
                "sdbvh_step_ms": sd["step_ms_avg"],
                "speedup_step": round(sp_step, 2),
                "native_height": nat["height_max"],
                "sdbvh_height": sd["height_max"],
                "native_sah_norm": nat["sah_norm_avg"],
                "sdbvh_sah_norm": sd["sah_norm_avg"],
                "native_contacts": nat["contacts_avg"],
                "sdbvh_contacts": sd["contacts_avg"],
                "contact_parity": round(parity, 4)
            })
        elif "sdbvh" in results_by_bp:
            sd = results_by_bp["sdbvh"]
            rec.update({
                "sdbvh_pairs_ms": sd["pairs_ms_avg"],
                "sdbvh_collide_ms": sd["collide_ms_avg"],
                "sdbvh_solve_ms": sd["solve_ms_avg"],
                "sdbvh_step_ms": sd["step_ms_avg"],
                "sdbvh_height": sd["height_max"],
                "sdbvh_sah_norm": sd["sah_norm_avg"],
                "sdbvh_contacts": sd["contacts_avg"]
            })
        elif "native" in results_by_bp:
            nat = results_by_bp["native"]
            rec.update({
                "native_pairs_ms": nat["pairs_ms_avg"],
                "native_collide_ms": nat["collide_ms_avg"],
                "native_solve_ms": nat["solve_ms_avg"],
                "native_step_ms": nat["step_ms_avg"],
                "native_height": nat["height_max"],
                "native_sah_norm": nat["sah_norm_avg"],
                "native_contacts": nat["contacts_avg"]
            })

        summary_records.append(rec)
        print("-" * 80, flush=True)

        # Save incremental summary after each scene so progress is never lost
        inc_summary_path = os.path.join(output_dir, "summary_stress_10k.csv" if args.preset == "stress-10k" else "summary.csv")
        if summary_records:
            inc_fields = list(summary_records[0].keys())
            for s in summary_records:
                for k in s.keys():
                    if k not in inc_fields:
                        inc_fields.append(k)
            with open(inc_summary_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=inc_fields)
                writer.writeheader()
                writer.writerows(summary_records)

    # Save summary to CSV file
    summary_path = os.path.join(output_dir, "summary.csv")
    if summary_records:
        fieldnames = list(summary_records[0].keys())
        for s in summary_records:
            for k in s.keys():
                if k not in fieldnames:
                    fieldnames.append(k)

        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary_records)

    # Print the summary table
    print("\n" + "=" * 90)
    print("  BENCHMARK EXECUTION SUMMARY")
    print("=" * 90)
    fmt = "{:<14} | {:>6} | {:>5} | {:>10} | {:>10} | {:>7} | {:>10} | {:>7} | {:>8}"
    print(fmt.format("Scene", "Actors", "Steps", "Pairs(B3D)", "Pairs(SD)", "SP(BP)", "Step(SD)", "SP(Stp)", "Height"))
    print("-" * 90)
    for s in summary_records:
        p_nat = f"{s.get('native_pairs_ms', 0):.2f}" if 'native_pairs_ms' in s else "-"
        p_sd = f"{s.get('sdbvh_pairs_ms', 0):.2f}" if 'sdbvh_pairs_ms' in s else "-"
        sp_bp = f"{s.get('speedup_broadphase', 0):.2f}x" if 'speedup_broadphase' in s else "-"
        st_sd = f"{s.get('sdbvh_step_ms', 0):.2f}" if 'sdbvh_step_ms' in s else "-"
        sp_st = f"{s.get('speedup_step', 0):.2f}x" if 'speedup_step' in s else "-"
        h = f"{s.get('native_height', '-') }->{s.get('sdbvh_height', '-')}"
        print(fmt.format(s['scene'], s['actors'], s['steps'], p_nat, p_sd, sp_bp, st_sd, sp_st, h))
    print("=" * 90)
    print(f"Summary written to: {summary_path}\n")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Tool to run and analyze Box3D and SDBVH benchmarks."
    )
    # Utility sub-modes
    parser.add_argument("--analyze", type=str, help="Read and show metrics from one CSV file.")
    parser.add_argument("--compare", nargs=2, metavar=("CSV1", "CSV2"), help="Compare two CSV files side by side.")

    # Execution parameters
    parser.add_argument("--preset", choices=["canonical-1000", "scale-sweep", "stress-10k", "stress-100k"],
                        help="Run a predefined benchmark suite.")
    parser.add_argument("--scenes", "-b", type=lambda s: [x.strip() for x in s.split(",")], default=CANONICAL_SCENES,
                        help="Comma-separated scene names.")
    parser.add_argument("--actors", "-a", type=lambda s: [int(x.strip()) for x in s.split(",")], default=[1000],
                        help="Comma-separated actor counts.")
    parser.add_argument("--steps", "-s", type=int, default=None,
                        help="Set the number of simulation steps.")
    parser.add_argument("--repeats", "-r", type=int, default=1,
                        help="Number of test repetitions for each configuration.")
    parser.add_argument("--workers", "-w", type=int, default=1,
                        help="Number of worker threads.")
    parser.add_argument("--broadphases", "-bp", type=lambda s: [x.strip().lower() for x in s.split(",")], default=["native", "sdbvh"],
                        help="Broadphases to test: 'native', 'sdbvh', or 'native,sdbvh'.")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Directory where the tool writes CSV files.")
    parser.add_argument("--exe", type=str, default=None,
                        help="Path to the benchmark executable file.")

    # SDBVH options
    parser.add_argument("--threshold", "-th", type=float, default=None, help="Subtree rebuild threshold value.")
    parser.add_argument("--metric", "-m", choices=["area_ratio", "subtree_sah"], default=None, help="Degradation metric to use.")
    parser.add_argument("--partition", "-p", choices=["sah", "median"], default=None, help="Rebuild partition algorithm to use.")
    parser.add_argument("--fattening", choices=["on", "off"], default=None, help="Enable or disable AABB fattening.")
    parser.add_argument("--predictive", choices=["on", "off"], default=None, help="Enable or disable predictive AABB expansion.")
    parser.add_argument("--rotations", choices=["on", "off"], default=None, help="Enable or disable tree rotations.")
    parser.add_argument("--rebuild", choices=["on", "off"], default=None, help="Enable or disable tree rebuilds.")
    parser.add_argument("--ground-truth", action="store_true", help="Calculate ideal SAH tree quality at each step.")

    args = parser.parse_args()

    if args.analyze:
        sys.exit(analyze_csv_command(args.analyze))
    if args.compare:
        sys.exit(compare_csv_command(args.compare[0], args.compare[1]))

    sys.exit(run_benchmark_suite(args))


if __name__ == "__main__":
    main()
