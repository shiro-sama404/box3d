#!/usr/bin/env python3
"""
tools/run_scale_benchmark.py
Script de automação para testes de escala assintótica (128 a 16.384 corpos)
compara Box3D Nativo vs DBVH com foco em redução de pares e complexidade temporal.
"""

import argparse
import csv
import math
import os
import subprocess
import sys
import time

DEFAULT_SCALES = [128, 256, 512, 1024, 2048, 4096, 8192, 16384]

def parse_args():
    parser = argparse.ArgumentParser(description="Executa benchmarks em escala de atores variáveis (128 a 16384 corpos).")
    parser.add_argument("--scene", "-b", default="convex_pile",
                        choices=["convex_pile", "many_pyramids", "spinner", "junkyard", "ragdoll_pile"],
                        help="Cena de benchmark a executar (padrão: convex_pile)")
    parser.add_argument("--actors", nargs="+", type=int, default=DEFAULT_SCALES,
                        help="Lista de contagens de atores a testar (padrão: 128 256 512 1024 2048 4096 8192 16384)")
    parser.add_argument("--steps", type=int, default=500,
                        help="Número de steps por execução (padrão: 500)")
    parser.add_argument("--repeats", "-r", type=int, default=1,
                        help="Número de repetições por configuração (padrão: 1)")
    parser.add_argument("--workers", "-w", type=int, default=1,
                        help="Número de threads de trabalho / workers (padrão: 1)")
    parser.add_argument("--exe", default=os.path.join("build", "bin", "benchmark.exe"),
                        help="Caminho do executável do benchmark")
    parser.add_argument("--output-dir", default="benchmark_results",
                        help="Diretório para saída dos CSVs e relatórios")
    parser.add_argument("--skip-native", action="store_true",
                        help="Pular execução do Box3D nativo")
    parser.add_argument("--skip-dbvh", action="store_true",
                        help="Pular execução da DBVH")
    parser.add_argument("--metric", choices=["area_ratio", "subtree_sah"], default="area_ratio",
                        help="Métrica de degradação da DBVH (padrão: area_ratio)")
    parser.add_argument("--threshold", type=float, default=1.50,
                        help="Limiar de rebuild da DBVH (padrão: 1.50)")
    parser.add_argument("--adaptive", choices=["on", "off"], default="on",
                        help="Habilita/desabilita o rebuild adaptativo da DBVH (padrão: on)")
    parser.add_argument("--max-leaves", type=int, default=64,
                        help="Limite máximo de folhas por subárvore reconstruída (padrão: 64)")
    return parser.parse_args()

def run_single_test(exe, benchmark_name, actors, steps, repeats, workers, broadphase, metric, threshold, adaptive, max_leaves, output_csv):
    cmd = [
        exe,
        f"-b={benchmark_name}",
        f"-a={actors}",
        f"--steps={steps}",
        f"-r={repeats}",
        f"-w={workers}",
        f"-bp={broadphase}",
        "-c",
        f"-o={output_csv}"
    ]
    if broadphase == "dbvh":
        cmd.append(f"-m={metric}")
        cmd.append(f"-th={threshold}")
        cmd.append(f"--adaptive={adaptive}")
        cmd.append(f"--max-subtree-leaves={max_leaves}")

    print(f"\n>> Executando: {' '.join(cmd)}")
    start_t = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start_t

    if res.returncode != 0:
        print(f"ERRO na execução (código {res.returncode}):")
        print(res.stderr or res.stdout)
        return False, elapsed

    print(f"   Concluído em {elapsed:.2f}s")
    return True, elapsed

def parse_csv_metrics(csv_path):
    if not os.path.exists(csv_path):
        return None

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    if not rows:
        return None

    def mean_col(col_name):
        vals = [float(r[col_name]) for r in rows if col_name in r and r[col_name] != ""]
        return sum(vals) / len(vals) if vals else 0.0

    return {
        "step_mean": mean_col("step_ms"),
        "pairs_mean": mean_col("pairs_ms"),
        "collide_mean": mean_col("collide_ms"),
        "solve_mean": mean_col("solve_ms"),
        "contact_mean": mean_col("contact_count"),
        "tree_height_final": int(float(rows[-1].get("tree_height", 0))),
        "tree_height_mean": mean_col("tree_height"),
        "sah_mean": mean_col("sah_normalized"),
        "q_norm_mean": mean_col("quality_ratio_normalized"),
        "rows_count": len(rows),
    }

def generate_svg_line_chart(series_list, title, x_label, y_label, x_values, width=760, height=360, log_scale_y=False):
    margin_l = 80
    margin_r = 40
    margin_t = 50
    margin_b = 60
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    all_y = []
    for s in series_list:
        all_y.extend([y for y in s["data"] if y is not None and y > 0])

    if not all_y:
        min_y, max_y = 0.1, 1.0
    else:
        min_y = min(all_y)
        max_y = max(all_y)

    if min_y == max_y:
        max_y *= 1.2
        min_y *= 0.8

    if not log_scale_y:
        min_y = 0.0

    def map_x(idx):
        if len(x_values) == 1:
            return margin_l + plot_w / 2
        return margin_l + idx * (plot_w / (len(x_values) - 1))

    def map_y(val):
        if val is None or val <= 0:
            return margin_t + plot_h
        if log_scale_y:
            log_min = math.log10(max(1e-4, min_y))
            log_max = math.log10(max(1e-3, max_y))
            norm = (math.log10(val) - log_min) / (log_max - log_min + 1e-9)
        else:
            norm = (val - min_y) / (max_y - min_y + 1e-9)
        norm = max(0.0, min(1.0, norm))
        return margin_t + plot_h - norm * plot_h

    svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" style="background:#181825;border-radius:12px;margin:10px 0;">']
    svg.append(f'<text x="{width/2}" y="30" fill="#cdd6f4" font-size="16" font-weight="bold" font-family="system-ui,sans-serif" text-anchor="middle">{title}</text>')

    # Grid & Y ticks
    num_y_ticks = 5
    for i in range(num_y_ticks + 1):
        if log_scale_y:
            log_min = math.log10(max(1e-4, min_y))
            log_max = math.log10(max(1e-3, max_y))
            tick_val = 10 ** (log_min + i * (log_max - log_min) / num_y_ticks)
        else:
            tick_val = min_y + i * (max_y - min_y) / num_y_ticks
        y_pos = map_y(tick_val)
        svg.append(f'<line x1="{margin_l}" y1="{y_pos}" x2="{width - margin_r}" y2="{y_pos}" stroke="#313244" stroke-dasharray="4,4"/>')
        fmt = f"{tick_val:.2f}" if tick_val < 10 else f"{tick_val:.1f}"
        svg.append(f'<text x="{margin_l - 12}" y="{y_pos + 4}" fill="#a6adc8" font-size="11" font-family="system-ui,sans-serif" text-anchor="end">{fmt}</text>')

    # X axis ticks & labels
    svg.append(f'<line x1="{margin_l}" y1="{margin_t + plot_h}" x2="{width - margin_r}" y2="{margin_t + plot_h}" stroke="#45475a" stroke-width="1.5"/>')
    for idx, xv in enumerate(x_values):
        xp = map_x(idx)
        svg.append(f'<line x1="{xp}" y1="{margin_t + plot_h}" x2="{xp}" y2="{margin_t + plot_h + 6}" stroke="#45475a"/>')
        svg.append(f'<text x="{xp}" y="{margin_t + plot_h + 22}" fill="#a6adc8" font-size="11" font-family="system-ui,sans-serif" text-anchor="middle">{xv}</text>')

    svg.append(f'<text x="{width/2}" y="{height - 12}" fill="#bac2de" font-size="12" font-family="system-ui,sans-serif" text-anchor="middle">{x_label}</text>')
    svg.append(f'<text transform="rotate(-90)" x="{-height/2}" y="22" fill="#bac2de" font-size="12" font-family="system-ui,sans-serif" text-anchor="middle">{y_label}</text>')

    # Series lines & dots
    for s in series_list:
        color = s["color"]
        points = []
        for idx, yv in enumerate(s["data"]):
            if yv is not None:
                xp = map_x(idx)
                yp = map_y(yv)
                points.append((xp, yp))

        if len(points) > 1:
            pts_str = " ".join([f"{x:.1f},{y:.1f}" for x, y in points])
            svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{pts_str}"/>')

        for xp, yp in points:
            svg.append(f'<circle cx="{xp:.1f}" cy="{yp:.1f}" r="4.5" fill="{color}" stroke="#181825" stroke-width="1.5"/>')

    # Legend
    leg_x = margin_l + 10
    leg_y = margin_t + 16
    for idx, s in enumerate(series_list):
        lx = leg_x + idx * 160
        svg.append(f'<line x1="{lx}" y1="{leg_y}" x2="{lx + 20}" y2="{leg_y}" stroke="{s["color"]}" stroke-width="3"/>')
        svg.append(f'<circle cx="{lx + 10}" cy="{leg_y}" r="3.5" fill="{s["color"]}"/>')
        svg.append(f'<text x="{lx + 26}" y="{leg_y + 4}" fill="#cdd6f4" font-size="11" font-family="system-ui,sans-serif">{s["name"]}</text>')

    svg.append('</svg>')
    return "\n".join(svg)

def generate_html_report(results, output_html):
    actors_list = [r["actors"] for r in results]

    # Data series for charts
    native_pairs = [r.get("native", {}).get("pairs_mean") for r in results]
    dbvh_pairs = [r.get("dbvh", {}).get("pairs_mean") for r in results]

    native_contacts = [r.get("native", {}).get("contact_mean") for r in results]
    dbvh_contacts = [r.get("dbvh", {}).get("contact_mean") for r in results]

    native_step = [r.get("native", {}).get("step_mean") for r in results]
    dbvh_step = [r.get("dbvh", {}).get("step_mean") for r in results]

    native_height = [r.get("native", {}).get("tree_height_final") for r in results]
    dbvh_height = [r.get("dbvh", {}).get("tree_height_final") for r in results]

    svg_pairs = generate_svg_line_chart([
        {"name": "Box3D Nativo", "color": "#f38ba8", "data": native_pairs},
        {"name": "DBVH", "color": "#89b4fa", "data": dbvh_pairs},
    ], "Tempo de Broad-Phase: Pairs (ms) vs Quantidade de Atores", "Número de Corpos (Atores)", "Tempo Médio Pairs (ms)", actors_list)

    svg_contacts = generate_svg_line_chart([
        {"name": "Box3D Nativo", "color": "#f38ba8", "data": native_contacts},
        {"name": "DBVH", "color": "#a6e3a1", "data": dbvh_contacts},
    ], "Redução de Pares: Contatos Ativos Médios vs Quantidade de Atores", "Número de Corpos (Atores)", "Média de Contatos/Pares", actors_list)

    svg_step = generate_svg_line_chart([
        {"name": "Box3D Nativo", "color": "#f38ba8", "data": native_step},
        {"name": "DBVH", "color": "#fab387", "data": dbvh_step},
    ], "Tempo Total de Simulação: Step (ms) vs Quantidade de Atores", "Número de Corpos (Atores)", "Tempo Médio Step (ms)", actors_list)

    svg_height = generate_svg_line_chart([
        {"name": "Box3D Nativo", "color": "#f38ba8", "data": native_height},
        {"name": "DBVH", "color": "#cba6f7", "data": dbvh_height},
    ], "Qualidade Topológica: Altura da Árvore vs Quantidade de Atores", "Número de Corpos (Atores)", "Altura da Árvore (H)", actors_list)

    # HTML structure
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Relatório de Escalabilidade Assintótica - Box3D vs DBVH</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #11111b; color: #cdd6f4; margin: 0; padding: 24px; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ color: #89b4fa; font-size: 26px; border-bottom: 2px solid #313244; padding-bottom: 12px; margin-bottom: 20px; }}
  h2 {{ color: #f9e2af; font-size: 20px; margin-top: 30px; }}
  .card {{ background: #1e1e2e; border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); border: 1px solid #313244; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
  th, td {{ padding: 10px 12px; text-align: right; border-bottom: 1px solid #313244; }}
  th {{ background: #181825; color: #a6adc8; font-weight: 600; }}
  th:first-child, td:first-child {{ text-align: left; }}
  tr:hover {{ background: #24273a; }}
  .badge-win {{ color: #a6e3a1; font-weight: bold; }}
  .badge-loss {{ color: #f38ba8; }}
  .chart-grid {{ display: grid; grid-template-columns: 1fr; gap: 20px; }}
  @media (min-width: 900px) {{ .chart-grid {{ grid-template-columns: 1fr 1fr; }} }}
  .chart-box {{ background: #181825; border-radius: 12px; padding: 12px; display: flex; justify-content: center; }}
</style>
</head>
<body>
<div class="container">
  <h1>Relatório de Escalabilidade Assintótica: DBVH vs Box3D Nativo</h1>
  <div class="card">
    <p>Comparativo sistemático de desempenho entre a <strong>DBVH (Árvore Dinâmica Otimizada por SAH)</strong> e a <strong>b3DynamicTree nativa do Box3D</strong> com quantidade variável de atores de 128 a 16.384 corpos.</p>
    <table>
      <thead>
        <tr>
          <th>Atores (N)</th>
          <th>Pairs Nativo (ms)</th>
          <th>Pairs DBVH (ms)</th>
          <th>Speedup Pairs</th>
          <th>Contatos Nativo</th>
          <th>Contatos DBVH</th>
          <th>Step Nativo (ms)</th>
          <th>Step DBVH (ms)</th>
          <th>H Nativo</th>
          <th>H DBVH</th>
        </tr>
      </thead>
      <tbody>
"""
    for r in results:
        n = r["actors"]
        nat = r.get("native", {})
        db = r.get("dbvh", {})

        p_nat = nat.get("pairs_mean", 0.0)
        p_db = db.get("pairs_mean", 0.0)
        speedup = f"{p_nat / p_db:.2f}x" if p_db > 0 and p_nat > 0 else "-"
        win_class = "badge-win" if p_db < p_nat else "badge-loss"

        c_nat = f"{nat.get('contact_mean', 0):.0f}" if nat else "-"
        c_db = f"{db.get('contact_mean', 0):.0f}" if db else "-"

        s_nat = f"{nat.get('step_mean', 0.0):.2f}" if nat else "-"
        s_db = f"{db.get('step_mean', 0.0):.2f}" if db else "-"

        h_nat = nat.get("tree_height_final", "-") if nat else "-"
        h_db = db.get("tree_height_final", "-") if db else "-"

        html += f"""        <tr>
          <td><strong>{n:,}</strong></td>
          <td>{p_nat:.4f}</td>
          <td>{p_db:.4f}</td>
          <td class="{win_class}">{speedup}</td>
          <td>{c_nat}</td>
          <td>{c_db}</td>
          <td>{s_nat}</td>
          <td>{s_db}</td>
          <td>{h_nat}</td>
          <td>{h_db}</td>
        </tr>
"""

    html += f"""      </tbody>
    </table>
  </div>

  <h2>Curvas Assintóticas e Comportamento em Escala</h2>
  <div class="chart-grid">
    <div class="chart-box">{svg_pairs}</div>
    <div class="chart-box">{svg_contacts}</div>
    <div class="chart-box">{svg_step}</div>
    <div class="chart-box">{svg_height}</div>
  </div>
</div>
</body>
</html>
"""
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n>> Dashboard HTML gerado em: {output_html}")

def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    print("=" * 70)
    print(" INICIANDO SWEEP DE ESCALA DE ATORES (Box3D vs DBVH)")
    print(f" Escalas: {args.actors}")
    print(f" Steps por teste: {args.steps} | Repetições: {args.repeats} | Workers: {args.workers}")
    print("=" * 70)

    summary_results = []

    for actors in args.actors:
        print(f"\n==================== ESCALA: {actors} ATORES ====================")
        res_entry = {"actors": actors}

        # Box3D
        if not args.skip_native:
            csv_nat = os.path.join(args.output_dir, f"scale_{args.scene}_{actors}_native.csv")
            ok, _ = run_single_test(
                args.exe, args.scene, actors, args.steps, args.repeats, args.workers,
                "native", "area_ratio", args.threshold, args.adaptive, args.max_leaves, csv_nat
            )
            if ok:
                res_entry["native"] = parse_csv_metrics(csv_nat)

        # SDBVH
        if not args.skip_dbvh:
            csv_dbvh = os.path.join(args.output_dir, f"scale_{args.scene}_{actors}_dbvh_{args.metric}.csv")
            ok, _ = run_single_test(
                args.exe, args.scene, actors, args.steps, args.repeats, args.workers,
                "dbvh", args.metric, args.threshold, args.adaptive, args.max_leaves, csv_dbvh
            )
            if ok:
                res_entry["dbvh"] = parse_csv_metrics(csv_dbvh)

        summary_results.append(res_entry)

    # Export Summary CSV
    summary_csv = os.path.join(args.output_dir, f"scale_sweep_{args.scene}_summary.csv")
    with open(summary_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "actors",
            "native_pairs_ms", "dbvh_pairs_ms", "pairs_speedup",
            "native_contacts", "dbvh_contacts",
            "native_step_ms", "dbvh_step_ms",
            "native_collide_ms", "dbvh_collide_ms",
            "native_tree_height", "dbvh_tree_height"
        ])
        for r in summary_results:
            n = r["actors"]
            nat = r.get("native") or {}
            db = r.get("dbvh") or {}
            p_nat = nat.get("pairs_mean", 0.0)
            p_db = db.get("pairs_mean", 0.0)
            speedup = (p_nat / p_db) if p_db > 0 else 0.0
            writer.writerow([
                n,
                f"{p_nat:.4f}", f"{p_db:.4f}", f"{speedup:.2f}",
                f"{nat.get('contact_mean', 0.0):.1f}", f"{db.get('contact_mean', 0.0):.1f}",
                f"{nat.get('step_mean', 0.0):.4f}", f"{db.get('step_mean', 0.0):.4f}",
                f"{nat.get('collide_mean', 0.0):.4f}", f"{db.get('collide_mean', 0.0):.4f}",
                nat.get("tree_height_final", 0), db.get("tree_height_final", 0)
            ])
    print(f"\n>> Resumo consolidado salvo em: {summary_csv}")

    # Generate HTML Dashboard
    html_file = os.path.join(args.output_dir, f"scale_report_{args.scene}_dashboard.html")
    generate_html_report(summary_results, html_file)

    # Print summary table
    print("\n" + "=" * 95)
    print(" RESUMO FINAL DE ESCALABILIDADE")
    print("=" * 95)
    header = f"{'Atores':<8} | {'Pairs Nat (ms)':<14} | {'Pairs DBVH (ms)':<15} | {'Speedup':<9} | {'Contatos Nat':<12} | {'Contatos DBVH':<13} | {'H Nat':<6} | {'H DBVH':<6}"
    print(header)
    print("-" * len(header))
    for r in summary_results:
        n = r["actors"]
        nat = r.get("native") or {}
        db = r.get("dbvh") or {}
        p_nat = nat.get("pairs_mean", 0.0)
        p_db = db.get("pairs_mean", 0.0)
        speedup = f"{p_nat / p_db:.2f}x" if p_db > 0 and p_nat > 0 else "-"
        c_nat = f"{nat.get('contact_mean', 0.0):.0f}"
        c_db = f"{db.get('contact_mean', 0.0):.0f}"
        h_nat = nat.get("tree_height_final", "-")
        h_db = db.get("tree_height_final", "-")
        print(f"{n:<8} | {p_nat:<14.4f} | {p_db:<15.4f} | {speedup:<9} | {c_nat:<12} | {c_db:<13} | {h_nat:<6} | {h_db:<6}")
    print("=" * 95)

if __name__ == "__main__":
    main()
