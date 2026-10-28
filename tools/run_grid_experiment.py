#!/usr/bin/env python3
"""
tools/run_grid_experiment.py
Executa bateria de experimentos.
Testa Box3D Nativo vs DBVH em grid (threshold: 1.3, 1.5, 1.8 x rebuild branches: 2, 4, 6)
com contagens de corpos N = [10, 100, 500, 1000, 10000].
Gera progresso em tempo real e consolida os resultados em grid_summary.csv.
"""

import os
import sys
import csv
import time
import argparse
import subprocess

DEFAULT_SCALES = [10, 100, 500, 1000, 10000]
DEFAULT_THRESHOLDS = [1.3, 1.5, 1.8]
DEFAULT_REBUILDS = [2, 4, 6]
DEFAULT_STEPS = 500
OUTPUT_DIR = os.path.join("benchmark_results", "grid_experiment")
SUMMARY_FILE = os.path.join(OUTPUT_DIR, "grid_summary.csv")

def parse_args():
    parser = argparse.ArgumentParser(description="Executa grid search de simulacao completa (Estrategia B - Frente 1).")
    parser.add_argument("--scales", nargs="+", type=int, default=DEFAULT_SCALES,
                        help="Contagens de corpos a testar (padrao: 10 100 500 1000 10000)")
    parser.add_argument("--thresholds", nargs="+", type=float, default=DEFAULT_THRESHOLDS,
                        help="Thresholds de degradacao DBVH (padrao: 1.3 1.5 1.8)")
    parser.add_argument("--rebuilds", nargs="+", type=int, default=DEFAULT_REBUILDS,
                        help="Subtrees / ramos de rebuild DBVH (padrao: 2 4 6)")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS,
                        help="Numero de steps de simulacao fisica por execucao (padrao: 500)")
    parser.add_argument("--exe", default=os.path.join("build", "bin", "benchmark.exe"),
                        help="Caminho do binario benchmark.exe")
    parser.add_argument("--skip-native", action="store_true", help="Pular execucoes nativas")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="Diretorio de saida dos CSVs")
    return parser.parse_args()

def analyze_csv(filepath):
    """Calcula médias e valores finais de um arquivo CSV de benchmark."""
    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            if not reader:
                return None
            
            def avg(key):
                if key in reader[0]:
                    vals = [float(r[key]) for r in reader if key in r and r[key] != ""]
                    return sum(vals) / len(vals) if vals else 0.0
                return 0.0

            last = reader[-1]
            return {
                "step_ms": avg("step_ms"),
                "pairs_ms": avg("pairs_ms"),
                "collide_ms": avg("collide_ms"),
                "solve_ms": avg("solve_ms"),
                "contacts": avg("contact_count"),
                "tree_height": int(last.get("tree_height", 0)),
                "sah_norm": float(last.get("sah_normalized", 0.0)),
                "leaf_count": int(last.get("leaf_count", 0)),
                "total_steps": len(reader)
            }
    except Exception as e:
        print(f"\n[Aviso] Falha ao processar CSV {filepath}: {e}")
        return None

def write_summary_row(summary_path, row_dict):
    """Escreve ou anexa uma linha ao arquivo grid_summary.csv."""
    headers = [
        "scale", "broadphase", "threshold", "rebuilds", "wall_time_s",
        "step_ms_avg", "pairs_ms_avg", "collide_ms_avg", "solve_ms_avg",
        "contacts_avg", "tree_height_final", "sah_norm_final", "csv_file"
    ]
    file_exists = os.path.isfile(summary_path)
    with open(summary_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_dict)

def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    if not os.path.isfile(args.exe):
        print(f"Erro: Binário não encontrado em {args.exe}")
        sys.exit(1)

    # Monta a lista de tarefas
    tasks = []
    for scale in args.scales:
        # Nativo (1 vez por escala)
        if not args.skip_native:
            tasks.append({
                "scale": scale,
                "broadphase": "native",
                "threshold": None,
                "rebuilds": None,
                "label": "Box3D Nativo"
            })
        # DBVH (3 thresholds x 3 rebuilds = 9 combinações)
        for th in args.thresholds:
            for rb in args.rebuilds:
                tasks.append({
                    "scale": scale,
                    "broadphase": "dbvh",
                    "threshold": th,
                    "rebuilds": rb,
                    "label": f"DBVH (th={th}, rb={rb})"
                })

    total_tasks = len(tasks)
    print("=" * 80)
    print(" BATERIA DE BENCHMARKS - ESTRATÉGIA B (Frente 1: Simulação Completa)")
    print("=" * 80)
    print(f" Escalas de corpos (N): {args.scales}")
    print(f" Steps de simulação por execução: {args.steps}")
    print(f" Grid DBVH: Thresholds={args.thresholds} | Rebuilds={args.rebuilds}")
    print(f" Total de baterias a executar: {total_tasks}")
    print(f" Diretório de saída: {args.output_dir}")
    print("=" * 80)

    start_all = time.perf_counter()

    for idx, t in enumerate(tasks, start=1):
        scale = t["scale"]
        bp = t["broadphase"]
        th = t["threshold"]
        rb = t["rebuilds"]
        label = t["label"]

        if bp == "native":
            csv_name = f"sim_native_N{scale}.csv"
        else:
            csv_name = f"sim_dbvh_N{scale}_th{th}_rb{rb}.csv"
        
        csv_path = os.path.join(args.output_dir, csv_name)

        cmd = [
            args.exe,
            "--benchmark=convex_pile",
            f"--actors={scale}",
            f"--steps={args.steps}",
            "--workers=1",
            "--repeats=1",
            f"--broadphase={bp}",
            "-c",
            "-o", csv_path
        ]

        if bp == "dbvh":
            cmd.extend([
                f"--threshold={th}",
                f"--rebuild-budget={rb}",
                "--adaptive=on",
                "--max-subtree-leaves=64"
            ])

        print(f"[{idx:02d}/{total_tasks:02d}] Invocando: N={scale:<5} | {label:<22} ... ", end="", flush=True)

        t_start = time.perf_counter()
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        wall_time = time.perf_counter() - t_start

        if proc.returncode != 0:
            print(f"FALHOU ({wall_time:.2f}s)!")
            print(f"      Erro: {proc.stderr.strip()[:200]}")
            continue

        metrics = analyze_csv(csv_path)
        if metrics:
            print(f"OK ({wall_time:.2f}s) | Step: {metrics['step_ms']:.2f}ms | Pairs: {metrics['pairs_ms']:.4f}ms | Collide: {metrics['collide_ms']:.2f}ms | H={metrics['tree_height']}")
            
            # Grava no resumo
            row = {
                "scale": scale,
                "broadphase": bp,
                "threshold": th if th is not None else "",
                "rebuilds": rb if rb is not None else "",
                "wall_time_s": f"{wall_time:.2f}",
                "step_ms_avg": f"{metrics['step_ms']:.4f}",
                "pairs_ms_avg": f"{metrics['pairs_ms']:.4f}",
                "collide_ms_avg": f"{metrics['collide_ms']:.4f}",
                "solve_ms_avg": f"{metrics['solve_ms']:.4f}",
                "contacts_avg": f"{metrics['contacts']:.1f}",
                "tree_height_final": metrics["tree_height"],
                "sah_norm_final": f"{metrics['sah_norm']:.4f}",
                "csv_file": csv_name
            }
            write_summary_row(SUMMARY_FILE, row)
        else:
            print(f"OK ({wall_time:.2f}s) [CSV não encontrado ou vazio]")

    total_duration = time.perf_counter() - start_all
    print("=" * 80)
    print(f" Bateria concluída em {total_duration / 60:.2f} minutos ({total_duration:.1f} segundos)!")
    print(f" Resumo consolidado salvo em: {SUMMARY_FILE}")
    print("=" * 80)

if __name__ == "__main__":
    main()
