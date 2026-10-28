#!/usr/bin/env python3
"""
tools/run_simultaneous_scale_suite.py
Executa a suíte de escala assintótica (128, 256, 512, 1000 e 10000 corpos)
com 500 passos em todas as 5 cenas do Box3D.
Executa o Box3D Nativo e a SDBVH SIMULTANEAMENTE (processos paralelos com 1 thread cada).
"""

import os
import sys
import time
import csv
import subprocess

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

EXE_PATH = os.path.join("build", "bin", "benchmark.exe")
OUTPUT_DIR = "benchmark_results"
CSV_SUMMARY = os.path.join(OUTPUT_DIR, "summary_scale_128_to_10000_all_scenes.csv")
HTML_REPORT = os.path.join(OUTPUT_DIR, "relatorio_escala_completa_128_10000.html")

SCENES = [
    {"id": "convex_pile", "name": "Convex Pile"},
    {"id": "many_pyramids", "name": "Many Pyramids"},
    {"id": "spinner", "name": "Spinner (Agitador)"},
    {"id": "junkyard", "name": "Junkyard (Pusher)"},
    {"id": "ragdoll_pile", "name": "Ragdoll Pile"}
]

SCALES = [128, 256, 512, 1000, 10000]
STEPS = 500
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
        "height_avg": avg(get_list("tree_height"))
    }

def run_pair_simultaneously(scene_id, scene_name, scale, steps, workers):
    csv_native = os.path.join(OUTPUT_DIR, f"scale_{scene_id}_{scale}_native.csv")
    csv_sdbvh = os.path.join(OUTPUT_DIR, f"scale_{scene_id}_{scale}_sdbvh.csv")

    cmd_native = [
        EXE_PATH,
        f"-b={scene_id}",
        f"-a={scale}",
        f"--steps={steps}",
        "-r=1",
        f"-w={workers}",
        "-bp=native",
        "-c",
        f"--output-csv={csv_native}"
    ]

    cmd_sdbvh = [
        EXE_PATH,
        f"-b={scene_id}",
        f"-a={scale}",
        f"--steps={steps}",
        "-r=1",
        f"-w={workers}",
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

    print(f">> Iniciando [{scene_name}] ({scale} corpos, {steps} passos) em paralelo...", flush=True)
    t0 = time.time()

    # Dispara os dois processos simultaneamente
    p_native = subprocess.Popen(cmd_native, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p_sdbvh = subprocess.Popen(cmd_sdbvh, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    out_nat, err_nat = p_native.communicate()
    out_sdbvh, err_sdbvh = p_sdbvh.communicate()
    elapsed = time.time() - t0

    if p_native.returncode != 0:
        print(f"   [ERRO NATIVE] Código {p_native.returncode}: {err_nat or out_nat}", flush=True)
    if p_sdbvh.returncode != 0:
        print(f"   [ERRO SDBVH] Código {p_sdbvh.returncode}: {err_sdbvh or out_sdbvh}", flush=True)

    data_nat = parse_csv(csv_native)
    data_sdbvh = parse_csv(csv_sdbvh)

    if not data_nat or not data_sdbvh:
        print(f"   [FALHA] Não foi possível ler dados CSV para {scene_id} ({scale} corpos)", flush=True)
        return None

    bp_speedup = data_nat["pairs_ms_avg"] / data_sdbvh["pairs_ms_avg"] if data_sdbvh["pairs_ms_avg"] > 0 else 1.0
    step_speedup = data_nat["step_ms_avg"] / data_sdbvh["step_ms_avg"] if data_sdbvh["step_ms_avg"] > 0 else 1.0

    print(f"   [CONCLUIDO em {elapsed:.1f}s] Contatos: Nat={data_nat['contacts_avg']:.1f} | SDBVH={data_sdbvh['contacts_avg']:.1f} "
          f"(Diff={abs(data_nat['contacts_avg'] - data_sdbvh['contacts_avg']):.1f}) | "
          f"BroadPhase Speedup: {bp_speedup:.2f}x | Step Speedup: {step_speedup:.2f}x", flush=True)

    return {
        "scene_id": scene_id,
        "scene_name": scene_name,
        "actors": scale,
        "steps": steps,
        "native_pairs_ms": data_nat["pairs_ms_avg"],
        "sdbvh_pairs_ms": data_sdbvh["pairs_ms_avg"],
        "bp_speedup": bp_speedup,
        "native_step_ms": data_nat["step_ms_avg"],
        "sdbvh_step_ms": data_sdbvh["step_ms_avg"],
        "step_speedup": step_speedup,
        "native_height": data_nat["height_avg"],
        "sdbvh_height": data_sdbvh["height_avg"],
        "native_contacts": data_nat["contacts_avg"],
        "sdbvh_contacts": data_sdbvh["contacts_avg"],
        "wall_time_s": elapsed
    }

def generate_html_report(results):
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Box3D - Relatório de Escala Completa (128 a 10.000 corpos)</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
        h1, h2, h3 {{ color: #38bdf8; }}
        .header {{ margin-bottom: 24px; padding-bottom: 12px; border-bottom: 1px solid #334155; }}
        .card {{ background-color: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }}
        th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background-color: #0f172a; color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 12px; }}
        tr:hover {{ background-color: #283548; }}
        .badge-win {{ background-color: #065f46; color: #34d399; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
        .badge-loss {{ background-color: #7f1d1d; color: #f87171; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
        .badge-parity {{ background-color: #374151; color: #9ca3af; padding: 4px 8px; border-radius: 4px; }}
        .metric-val {{ font-family: monospace; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Varredura de Escala Completa: Box3D Nativo vs SDBVH Otimizada</h1>
        <p>Configuração: 500 passos por teste | Threads: 1 (Execução simultânea e isolada por processo) | Escalas: 128, 256, 512, 1.000, 10.000 corpos</p>
    </div>

    <div class="card">
        <h2>Tabela Geral Consolidada</h2>
        <table>
            <thead>
                <tr>
                    <th>Cena</th>
                    <th>Corpos</th>
                    <th>Nativo Broad (ms)</th>
                    <th>SDBVH Broad (ms)</th>
                    <th>Speedup Broad</th>
                    <th>Nativo Step (ms)</th>
                    <th>SDBVH Step (ms)</th>
                    <th>Speedup Step</th>
                    <th>Altura (Nat / SDBVH)</th>
                    <th>Contatos (Nat / SDBVH)</th>
                </tr>
            </thead>
            <tbody>
    """

    for r in results:
        sp_bp = r["bp_speedup"]
        sp_st = r["step_speedup"]

        badge_bp = "badge-win" if sp_bp > 1.05 else ("badge-loss" if sp_bp < 0.95 else "badge-parity")
        badge_st = "badge-win" if sp_st > 1.05 else ("badge-loss" if sp_st < 0.95 else "badge-parity")

        html += f"""
                <tr>
                    <td><strong>{r['scene_name']}</strong></td>
                    <td>{r['actors']}</td>
                    <td class="metric-val">{r['native_pairs_ms']:.4f}</td>
                    <td class="metric-val">{r['sdbvh_pairs_ms']:.4f}</td>
                    <td><span class="{badge_bp}">{sp_bp:.2f}x</span></td>
                    <td class="metric-val">{r['native_step_ms']:.2f}</td>
                    <td class="metric-val">{r['sdbvh_step_ms']:.2f}</td>
                    <td><span class="{badge_st}">{sp_st:.2f}x</span></td>
                    <td class="metric-val">{r['native_height']:.0f} / {r['sdbvh_height']:.0f}</td>
                    <td class="metric-val">{r['native_contacts']:.0f} / {r['sdbvh_contacts']:.0f}</td>
                </tr>
        """

    html += """
            </tbody>
        </table>
    </div>
</body>
</html>
    """

    with open(HTML_REPORT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f">> Relatório HTML condensado gerado em: {HTML_REPORT}", flush=True)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("================================================================================")
    print(f"VARREDURA COMPLETA DE ESCALA SIMULTÂNEA: {SCALES}")
    print(f"Cenas: {', '.join([s['name'] for s in SCENES])}")
    print(f"Passos: {STEPS} | Workers: {WORKERS} (Processos Nativo e SDBVH rodando juntos)")
    print("================================================================================\n")

    all_results = []

    for s in SCENES:
        sid = s["id"]
        sname = s["name"]
        print(f"\n--- Iniciando Cena: {sname} ---")

        for scale in SCALES:
            res = run_pair_simultaneously(sid, sname, scale, STEPS, WORKERS)
            if res:
                all_results.append(res)

    if all_results:
        # Salva o resumo consolidado
        fieldnames = [
            "scene_id", "scene_name", "actors", "steps",
            "native_pairs_ms", "sdbvh_pairs_ms", "bp_speedup",
            "native_step_ms", "sdbvh_step_ms", "step_speedup",
            "native_height", "sdbvh_height",
            "native_contacts", "sdbvh_contacts", "wall_time_s"
        ]
        with open(CSV_SUMMARY, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in all_results:
                writer.writerow(r)
        print(f"\n>> Resumo consolidado salvo em: {CSV_SUMMARY}", flush=True)

        generate_html_report(all_results)

    print("\n================================================================================")
    print("SUÍTE DE ESCALA COMPLETA CONCLUÍDA COM SUCESSO!")
    print("================================================================================")

if __name__ == "__main__":
    main()
