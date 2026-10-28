#!/usr/bin/env python3
"""
tools/run_comprehensive_benchmarks.py
Executa a suite completa de benchmarks para 1.000 e 10.000 corpos em todas as 5 cenas
com suporte a escala (convex_pile, many_pyramids, spinner, junkyard, ragdoll_pile).
Compara Box3D Nativo vs SDBVH e gera um relatório HTML widescreen condensado e executivo.
"""

import os
import sys
import subprocess
import time
import csv
import json

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
from generate_condensed_report import generate_condensed_html

EXE_PATH = os.path.join("build", "bin", "benchmark.exe")
OUTPUT_DIR = "benchmark_results"

SCENES = [
    {
        "id": "convex_pile",
        "name": "Convex Pile",
        "steps_1k": 1000,
        "steps_10k": 500
    },
    {
        "id": "many_pyramids",
        "name": "Many Pyramids",
        "steps_1k": 1000,
        "steps_10k": 500
    },
    {
        "id": "spinner",
        "name": "Spinner (Agitador)",
        "steps_1k": 1000,
        "steps_10k": 500
    },
    {
        "id": "junkyard",
        "name": "Junkyard (Pusher)",
        "steps_1k": 1000,
        "steps_10k": 500
    },
    {
        "id": "ragdoll_pile",
        "name": "Ragdoll Pile",
        "steps_1k": 1000,
        "steps_10k": 500
    }
]

SCALES = [1000, 10000]

def run_test(scene_id, actors, steps, broadphase, output_csv, partition=None):
    cmd = [
        EXE_PATH,
        f"-b={scene_id}",
        f"-a={actors}",
        f"--steps={steps}",
        "-r=1",
        "-w=1",
        f"-bp={broadphase}",
        "-c",
        f"--output-csv={output_csv}"
    ]
    if broadphase == "sdbvh":
        cmd.extend([
            "-m=area_ratio",
            "--threshold=1.80",
            "--fattening=off",
            "--predictive=off",
            "--rotations=off",
            "--adaptive=on",
            "--max-subtree-leaves=1024"
        ])
        if partition:
            cmd.append(f"--partition={partition}")

    print(f">> Executando [{broadphase.upper()}] {scene_id} ({actors} corpos, {steps} passos)...", flush=True)
    start_t = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start_t

    if res.returncode != 0:
        print(f"   [ERRO] Código {res.returncode}: {res.stderr or res.stdout}", flush=True)
        return False, elapsed

    print(f"   [OK] Concluído em {elapsed:.2f}s", flush=True)
    return True, elapsed

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

    step_ms = get_list("step_ms")
    pairs_ms = get_list("pairs_ms")
    contacts = get_list("contact_count")
    heights = get_list("tree_height")

    return {
        "step_ms_avg": avg(step_ms),
        "pairs_ms_avg": avg(pairs_ms),
        "contacts_avg": avg(contacts),
        "height_avg": avg(heights)
    }

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    target_scales = SCALES
    if "--only-1k" in sys.argv or "-1k" in sys.argv or (len(sys.argv) > 1 and "1000" in sys.argv[1]):
        target_scales = [1000]

    print("================================================================================")
    print(f"INICIANDO SUITE DE BENCHMARKS: {', '.join(str(s) for s in target_scales)} CORPOS")
    print(f"Cenas: {', '.join([s['name'] for s in SCENES])}")
    print("================================================================================\n")

    summary_rows = []

    for s in SCENES:
        sid = s["id"]
        sname = s["name"]
        for actors in target_scales:
            steps = s["steps_1k"] if actors == 1000 else s["steps_10k"]

            csv_nat = os.path.join(OUTPUT_DIR, f"scale_{sid}_{actors}_native.csv")
            csv_sd = os.path.join(OUTPUT_DIR, f"scale_{sid}_{actors}_sdbvh.csv")

            run_test(sid, actors, steps, "native", csv_nat)
            run_test(sid, actors, steps, "sdbvh", csv_sd)

            nat_data = parse_csv(csv_nat)
            sd_data = parse_csv(csv_sd)

            if nat_data and sd_data:
                bp_speedup = (nat_data["pairs_ms_avg"] / sd_data["pairs_ms_avg"]) if sd_data["pairs_ms_avg"] > 0 else 1.0
                step_speedup = (nat_data["step_ms_avg"] / sd_data["step_ms_avg"]) if sd_data["step_ms_avg"] > 0 else 1.0

                summary_rows.append({
                    "scene_id": sid,
                    "scene_name": sname,
                    "actors": actors,
                    "steps": steps,
                    "native_pairs_ms": nat_data["pairs_ms_avg"],
                    "sdbvh_pairs_ms": sd_data["pairs_ms_avg"],
                    "bp_speedup": bp_speedup,
                    "native_step_ms": nat_data["step_ms_avg"],
                    "sdbvh_step_ms": sd_data["step_ms_avg"],
                    "step_speedup": step_speedup,
                    "native_height": nat_data["height_avg"],
                    "sdbvh_height": sd_data["height_avg"],
                    "native_contacts": nat_data["contacts_avg"],
                    "sdbvh_contacts": sd_data["contacts_avg"]
                })

                print(f"--> [{sname} - {actors} corpos] Speedup Pairs: {bp_speedup:.2f}x | Speedup Step: {step_speedup:.2f}x\n", flush=True)

    summary_csv_path = os.path.join(OUTPUT_DIR, "summary_scale_1k_10k_all_scenes.csv")
    
    # Merge with existing rows if only running a subset of scales
    existing_rows = []
    if os.path.exists(summary_csv_path):
        with open(summary_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                existing_rows.append(r)

    final_rows = []
    for s in SCENES:
        sid = s["id"]
        for actors in [1000, 10000]:
            # Look in new summary_rows
            match = next((r for r in summary_rows if r["scene_id"] == sid and r["actors"] == actors), None)
            if match is None:
                # Look in existing_rows
                match = next((r for r in existing_rows if r["scene_id"] == sid and int(r["actors"]) == actors), None)
            if match:
                final_rows.append(match)

    if final_rows:
        with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(final_rows[0].keys()))
            writer.writeheader()
            writer.writerows(final_rows)
        print(f">> Resumo consolidado salvo em CSV: {summary_csv_path}")

    generate_condensed_html()

if __name__ == "__main__":
    main()
