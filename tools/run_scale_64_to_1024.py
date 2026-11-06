import subprocess
import os
import sys
import csv
import math
import statistics

SCENES = ["convex_pile", "many_pyramids", "spinner", "junkyard", "ragdoll_pile"]
SIZES = [64, 128, 256, 512, 1024]
REPEATS = 5
BROADPHASES = ["native", "sdbvh"]

def get_step_count(scene):
    step_map = {
        "convex_pile": 1000,
        "spinner": 400,
        "ragdoll_pile": 400,
        "many_pyramids": 100,
        "junkyard": 1500
    }
    return step_map.get(scene, 500)

def mean_or_zero(lst):
    return statistics.mean(lst) if lst else 0.0

def stdev_or_zero(lst):
    return statistics.stdev(lst) if len(lst) > 1 else 0.0

def main():
    out_dir = os.path.join("benchmark_results", "2026-11-01_scale_sweep_64_to_1024")
    os.makedirs(out_dir, exist_ok=True)
    temp_csv = os.path.join(out_dir, "temp_run.csv")
    summary_csv = os.path.join(out_dir, "summary_scale_64_to_1024.csv")
    detailed_csv = os.path.join(out_dir, "detailed_scale_64_to_1024.csv")
    
    detailed_rows = []
    summary_rows = []
    
    total_configs = len(SCENES) * len(SIZES)
    config_idx = 0
    
    print(f"Starting Battery 1: 6 scenes x 5 sizes (64..1024) x 5 repeats x 2 broadphases", flush=True)
    print(f"Total configurations to evaluate: {total_configs}", flush=True)
    print("=" * 80, flush=True)
    
    for scene in SCENES:
        steps = get_step_count(scene)
        for n in SIZES:
            config_idx += 1
            print(f"\n[{config_idx}/{total_configs}] Running Scene: {scene} | N: {n} | Steps: {steps}", flush=True)
            
            bp_stats = {}
            for bp in BROADPHASES:
                run_pairs = []
                run_steps = []
                run_collides = []
                run_solves = []
                run_contacts = []
                run_heights = []
                
                for r in range(REPEATS):
                    cmd = [
                        "build\\bin\\benchmark.exe",
                        f"-b={scene}",
                        f"-a={n}",
                        f"--steps={steps}",
                        "-w=1",
                        "-r=1",
                        f"-bp={bp}",
                        "-c",
                        f"-o={temp_csv}"
                    ]
                    
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if res.returncode != 0:
                        print(f"Error running {scene} {bp} N={n} repeat={r}: {res.stderr}", flush=True)
                        continue
                        
                    if not os.path.exists(temp_csv):
                        print(f"Warning: {temp_csv} not generated!", flush=True)
                        continue
                        
                    with open(temp_csv, mode="r", newline="", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        frames = list(reader)
                        
                    if not frames:
                        continue
                        
                    pairs_vals = [float(row["pairs_ms"]) for row in frames]
                    step_vals = [float(row["step_ms"]) for row in frames]
                    collide_vals = [float(row["collide_ms"]) for row in frames]
                    solve_vals = [float(row["solve_ms"]) for row in frames]
                    contact_vals = [float(row["contact_count"]) for row in frames]
                    height_val = int(frames[-1]["tree_height"])
                    
                    m_pair = mean_or_zero(pairs_vals)
                    m_step = mean_or_zero(step_vals)
                    m_collide = mean_or_zero(collide_vals)
                    m_solve = mean_or_zero(solve_vals)
                    m_contact = mean_or_zero(contact_vals)
                    m_height = height_val
                    
                    run_pairs.append(m_pair)
                    run_steps.append(m_step)
                    run_collides.append(m_collide)
                    run_solves.append(m_solve)
                    run_contacts.append(m_contact)
                    run_heights.append(m_height)
                    
                    detailed_rows.append({
                        "scene": scene,
                        "n": n,
                        "broadphase": bp,
                        "repeat": r,
                        "pairs_ms": m_pair,
                        "step_ms": m_step,
                        "collide_ms": m_collide,
                        "solve_ms": m_solve,
                        "contacts": m_contact,
                        "tree_height": m_height
                    })
                    
                bp_stats[bp] = {
                    "pairs_mean": mean_or_zero(run_pairs),
                    "pairs_std": stdev_or_zero(run_pairs),
                    "step_mean": mean_or_zero(run_steps),
                    "step_std": stdev_or_zero(run_steps),
                    "collide_mean": mean_or_zero(run_collides),
                    "solve_mean": mean_or_zero(run_solves),
                    "contacts_mean": mean_or_zero(run_contacts),
                    "height_final": run_heights[-1] if run_heights else 0
                }
                
                print(f"  {bp.upper():6s} -> Pairs: {bp_stats[bp]['pairs_mean']:7.4f} +/- {bp_stats[bp]['pairs_std']:6.4f} ms | "
                      f"Step: {bp_stats[bp]['step_mean']:7.3f} ms | Contacts: {bp_stats[bp]['contacts_mean']:7.1f} | "
                      f"Height: {bp_stats[bp]['height_final']}", flush=True)
            
            nat = bp_stats["native"]
            sdb = bp_stats["sdbvh"]
            
            speedup_pairs = (nat["pairs_mean"] / sdb["pairs_mean"]) if sdb["pairs_mean"] > 0 else 0.0
            speedup_step = (nat["step_mean"] / sdb["step_mean"]) if sdb["step_mean"] > 0 else 0.0
            contact_parity = (sdb["contacts_mean"] / nat["contacts_mean"]) if nat["contacts_mean"] > 0 else 1.0
            
            print(f"  ==> SPEEDUP BROADPHASE: {speedup_pairs:6.2f}x | SPEEDUP GLOBAL: {speedup_step:6.2f}x | PARITY: {contact_parity*100:6.2f}%", flush=True)
            
            summary_rows.append({
                "scene": scene,
                "n": n,
                "steps": steps,
                "native_pairs_ms": round(nat["pairs_mean"], 4),
                "native_pairs_std": round(nat["pairs_std"], 4),
                "sdbvh_pairs_ms": round(sdb["pairs_mean"], 4),
                "sdbvh_pairs_std": round(sdb["pairs_std"], 4),
                "speedup_broadphase": round(speedup_pairs, 2),
                "native_step_ms": round(nat["step_mean"], 3),
                "native_step_std": round(nat["step_std"], 3),
                "sdbvh_step_ms": round(sdb["step_mean"], 3),
                "sdbvh_step_std": round(sdb["step_std"], 3),
                "speedup_step": round(speedup_step, 2),
                "native_contacts": round(nat["contacts_mean"], 1),
                "sdbvh_contacts": round(sdb["contacts_mean"], 1),
                "contact_parity": round(contact_parity, 4),
                "native_height": nat["height_final"],
                "sdbvh_height": sdb["height_final"]
            })
            
            # Save progress periodically using standard csv
            if summary_rows:
                with open(summary_csv, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(summary_rows)
                    
            if detailed_rows:
                with open(detailed_csv, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=detailed_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(detailed_rows)
            
    if os.path.exists(temp_csv):
        os.remove(temp_csv)
        
    print("\n" + "=" * 80, flush=True)
    print("ALL SCALE BENCHMARKS FINISHED SUCCESSFULLY!", flush=True)
    print(f"Summary written to: {summary_csv}", flush=True)
    print(f"Detailed runs written to: {detailed_csv}", flush=True)

if __name__ == "__main__":
    main()
