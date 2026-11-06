import subprocess
import os
import sys
import csv
import math
import statistics

# Battery 2: Asymptotic Stress Test
# 10,000 bodies (30 steps, ragdoll 20 steps)
# 100,000 bodies (5 steps)
# 1 repeat per test (-r=1)

CONFIGS = [
    # 10k tests
    {"scene": "convex_pile", "n": 10000, "steps": 1000},
    {"scene": "many_pyramids", "n": 10000, "steps": 100},
    {"scene": "spinner", "n": 10000, "steps": 400},
    {"scene": "junkyard", "n": 10000, "steps": 1500},
    {"scene": "ragdoll_pile", "n": 10000, "steps": 400},
    # 100k tests (excluding ragdoll due to 64k joint limit)
    {"scene": "convex_pile", "n": 100000, "steps": 1000},
    {"scene": "many_pyramids", "n": 100000, "steps": 100},
    {"scene": "spinner", "n": 100000, "steps": 400},
    {"scene": "junkyard", "n": 100000, "steps": 1500},
]

BROADPHASES = ["native", "sdbvh"]

def mean_or_zero(lst):
    return statistics.mean(lst) if lst else 0.0

def main():
    out_dir = os.path.join("benchmark_results", "final_10k_100k")
    os.makedirs(out_dir, exist_ok=True)
    temp_csv = os.path.join(out_dir, "temp_large_run.csv")
    summary_csv = os.path.join(out_dir, "summary_large_scale_10k_100k.csv")
    detailed_csv = os.path.join(out_dir, "detailed_large_scale_10k_100k.csv")
    
    detailed_rows = []
    summary_rows = []
    
    total = len(CONFIGS)
    print(f"Starting Battery 2: Asymptotic Stress Testing (10k and 100k bodies)", flush=True)
    print(f"Total configurations: {total} (each tested with Native and SDBVH)", flush=True)
    print("=" * 80, flush=True)
    
    for idx, cfg in enumerate(CONFIGS, 1):
        scene = cfg["scene"]
        n = cfg["n"]
        steps = cfg["steps"]
        
        print(f"\n[{idx}/{total}] Scene: {scene} | N: {n} | Steps: {steps}", flush=True)
        bp_results = {}
        
        for bp in BROADPHASES:
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
            
            print(f"  Starting {bp.upper()}...", flush=True)
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                print(f"  Error running {scene} {bp} N={n}: {res.stderr}", flush=True)
                continue
                
            if not os.path.exists(temp_csv):
                print(f"  Warning: {temp_csv} not generated!", flush=True)
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
            
            bp_results[bp] = {
                "pairs_ms": m_pair,
                "step_ms": m_step,
                "collide_ms": m_collide,
                "solve_ms": m_solve,
                "contacts": m_contact,
                "height": m_height
            }
            
            print(f"    {bp.upper():6s} -> Pairs: {m_pair:8.4f} ms | Step: {m_step:8.3f} ms | "
                  f"Contacts: {m_contact:8.1f} | Tree Height: {m_height}", flush=True)
                  
            detailed_rows.append({
                "scene": scene,
                "n": n,
                "steps": steps,
                "broadphase": bp,
                "pairs_ms": m_pair,
                "step_ms": m_step,
                "collide_ms": m_collide,
                "solve_ms": m_solve,
                "contacts": m_contact,
                "tree_height": m_height
            })
            
        if "native" in bp_results and "sdbvh" in bp_results:
            nat = bp_results["native"]
            sdb = bp_results["sdbvh"]
            
            speedup_pairs = (nat["pairs_ms"] / sdb["pairs_ms"]) if sdb["pairs_ms"] > 0 else 0.0
            speedup_step = (nat["step_ms"] / sdb["step_ms"]) if sdb["step_ms"] > 0 else 0.0
            contact_parity = (sdb["contacts"] / nat["contacts"]) if nat["contacts"] > 0 else 1.0
            
            print(f"    ==> SPEEDUP BROADPHASE: {speedup_pairs:6.2f}x | SPEEDUP GLOBAL: {speedup_step:6.2f}x | "
                  f"PARITY: {contact_parity*100:6.2f}% | HEIGHT (NAT vs SDB): {nat['height']} vs {sdb['height']}", flush=True)
                  
            summary_rows.append({
                "scene": scene,
                "n": n,
                "steps": steps,
                "native_pairs_ms": round(nat["pairs_ms"], 4),
                "sdbvh_pairs_ms": round(sdb["pairs_ms"], 4),
                "speedup_broadphase": round(speedup_pairs, 2),
                "native_step_ms": round(nat["step_ms"], 3),
                "sdbvh_step_ms": round(sdb["step_ms"], 3),
                "speedup_step": round(speedup_step, 2),
                "native_contacts": round(nat["contacts"], 1),
                "sdbvh_contacts": round(sdb["contacts"], 1),
                "contact_parity": round(contact_parity, 4),
                "native_height": nat["height"],
                "sdbvh_height": sdb["height"]
            })
            
            with open(summary_csv, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
                writer.writeheader()
                writer.writerows(summary_rows)
                
            with open(detailed_csv, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=detailed_rows[0].keys())
                writer.writeheader()
                writer.writerows(detailed_rows)
                
    if os.path.exists(temp_csv):
        os.remove(temp_csv)
        
    print("\n" + "=" * 80, flush=True)
    print("ALL LARGE SCALE BENCHMARKS FINISHED SUCCESSFULLY!", flush=True)
    print(f"Summary written to: {summary_csv}", flush=True)
    print(f"Detailed runs written to: {detailed_csv}", flush=True)

if __name__ == "__main__":
    main()
