#!/usr/bin/env python3
"""
tools/plot_benchmarks.py
Script de automação para análise estatística e plotagem comparativa.
Compara desempenho, custos SAH e razão de qualidade da DBVH vs Box3D vs Árvore Ideal.
Funciona 100% nativo com a biblioteca padrão do Python (gera tabelas e gráficos SVG/HTML)
e também gera imagens PNG de alta resolução caso matplotlib esteja disponível.
"""

import argparse
import csv
import glob
import math
import os
import sys

def parse_args():
    parser = argparse.ArgumentParser(description="Plota gráficos comparativos e estatísticas de benchmarks do Box3D / DBVH.")
    parser.add_argument("files", nargs="*", help="Arquivos CSV gerados pelo benchmark (ex: benchmark_results/*.csv)")
    parser.add_argument("--labels", nargs="*", help="Nomes/rótulos para a legenda de cada arquivo CSV")
    parser.add_argument("-o", "--output-dir", default="benchmark_results", help="Diretório onde os relatórios e gráficos serão salvos")
    return parser.parse_args()

def load_csv(filepath):
    data = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                if k not in data:
                    data[k] = []
                try:
                    data[k].append(float(v))
                except ValueError:
                    data[k].append(v)
    return data

def calc_mean(lst):
    return sum(lst) / len(lst) if lst else 0.0

def calc_max(lst):
    return max(lst) if lst else 0.0

def clean_label(filepath):
    base = os.path.splitext(os.path.basename(filepath))[0]
    base = base.replace("benchmark_", "").replace("results_", "")
    base = base.replace("_", " ").title()
    return base

def print_summary_table(datasets, labels):
    print("\n" + "="*105)
    print(" RESUMO ESTATÍSTICO DOS BENCHMARKS (TCC)")
    print("="*105)
    header = f"{'Configuração':<32} | {'Step Médio':<12} | {'Pairs Médio':<13} | {'SAH Padrão':<12} | {'Q_Standard':<12} | {'Q_Norm':<10}"
    print(header)
    print("-" * len(header))

    for i, (fname, data) in enumerate(datasets):
        name = labels[i] if i < len(labels) else clean_label(fname)
        step_mean = calc_mean(data.get('step_ms', []))
        pairs_mean = calc_mean(data.get('pairs_ms', []))
        sah_mean = calc_mean(data.get('sah_standard', []))
        
        q_std_vals = [x for x in data.get('quality_ratio_standard', []) if x > 0]
        q_norm_vals = [x for x in data.get('quality_ratio_normalized', []) if x > 0]

        q_std_mean = calc_mean(q_std_vals)
        q_norm_mean = calc_mean(q_norm_vals)

        q_std_str = f"{q_std_mean:.3f}x" if q_std_mean > 0 else "N/A"
        q_norm_str = f"{q_norm_mean:.3f}x" if q_norm_mean > 0 else "N/A"

        print(f"{name:<32} | {step_mean:<10.3f} ms | {pairs_mean:<10.3f} ms | {sah_mean:<12.1f} | {q_std_str:<12} | {q_norm_str:<10}")
    print("="*105 + "\n")

def generate_svg_chart(title, xlabel, ylabel, datasets, labels, key, ideal_key=None, width=850, height=460):
    colors = ['#1f77b4', '#d62728', '#2ca02c', '#9467bd', '#ff7f0e', '#8c564b', '#e377c2']
    margin_l, margin_r, margin_t, margin_b = 85, 200, 60, 60
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    all_x = []
    all_y = []
    for _, data in datasets:
        if 'frame' in data:
            all_x.extend(data['frame'])
        if key in data:
            all_y.extend(data[key])
        if ideal_key and ideal_key in data:
            all_y.extend(data[ideal_key])

    if not all_x or not all_y:
        return ""

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    if max_x == min_x: max_x += 1
    if max_y == min_y: max_y += 1
    min_y = min(0.0, min_y)

    def tx(x): return margin_l + (x - min_x) / (max_x - min_x) * plot_w
    def ty(y): return margin_t + plot_h - (y - min_y) / (max_y - min_y) * plot_h

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" class="chart-svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background:#ffffff; font-family:-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif;">']
    svg.append(f'<text x="{width/2}" y="35" text-anchor="middle" font-size="16" font-weight="bold" fill="#1a202c">{title}</text>')
    
    # Eixos
    svg.append(f'<line x1="{margin_l}" y1="{margin_t}" x2="{margin_l}" y2="{margin_t+plot_h}" stroke="#cbd5e1" stroke-width="1.5"/>')
    svg.append(f'<line x1="{margin_l}" y1="{margin_t+plot_h}" x2="{margin_l+plot_w}" y2="{margin_t+plot_h}" stroke="#cbd5e1" stroke-width="1.5"/>')

    # Grid e Labels Y
    for step in range(5):
        y_val = min_y + step * (max_y - min_y) / 4
        y_pos = ty(y_val)
        svg.append(f'<line x1="{margin_l}" y1="{y_pos}" x2="{margin_l+plot_w}" y2="{y_pos}" stroke="#f1f5f9" stroke-dasharray="4"/>')
        svg.append(f'<text x="{margin_l-10}" y="{y_pos+4}" text-anchor="end" font-size="11" fill="#64748b">{y_val:.2f}</text>')

    # Linhas dos Datasets com suporte a Hover e Destaque
    svg.append('<g class="lines-group">')
    legend_y = margin_t + 10
    legend_items = []

    for i, (fname, data) in enumerate(datasets):
        name = labels[i] if i < len(labels) else clean_label(fname)
        c = colors[i % len(colors)]
        s_id = f"series-{i}"
        if key in data and 'frame' in data:
            pts = " ".join([f"{tx(x):.1f},{ty(y):.1f}" for x, y in zip(data['frame'], data[key])])
            # Hit area invisivel mais larga (stroke 14px) para facilitar o hover com o mouse
            svg.append(f'<polyline class="hit-area" data-series="{s_id}" fill="none" stroke="transparent" stroke-width="14" points="{pts}"/>')
            # Linha visivel
            svg.append(f'<polyline class="series-line {s_id}" data-series="{s_id}" fill="none" stroke="{c}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="{pts}"/>')

        # Legenda interativa
        legend_items.append(f'<g class="legend-item" data-series="{s_id}">')
        legend_items.append(f'  <line class="legend-marker" x1="{margin_l+plot_w+20}" y1="{legend_y}" x2="{margin_l+plot_w+45}" y2="{legend_y}" stroke="{c}" stroke-width="3" stroke-linecap="round"/>')
        legend_items.append(f'  <text class="legend-text" x="{margin_l+plot_w+52}" y="{legend_y+4}" font-size="12" fill="#334155">{name}</text>')
        legend_items.append('</g>')
        legend_y += 24

    # Linha Ideal se existir
    if ideal_key and datasets and ideal_key in datasets[0][1]:
        data = datasets[0][1]
        pts = " ".join([f"{tx(x):.1f},{ty(y):.1f}" for x, y in zip(data['frame'], data[ideal_key])])
        s_id = "series-ideal"
        svg.append(f'<polyline class="hit-area" data-series="{s_id}" fill="none" stroke="transparent" stroke-width="14" points="{pts}"/>')
        svg.append(f'<polyline class="series-line {s_id}" data-series="{s_id}" fill="none" stroke="#0f172a" stroke-dasharray="5,5" stroke-width="2" points="{pts}"/>')
        legend_items.append(f'<g class="legend-item" data-series="{s_id}">')
        legend_items.append(f'  <line class="legend-marker" x1="{margin_l+plot_w+20}" y1="{legend_y}" x2="{margin_l+plot_w+45}" y2="{legend_y}" stroke="#0f172a" stroke-dasharray="4,4" stroke-width="2"/>')
        legend_items.append(f'  <text class="legend-text" x="{margin_l+plot_w+52}" y="{legend_y+4}" font-size="12" fill="#0f172a">Ideal (Full SAH)</text>')
        legend_items.append('</g>')

    svg.append('</g>') # Fecha lines-group
    svg.extend(legend_items)

    # Labels dos eixos
    svg.append(f'<text x="{margin_l+plot_w/2}" y="{height-15}" text-anchor="middle" font-size="13" fill="#475569">{xlabel}</text>')
    svg.append(f'<text transform="rotate(-90)" x="{-margin_t-plot_h/2}" y="25" text-anchor="middle" font-size="13" fill="#475569">{ylabel}</text>')
    svg.append('</svg>')

    return "\n".join(svg)

def export_html_dashboard(datasets, labels, output_dir):
    charts = [
        ("Tempo por Passo de Simulação (Step Time)", "Quadro (Frame)", "Tempo (ms)", "step_ms", None),
        ("Tempo da Broad-Phase (Find Pairs)", "Quadro (Frame)", "Tempo (ms)", "pairs_ms", None),
        ("Custo SAH Padrão vs Ideal", "Quadro (Frame)", "Custo SAH", "sah_standard", "ideal_sah_standard"),
        ("Custo SAH Normalizado vs Ideal", "Quadro (Frame)", "Custo Normalizado", "sah_normalized", "ideal_sah_normalized"),
        ("Razão de Qualidade Estrutural: Q(t) = C_Tree / C_Ideal", "Quadro (Frame)", "Q(t) (1.0 = Ideal)", "quality_ratio_standard", None),
        ("Razão de Qualidade Normalizada: Q_norm(t)", "Quadro (Frame)", "Q_norm(t) (1.0 = Ideal)", "quality_ratio_normalized", None),
        ("Altura da Árvore (Tree Height / Depth)", "Quadro (Frame)", "Níveis", "tree_height", "ideal_tree_height"),
    ]

    html = ["""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Relatório Comparativo de Broad-Phase (DBVH vs Box3D)</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }
        .container { max-width: 1100px; margin: 0 auto; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); padding: 36px; }
        h1 { color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 16px; margin-top: 0; }
        .hint-box { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; padding: 12px 18px; border-radius: 8px; margin-bottom: 24px; font-size: 14px; }
        .chart-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 28px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.04); position: relative; transition: box-shadow 0.2s ease; }
        .chart-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        table { width: 100%; border-collapse: collapse; margin-bottom: 32px; border-radius: 8px; overflow: hidden; }
        th, td { padding: 12px 18px; border: 1px solid #e2e8f0; text-align: left; }
        th { background: #f1f5f9; font-weight: 600; color: #334155; }
        tr:nth-child(even) { background: #f8fafc; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; background: #e0f2fe; color: #0369a1; }
        
        /* Interatividade de Destaque / Hover nos Gráficos */
        .series-line { transition: opacity 0.15s ease, stroke-width 0.15s ease, filter 0.15s ease; pointer-events: none; }
        .hit-area { cursor: pointer; pointer-events: stroke; }
        .legend-item { cursor: pointer; user-select: none; transition: opacity 0.15s ease; }
        .legend-item text { transition: fill 0.15s ease, font-weight 0.15s ease; }
        .legend-item:hover text { font-weight: 700; fill: #0f172a; }

        /* Estado de destaque ativo quando um modelo é focado */
        .chart-card.highlighting .series-line { opacity: 0.12 !important; }
        .chart-card.highlighting .legend-item { opacity: 0.30 !important; }
        .chart-card.highlighting .series-line.highlighted {
            opacity: 1.0 !important;
            stroke-width: 5.0px !important;
            filter: drop-shadow(0 2px 5px rgba(0,0,0,0.4));
        }
        .chart-card.highlighting .legend-item.highlighted { opacity: 1.0 !important; }
        .chart-card.highlighting .legend-item.highlighted text { font-weight: 700 !important; fill: #0f172a !important; }
        .chart-card.highlighting .legend-item.highlighted line { stroke-width: 5px !important; }
    </style>
</head>
<body>
<div class="container">
    <h1>Avaliação de Desempenho e Qualidade de Árvore (TCC)</h1>
    <div class="hint-box">
        💡 <strong>Dica de Interatividade:</strong> Passe o mouse sobre <strong>qualquer linha</strong> ou sobre os <strong>itens da legenda</strong> para destacar o modelo e trazer sua curva para o primeiro plano, facilitando a identificação em regiões onde os modelos se sobrepõem.
    </div>
"""]

    # Adiciona tabela HTML
    html.append("<h2>Resumo Estatístico Médio</h2>")
    html.append("<table><tr><th>Configuração</th><th>Step Médio (ms)</th><th>Pairs Médio (ms)</th><th>SAH Padrão</th><th>Q_Standard</th><th>Q_Normalized</th></tr>")
    for i, (fname, data) in enumerate(datasets):
        name = labels[i] if i < len(labels) else clean_label(fname)
        step_mean = calc_mean(data.get('step_ms', []))
        pairs_mean = calc_mean(data.get('pairs_ms', []))
        sah_mean = calc_mean(data.get('sah_standard', []))
        q_std_vals = [x for x in data.get('quality_ratio_standard', []) if x > 0]
        q_norm_vals = [x for x in data.get('quality_ratio_normalized', []) if x > 0]
        q_std_mean = calc_mean(q_std_vals)
        q_norm_mean = calc_mean(q_norm_vals)
        q_std_str = f"{q_std_mean:.3f}x" if q_std_mean > 0 else "N/A"
        q_norm_str = f"{q_norm_mean:.3f}x" if q_norm_mean > 0 else "N/A"
        html.append(f"<tr><td><strong>{name}</strong></td><td>{step_mean:.3f}</td><td>{pairs_mean:.3f}</td><td>{sah_mean:.1f}</td><td><span class='badge'>{q_std_str}</span></td><td><span class='badge'>{q_norm_str}</span></td></tr>")
    html.append("</table>")

    # Adiciona gráficos SVG
    for title, xlabel, ylabel, key, ideal_key in charts:
        svg_content = generate_svg_chart(title, xlabel, ylabel, datasets, labels, key, ideal_key)
        if svg_content:
            html.append(f'<div class="chart-card">{svg_content}</div>')

    # Adiciona JavaScript para destaque interativo e bring-to-front
    html.append("""<script>
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.chart-card').forEach(card => {
            const interactiveElements = card.querySelectorAll('[data-series]');
            interactiveElements.forEach(el => {
                const series = el.getAttribute('data-series');
                if (!series) return;

                el.addEventListener('mouseenter', () => {
                    card.classList.add('highlighting');
                    card.querySelectorAll('.' + series).forEach(target => {
                        target.classList.add('highlighted');
                        // Trazer o elemento SVG para frente para nao ficar coberto por outras linhas sobrepostas
                        if (target.parentNode) {
                            target.parentNode.appendChild(target);
                        }
                    });
                    card.querySelectorAll('.legend-item[data-series="' + series + '"]').forEach(leg => {
                        leg.classList.add('highlighted');
                    });
                });

                el.addEventListener('mouseleave', () => {
                    card.classList.remove('highlighting');
                    card.querySelectorAll('.highlighted').forEach(target => {
                        target.classList.remove('highlighted');
                    });
                });
            });
        });
    });
    </script>""")

    html.append("</div></body></html>")

    report_path = os.path.join(output_dir, "report_dashboard.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    print(f"Relatório HTML e Gráficos SVG gerados em: {report_path}")

def main():
    args = parse_args()
    file_list = []

    for pattern in args.files:
        matched = glob.glob(pattern)
        if matched:
            file_list.extend(matched)
        else:
            file_list.append(pattern)

    if not file_list:
        file_list = glob.glob("benchmark_results/*.csv")
        if not file_list:
            file_list = glob.glob("*.csv")

    if not file_list:
        print("Nenhum arquivo CSV encontrado em benchmark_results/ ou no diretório atual.")
        print("Execute o benchmark primeiro: .\\build\\bin\\benchmark.exe -b convex_pile -gt")
        return

    datasets = []
    for f in file_list:
        try:
            d = load_csv(f)
            if d:
                datasets.append((f, d))
        except Exception as e:
            print(f"Erro ao ler {f}: {e}")

    if not datasets:
        print("Nenhum dado válido carregado.")
        return

    labels = args.labels if args.labels else []
    os.makedirs(args.output_dir, exist_ok=True)
    print_summary_table(datasets, labels)
    export_html_dashboard(datasets, labels, args.output_dir)

if __name__ == "__main__":
    main()
