#!/usr/bin/env python3
"""
tools/generate_condensed_report.py
Lê os CSVs já gerados em benchmark_results/ e compila o relatório HTML
em layout ultra-condensado, horizontal e executivo (Widescreen Dashboard).
"""

import os
import csv
import json
import time

OUTPUT_DIR = "benchmark_results"
HTML_OUTPUT = os.path.join(OUTPUT_DIR, "relatorio_benchmark_1k_10k.html")
SUMMARY_CSV = os.path.join(OUTPUT_DIR, "summary_scale_1k_10k_all_scenes.csv")

SCENES = [
    {"id": "convex_pile", "name": "Convex Pile"},
    {"id": "many_pyramids", "name": "Many Pyramids"},
    {"id": "spinner", "name": "Spinner"},
    {"id": "junkyard", "name": "Junkyard"},
    {"id": "ragdoll_pile", "name": "Ragdoll Pile"}
]

def load_summary():
    if not os.path.exists(SUMMARY_CSV):
        print(f"Erro: {SUMMARY_CSV} não encontrado.")
        return []

    rows = []
    with open(SUMMARY_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "scene_id": r["scene_id"],
                "scene_name": r["scene_name"],
                "actors": int(r["actors"]),
                "steps": int(r["steps"]),
                "native_pairs_ms": float(r["native_pairs_ms"]),
                "sdbvh_pairs_ms": float(r["sdbvh_pairs_ms"]),
                "bp_speedup": float(r["bp_speedup"]),
                "native_step_ms": float(r["native_step_ms"]),
                "sdbvh_step_ms": float(r["sdbvh_step_ms"]),
                "step_speedup": float(r["step_speedup"]),
                "native_height": float(r["native_height"]),
                "sdbvh_height": float(r["sdbvh_height"]),
                "native_contacts": float(r["native_contacts"]),
                "sdbvh_contacts": float(r["sdbvh_contacts"]),
            })
    return rows

def generate_condensed_html():
    summary_rows = load_summary()
    if not summary_rows:
        return

    # Prepare datasets for Chart.js
    scenes_labels = [s["name"] for s in SCENES]
    
    scale_1k_bp_speedup = []
    scale_10k_bp_speedup = []
    scale_1k_step_speedup = []
    scale_10k_step_speedup = []

    pairs_10k_nat = []
    pairs_10k_sd = []
    step_10k_nat = []
    step_10k_sd = []

    for s in SCENES:
        sid = s["id"]
        # Find 1k and 10k rows
        r_1k = next((r for r in summary_rows if r["scene_id"] == sid and r["actors"] == 1000), None)
        r_10k = next((r for r in summary_rows if r["scene_id"] == sid and r["actors"] == 10000), None)

        scale_1k_bp_speedup.append(round(r_1k["bp_speedup"], 2) if r_1k else 1.0)
        scale_10k_bp_speedup.append(round(r_10k["bp_speedup"], 2) if r_10k else 1.0)
        scale_1k_step_speedup.append(round(r_1k["step_speedup"], 2) if r_1k else 1.0)
        scale_10k_step_speedup.append(round(r_10k["step_speedup"], 2) if r_10k else 1.0)

        pairs_10k_nat.append(round(r_10k["native_pairs_ms"], 2) if r_10k else 0.0)
        pairs_10k_sd.append(round(r_10k["sdbvh_pairs_ms"], 2) if r_10k else 0.0)
        step_10k_nat.append(round(r_10k["native_step_ms"], 1) if r_10k else 0.0)
        step_10k_sd.append(round(r_10k["sdbvh_step_ms"], 1) if r_10k else 0.0)

    # Global KPI numbers
    max_bp_speedup = max(r["bp_speedup"] for r in summary_rows)
    max_step_speedup = max(r["step_speedup"] for r in summary_rows)
    avg_bp_speedup = sum(r["bp_speedup"] for r in summary_rows) / len(summary_rows)
    avg_step_speedup = sum(r["step_speedup"] for r in summary_rows) / len(summary_rows)

    chart_payload = {
        "scenes": scenes_labels,
        "bp_1k": scale_1k_bp_speedup,
        "bp_10k": scale_10k_bp_speedup,
        "step_1k": scale_1k_step_speedup,
        "step_10k": scale_10k_step_speedup,
        "pairs_10k_nat": pairs_10k_nat,
        "pairs_10k_sd": pairs_10k_sd,
        "step_10k_nat": step_10k_nat,
        "step_10k_sd": step_10k_sd
    }

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Box3D Nativo vs SDBVH (1k & 10k Corpos) - Relatório Executivo</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg: #090d16;
            --card-bg: rgba(16, 24, 39, 0.7);
            --card-hover: rgba(26, 36, 56, 0.85);
            --border: rgba(255, 255, 255, 0.08);
            --border-highlight: rgba(99, 102, 241, 0.35);
            --primary: #6366f1;
            --cyan: #06b6d4;
            --emerald: #10b981;
            --rose: #f43f5e;
            --amber: #f59e0b;
            --text: #f8fafc;
            --text-sec: #94a3b8;
            --text-mut: #64748b;
            --font-sans: 'Inter', -apple-system, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            background-color: var(--bg);
            color: var(--text);
            font-family: var(--font-sans);
            padding: 0.85rem 1.25rem;
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 10% 10%, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 90% 90%, rgba(6, 182, 212, 0.06) 0%, transparent 40%);
        }}

        .dashboard-container {{
            max-width: 1720px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 0.85rem;
        }}

        /* Top Executive Bar (Header + KPIs horizontal) */
        .top-executive-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 0.65rem;
            padding: 0.65rem 1.15rem;
            backdrop-filter: blur(12px);
            gap: 1.5rem;
        }}

        .header-brand {{
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
        }}

        .brand-pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #818cf8;
        }}

        .brand-title {{
            font-size: 1.25rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .brand-title span {{
            color: var(--text-sec);
            font-weight: 400;
            font-size: 0.85rem;
        }}

        .kpi-row {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .kpi-pill {{
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--border);
            border-radius: 0.5rem;
            padding: 0.35rem 0.75rem;
            display: flex;
            align-items: baseline;
            gap: 0.45rem;
            transition: border-color 0.2s;
        }}

        .kpi-pill:hover {{
            border-color: var(--border-highlight);
        }}

        .kpi-pill-label {{
            font-size: 0.68rem;
            font-weight: 600;
            color: var(--text-mut);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            white-space: nowrap;
        }}

        .kpi-pill-val {{
            font-family: var(--font-mono);
            font-size: 1.25rem;
            font-weight: 800;
            color: #ffffff;
            white-space: nowrap;
        }}

        .kpi-pill-val.green {{ color: #34d399; }}
        .kpi-pill-val.amber {{ color: #fbbf24; }}
        .kpi-pill-val.cyan {{ color: #38bdf8; }}
        .kpi-pill-val.indigo {{ color: #a5b4fc; }}

        /* Horizontal 4-Column Charts Strip */
        .charts-strip {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 0.85rem;
        }}

        @media (max-width: 1280px) {{
            .charts-strip {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        .chart-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 0.65rem;
            padding: 0.75rem 0.95rem;
            backdrop-filter: blur(12px);
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }}

        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .chart-header h3 {{
            font-size: 0.78rem;
            font-weight: 700;
            color: #e2e8f0;
            letter-spacing: -0.01em;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }}

        .chart-badge {{
            font-size: 0.65rem;
            font-weight: 700;
            padding: 0.15rem 0.45rem;
            border-radius: 0.3rem;
            font-family: var(--font-mono);
        }}

        .badge-green {{ background: rgba(16, 185, 129, 0.15); color: #34d399; }}
        .badge-cyan {{ background: rgba(6, 182, 212, 0.15); color: #38bdf8; }}
        .badge-amber {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; }}
        .badge-indigo {{ background: rgba(99, 102, 241, 0.15); color: #a5b4fc; }}

        .chart-wrapper {{
            position: relative;
            height: 180px;
            width: 100%;
        }}

        /* Compact Data Matrix Table */
        .table-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 0.65rem;
            padding: 0.75rem 1.15rem;
            backdrop-filter: blur(12px);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }}

        .table-header-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.65rem;
        }}

        .table-title {{
            font-size: 0.85rem;
            font-weight: 700;
            color: #f1f5f9;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .table-responsive {{
            overflow-x: auto;
            border-radius: 0.45rem;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.78rem;
            text-align: left;
        }}

        th {{
            background: rgba(15, 23, 42, 0.95);
            color: var(--text-sec);
            font-weight: 700;
            text-transform: uppercase;
            font-size: 0.68rem;
            letter-spacing: 0.05em;
            padding: 0.45rem 0.65rem;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}

        td {{
            padding: 0.35rem 0.65rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            color: var(--text);
            white-space: nowrap;
        }}

        tr:nth-child(even) td {{
            background: rgba(255, 255, 255, 0.015);
        }}

        tr:hover td {{
            background: rgba(99, 102, 241, 0.08);
        }}

        .num {{ font-family: var(--font-mono); }}

        .badge-scene {{ font-weight: 700; color: #ffffff; }}

        .badge-scale {{
            display: inline-flex;
            padding: 0.1rem 0.4rem;
            border-radius: 0.25rem;
            font-family: var(--font-mono);
            font-size: 0.68rem;
            font-weight: 700;
            background: rgba(71, 85, 105, 0.4);
            color: #cbd5e1;
        }}

        .badge-scale.scale-10k {{
            background: rgba(99, 102, 241, 0.2);
            color: #c7d2fe;
            border: 1px solid rgba(99, 102, 241, 0.4);
        }}

        .speedup {{
            display: inline-flex;
            align-items: center;
            font-family: var(--font-mono);
            font-weight: 700;
            padding: 0.15rem 0.45rem;
            border-radius: 0.3rem;
            font-size: 0.75rem;
        }}

        .speedup.high {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); }}
        .speedup.mid {{ background: rgba(6, 182, 212, 0.2); color: #38bdf8; border: 1px solid rgba(6, 182, 212, 0.35); }}
        .speedup.low {{ background: rgba(148, 163, 184, 0.1); color: #94a3b8; }}

        /* Horizontal 3-Column Compact Insights */
        .insights-strip {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.85rem;
        }}

        @media (max-width: 1024px) {{
            .insights-strip {{
                grid-template-columns: 1fr;
            }}
        }}

        .insight-pill {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 0.65rem;
            padding: 0.65rem 0.95rem;
            border-left: 3px solid var(--primary);
            font-size: 0.74rem;
            line-height: 1.45;
            color: var(--text-sec);
        }}

        .insight-pill.green {{ border-left-color: var(--emerald); }}
        .insight-pill.cyan {{ border-left-color: var(--cyan); }}
        .insight-pill.amber {{ border-left-color: var(--amber); }}

        .insight-pill strong {{ color: #f8fafc; font-size: 0.78rem; display: block; margin-bottom: 0.15rem; }}

        footer {{
            text-align: center;
            color: var(--text-mut);
            font-size: 0.7rem;
            padding-top: 0.25rem;
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- 1. Top Executive Bar -->
        <header class="top-executive-bar">
            <div class="header-brand">
                <div class="brand-pill">TCC FACOM / UFMS &bull; SDBVH Research Benchmark</div>
                <div class="brand-title">
                    Box3D Nativo vs SDBVH
                    <span>| Avaliação Comparativa de Escala (1.000 e 10.000 Corpos)</span>
                </div>
            </div>
            <div class="kpi-row">
                <div class="kpi-pill">
                    <span class="kpi-pill-label">Speedup Máx. Step</span>
                    <span class="kpi-pill-val amber">{max_step_speedup:.2f}&times;</span>
                </div>
                <div class="kpi-pill">
                    <span class="kpi-pill-label">Speedup Máx. Pairs</span>
                    <span class="kpi-pill-val cyan">{max_bp_speedup:.2f}&times;</span>
                </div>
                <div class="kpi-pill">
                    <span class="kpi-pill-label">Média Global Step</span>
                    <span class="kpi-pill-val green">{avg_step_speedup:.2f}&times;</span>
                </div>
                <div class="kpi-pill">
                    <span class="kpi-pill-label">Média Global Pairs</span>
                    <span class="kpi-pill-val indigo">{avg_bp_speedup:.2f}&times;</span>
                </div>
            </div>
        </header>

        <!-- 2. Horizontal 4-Column Charts Strip -->
        <section class="charts-strip">
            <!-- Chart 1: Broadphase Speedup -->
            <div class="chart-card">
                <div class="chart-header">
                    <h3>Speedup Fase Ampla (Pairs)</h3>
                    <span class="chart-badge badge-cyan">Broad-Phase</span>
                </div>
                <div class="chart-wrapper">
                    <canvas id="chartBpSpeedup"></canvas>
                </div>
            </div>

            <!-- Chart 2: Step Speedup -->
            <div class="chart-card">
                <div class="chart-header">
                    <h3>Speedup Global do Passo</h3>
                    <span class="chart-badge badge-amber">Total Step</span>
                </div>
                <div class="chart-wrapper">
                    <canvas id="chartStepSpeedup"></canvas>
                </div>
            </div>

            <!-- Chart 3: Pairs Time 10k -->
            <div class="chart-card">
                <div class="chart-header">
                    <h3>Tempo Broad-Phase (10k)</h3>
                    <span class="chart-badge badge-indigo">ms (Menor = Melhor)</span>
                </div>
                <div class="chart-wrapper">
                    <canvas id="chartBpTime"></canvas>
                </div>
            </div>

            <!-- Chart 4: Step Time 10k -->
            <div class="chart-card">
                <div class="chart-header">
                    <h3>Tempo Total Step (10k)</h3>
                    <span class="chart-badge badge-green">ms (Menor = Melhor)</span>
                </div>
                <div class="chart-wrapper">
                    <canvas id="chartStepTime"></canvas>
                </div>
            </div>
        </section>

        <!-- 3. Compact Data Matrix Table -->
        <section class="table-card">
            <div class="table-header-row">
                <div class="table-title">
                    Matriz Comparativa Completa de Desempenho e Degradação
                </div>
                <span style="font-size: 0.7rem; color: var(--text-mut);">Planejamento de Longo Prazo: 1.000 passos (1k corpos) e 500 passos (10k corpos) &bull; Single-threaded CPU</span>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Cena</th>
                            <th>Escala</th>
                            <th>Passos</th>
                            <th>Pairs Nativo</th>
                            <th>Pairs SDBVH</th>
                            <th>Speedup Pairs</th>
                            <th>Step Nativo</th>
                            <th>Step SDBVH</th>
                            <th>Speedup Step</th>
                            <th>Altura (Nat / SD)</th>
                            <th>Contatos Médios (Nat / SD)</th>
                        </tr>
                    </thead>
                    <tbody>
"""

    for r in summary_rows:
        bp_cls = "high" if r["bp_speedup"] >= 2.0 else ("mid" if r["bp_speedup"] >= 1.25 else "low")
        step_cls = "high" if r["step_speedup"] >= 1.5 else ("mid" if r["step_speedup"] >= 1.15 else "low")
        scale_cls = "scale-10k" if r["actors"] == 10000 else ""
        
        html += f"""                        <tr>
                            <td><strong class="badge-scene">{r['scene_name']}</strong></td>
                            <td><span class="badge-scale {scale_cls}">{r['actors']}</span></td>
                            <td class="num">{r['steps']}</td>
                            <td class="num">{r['native_pairs_ms']:.3f} ms</td>
                            <td class="num">{r['sdbvh_pairs_ms']:.3f} ms</td>
                            <td><span class="speedup {bp_cls}">{r['bp_speedup']:.2f}&times;</span></td>
                            <td class="num">{r['native_step_ms']:.2f} ms</td>
                            <td class="num">{r['sdbvh_step_ms']:.2f} ms</td>
                            <td><span class="speedup {step_cls}">{r['step_speedup']:.2f}&times;</span></td>
                            <td class="num">{r['native_height']:.0f} / {r['sdbvh_height']:.0f}</td>
                            <td class="num">{r['native_contacts']:.0f} &rarr; {r['sdbvh_contacts']:.0f}</td>
                        </tr>
"""

    html += f"""                    </tbody>
                </table>
            </div>
        </section>

        <!-- 4. Horizontal 3-Column Compact Insights -->
        <section class="insights-strip">
            <div class="insight-pill green">
                <strong>Contenção Drástica da Altura da Árvore</strong>
                No longo prazo (500 a 1.000 passos), a árvore nativa degradou severamente por permutações locais acumuladas, inflando até <strong>H = 29,7</strong> em Convex Pile 10k e <strong>H = 26,0</strong> em Ragdoll Pile 10k. A SDBVH impediu esse colapso topológico, estabilizando a hierarquia entre <strong>H = 12 e 18</strong> (próxima ao limite logarítmico ideal).
            </div>
            <div class="insight-pill cyan">
                <strong>Eficiência Sustentada em Stacking e Articulados</strong>
                Em Many Pyramids, a SDBVH sustentou speedup global de <strong>1,31&times; (1k)</strong> e <strong>1,19&times; (10k)</strong> ao longo de centenas de quadros, reduzindo em milhares os contatos espúrios. Em Ragdoll Pile (11.600+ juntas), a SDBVH reduziu em <strong>27%</strong> a contagem de contatos (de 19.413 para 14.154), aliviando a narrow-phase.
            </div>
            <div class="insight-pill amber">
                <strong>Trade-off em Agitação Perpétua Prolongada</strong>
                Em regimes caóticos perpétuos sem repouso (Spinner 10k por 500 passos), a repenetração caótica massiva e o custo cumulativo de reconstruções amortizadas revelam o limite do rebuild automático sob sobreposição volumétrica extrema, apontando a necessidade de histerese adaptativa dinâmica.
            </div>
        </section>

        <footer>
            Monografia de TCC &bull; Departamento de Computação &bull; UFMS &bull; Dados brutos exportados em <code>benchmark_results/</code>
        </footer>
    </div>

    <script>
        const data = {json.dumps(chart_payload)};

        const chartDefaults = {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{
                    labels: {{
                        color: '#94a3b8',
                        font: {{ family: 'Inter', size: 10 }},
                        boxWidth: 10,
                        padding: 6
                    }}
                }},
                tooltip: {{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#ffffff',
                    bodyColor: '#cbd5e1',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 6,
                    bodyFont: {{ family: 'JetBrains Mono', size: 10 }}
                }}
            }},
            scales: {{
                x: {{
                    grid: {{ display: false }},
                    ticks: {{ color: '#94a3b8', font: {{ family: 'Inter', size: 9 }} }}
                }},
                y: {{
                    grid: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                    ticks: {{ color: '#94a3b8', font: {{ family: 'JetBrains Mono', size: 9 }} }}
                }}
            }}
        }};

        // 1. Broadphase Speedup
        new Chart(document.getElementById('chartBpSpeedup').getContext('2d'), {{
            type: 'bar',
            data: {{
                labels: data.scenes,
                datasets: [
                    {{ label: '1k', data: data.bp_1k, backgroundColor: 'rgba(6, 182, 212, 0.7)', borderRadius: 3 }},
                    {{ label: '10k', data: data.bp_10k, backgroundColor: 'rgba(99, 102, 241, 0.85)', borderRadius: 3 }}
                ]
            }},
            options: chartDefaults
        }});

        // 2. Step Speedup
        new Chart(document.getElementById('chartStepSpeedup').getContext('2d'), {{
            type: 'bar',
            data: {{
                labels: data.scenes,
                datasets: [
                    {{ label: '1k', data: data.step_1k, backgroundColor: 'rgba(16, 185, 129, 0.7)', borderRadius: 3 }},
                    {{ label: '10k', data: data.step_10k, backgroundColor: 'rgba(245, 158, 11, 0.85)', borderRadius: 3 }}
                ]
            }},
            options: chartDefaults
        }});

        // 3. Pairs Time 10k
        new Chart(document.getElementById('chartBpTime').getContext('2d'), {{
            type: 'bar',
            data: {{
                labels: data.scenes,
                datasets: [
                    {{ label: 'Nativo', data: data.pairs_10k_nat, backgroundColor: 'rgba(244, 63, 94, 0.7)', borderRadius: 3 }},
                    {{ label: 'SDBVH', data: data.pairs_10k_sd, backgroundColor: 'rgba(99, 102, 241, 0.85)', borderRadius: 3 }}
                ]
            }},
            options: chartDefaults
        }});

        // 4. Step Time 10k
        new Chart(document.getElementById('chartStepTime').getContext('2d'), {{
            type: 'bar',
            data: {{
                labels: data.scenes,
                datasets: [
                    {{ label: 'Nativo', data: data.step_10k_nat, backgroundColor: 'rgba(244, 63, 94, 0.7)', borderRadius: 3 }},
                    {{ label: 'SDBVH', data: data.step_10k_sd, backgroundColor: 'rgba(16, 185, 129, 0.85)', borderRadius: 3 }}
                ]
            }},
            options: chartDefaults
        }});
    </script>
</body>
</html>
"""

    with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f">> Relatório condensado widescreen gerado com sucesso em: {HTML_OUTPUT}")

if __name__ == "__main__":
    generate_condensed_html()
