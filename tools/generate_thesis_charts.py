#!/usr/bin/env python3
"""
tools/generate_thesis_charts.py
Generates high-resolution academic charts for the SDBVH thesis from benchmark data.
Outputs PDF and PNG files into local/text/figuras/
"""

import os
import csv
import numpy as np
import matplotlib.pyplot as plt

# Configuration
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 12,
    'lines.linewidth': 1.6,
    'grid.alpha': 0.4,
    'grid.linestyle': '--'
})

OUTPUT_DIR = os.path.join("local", "text", "figures")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SUITE_1000_DIR = os.path.join("benchmark_results", "2026-11-05_canonical_suite_1000")
SCALE_SWEEP_CSV = os.path.join("benchmark_results", "2026-11-01_scale_sweep_64_to_1024", "summary_scale_64_to_1024.csv")

def load_csv_timeseries(csv_path):
    if not os.path.exists(csv_path):
        return None
    data = {
        'frame': [],
        'step_ms': [],
        'pairs_ms': [],
        'collide_ms': [],
        'solve_ms': [],
        'contact_count': [],
        'tree_height': []
    }
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            data['frame'].append(int(r['frame']))
            data['step_ms'].append(float(r['step_ms']))
            data['pairs_ms'].append(float(r['pairs_ms']))
            data['collide_ms'].append(float(r['collide_ms']))
            data['solve_ms'].append(float(r['solve_ms']))
            data['contact_count'].append(float(r['contact_count']))
            data['tree_height'].append(float(r['tree_height']))
    return {k: np.array(v) for k, v in data.items()}

def moving_average(a, n=15):
    ret = np.cumsum(a, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    return ret[n - 1:] / n

# -----------------------------------------------------------------------------
# 1. Height Evolution Chart (Variação de Altura da Árvore)
# -----------------------------------------------------------------------------
def plot_height_evolution():
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7), sharey=True)
    
    # Left: convex_pile
    nat = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_convex_pile_native.csv"))
    sd = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_convex_pile_sdbvh.csv"))
    
    if nat and sd:
        axes[0].plot(nat['frame'], nat['tree_height'], label='Box3D Nativo', color='#1f77b4', linestyle='--')
        axes[0].plot(sd['frame'], sd['tree_height'], label='SDBVH (Proposta)', color='#d62728', linestyle='-')
        axes[0].set_title("(a) Pilha de Convexos (convex_pile)")
        axes[0].set_xlabel("Passo de Simulação (step)")
        axes[0].set_ylabel("Altura da Hierarquia ($H$)")
        axes[0].grid(True)
        axes[0].legend(loc='upper left')
        axes[0].set_ylim(8, 28)
    
    # Right: ragdoll_pile
    nat_rag = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_ragdoll_pile_native.csv"))
    sd_rag = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_ragdoll_pile_sdbvh.csv"))
    
    if nat_rag and sd_rag:
        axes[1].plot(nat_rag['frame'], nat_rag['tree_height'], label='Box3D Nativo', color='#1f77b4', linestyle='--')
        axes[1].plot(sd_rag['frame'], sd_rag['tree_height'], label='SDBVH (Proposta)', color='#d62728', linestyle='-')
        axes[1].set_title("(b) Corpos Articulados (ragdoll_pile)")
        axes[1].set_xlabel("Passo de Simulação (step)")
        axes[1].grid(True)
        axes[1].legend(loc='upper left')
    
    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_altura_tempo.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_altura_tempo.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Generated: grafico_altura_tempo")

# -----------------------------------------------------------------------------
# 2. Broad-Phase Time Chart (Tempo de Broad-phase ao Longo dos Passos)
# -----------------------------------------------------------------------------
def plot_broadphase_time():
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))
    
    nat = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_ragdoll_pile_native.csv"))
    sd = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_ragdoll_pile_sdbvh.csv"))
    
    if nat and sd:
        # Ragdoll Pile
        w = 11
        f_cut = nat['frame'][w-1:]
        axes[0].plot(f_cut, moving_average(nat['pairs_ms'], w), label='Nativo (média móvel)', color='#1f77b4', linestyle='--')
        axes[0].plot(f_cut, moving_average(sd['pairs_ms'], w), label='SDBVH (média móvel)', color='#2ca02c', linestyle='-')
        axes[0].set_title("(a) Broad-Phase: ragdoll_pile (1.000 corpos)")
        axes[0].set_xlabel("Passo de Simulação (step)")
        axes[0].set_ylabel("Tempo de Broad-Phase (ms)")
        axes[0].grid(True)
        axes[0].legend()
        
    nat_junk = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_junkyard_native.csv"))
    sd_junk = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_junkyard_sdbvh.csv"))
    if nat_junk and sd_junk:
        w = 11
        f_cut = nat_junk['frame'][w-1:]
        axes[1].plot(f_cut, moving_average(nat_junk['pairs_ms'], w), label='Nativo', color='#1f77b4', linestyle='--')
        axes[1].plot(f_cut, moving_average(sd_junk['pairs_ms'], w), label='SDBVH', color='#2ca02c', linestyle='-')
        axes[1].set_title("(b) Broad-Phase: junkyard (1.000 corpos)")
        axes[1].set_xlabel("Passo de Simulação (step)")
        axes[1].set_ylabel("Tempo de Broad-Phase (ms)")
        axes[1].grid(True)
        axes[1].legend()

    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_broadphase_tempo.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_broadphase_tempo.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Generated: grafico_broadphase_tempo")

# -----------------------------------------------------------------------------
# 3. Contact Count & Physical Parity Chart (Quantidade de Contatos)
# -----------------------------------------------------------------------------
def plot_contacts_parity():
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))
    
    # Convex pile contacts
    nat = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_convex_pile_native.csv"))
    sd = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_convex_pile_sdbvh.csv"))
    if nat and sd:
        axes[0].plot(nat['frame'], nat['contact_count'], label='Nativo', color='#1f77b4', alpha=0.8, linewidth=1.2)
        axes[0].plot(sd['frame'], sd['contact_count'], label='SDBVH', color='#ff7f0e', linestyle=':', linewidth=1.5)
        axes[0].set_title("(a) Contatos: convex_pile (1.000 corpos)")
        axes[0].set_xlabel("Passo de Simulação (step)")
        axes[0].set_ylabel("Pares de Contato Confirmados")
        axes[0].grid(True)
        axes[0].legend()
    
    # Spinner contacts
    nat_sp = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_spinner_native.csv"))
    sd_sp = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_spinner_sdbvh.csv"))
    if nat_sp and sd_sp:
        axes[1].plot(nat_sp['frame'], nat_sp['contact_count'], label='Nativo', color='#1f77b4', alpha=0.8, linewidth=1.2)
        axes[1].plot(sd_sp['frame'], sd_sp['contact_count'], label='SDBVH', color='#ff7f0e', linestyle=':', linewidth=1.5)
        axes[1].set_title("(b) Contatos: spinner (1.000 corpos)")
        axes[1].set_xlabel("Passo de Simulação (step)")
        axes[1].set_ylabel("Pares de Contato Confirmados")
        axes[1].grid(True)
        axes[1].legend()

    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_contatos_tempo.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_contatos_tempo.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Generated: grafico_contatos_tempo")

# -----------------------------------------------------------------------------
# 4. Step Time Chart (Tempo Total do Step Físico)
# -----------------------------------------------------------------------------
def plot_step_time():
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))
    
    nat = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_convex_pile_native.csv"))
    sd = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_convex_pile_sdbvh.csv"))
    if nat and sd:
        w = 15
        f_cut = nat['frame'][w-1:]
        axes[0].plot(f_cut, moving_average(nat['step_ms'], w), label='Nativo', color='#1f77b4', linestyle='--')
        axes[0].plot(f_cut, moving_average(sd['step_ms'], w), label='SDBVH', color='#9467bd', linestyle='-')
        axes[0].set_title("(a) Tempo Global: convex_pile (1.000 corpos)")
        axes[0].set_xlabel("Passo de Simulação (step)")
        axes[0].set_ylabel("Tempo de Step Total (ms)")
        axes[0].grid(True)
        axes[0].legend()
    
    nat_rag = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_ragdoll_pile_native.csv"))
    sd_rag = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_ragdoll_pile_sdbvh.csv"))
    if nat_rag and sd_rag:
        w = 15
        f_cut = nat_rag['frame'][w-1:]
        axes[1].plot(f_cut, moving_average(nat_rag['step_ms'], w), label='Nativo', color='#1f77b4', linestyle='--')
        axes[1].plot(f_cut, moving_average(sd_rag['step_ms'], w), label='SDBVH', color='#9467bd', linestyle='-')
        axes[1].set_title("(b) Tempo Global: ragdoll_pile (1.000 corpos)")
        axes[1].set_xlabel("Passo de Simulação (step)")
        axes[1].set_ylabel("Tempo de Step Total (ms)")
        axes[1].grid(True)
        axes[1].legend()

    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_step_tempo.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_step_tempo.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Generated: grafico_step_tempo")

# -----------------------------------------------------------------------------
# 5. Speedup and Scale Chart (Speedup em Função de N)
# -----------------------------------------------------------------------------
def plot_speedup_scale():
    if not os.path.exists(SCALE_SWEEP_CSV):
        print("Scale sweep CSV not found.")
        return
        
    data = {}
    with open(SCALE_SWEEP_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            scene = r['scene']
            if scene not in data:
                data[scene] = {'n': [], 'bp_speedup': [], 'step_speedup': []}
            data[scene]['n'].append(int(r['n']))
            data[scene]['bp_speedup'].append(float(r['speedup_broadphase']))
            data[scene]['step_speedup'].append(float(r['speedup_step']))
            
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8))
    
    colors = {
        'convex_pile': '#d62728',
        'ragdoll_pile': '#2ca02c',
        'junkyard': '#ff7f0e',
        'spinner': '#1f77b4',
        'many_pyramids': '#7f7f7f'
    }
    labels = {
        'convex_pile': 'convex_pile',
        'ragdoll_pile': 'ragdoll_pile',
        'junkyard': 'junkyard',
        'spinner': 'spinner',
        'many_pyramids': 'many_pyramids'
    }
    markers = {
        'convex_pile': 'o',
        'ragdoll_pile': 's',
        'junkyard': '^',
        'spinner': 'v',
        'many_pyramids': 'D'
    }
    
    for scene, vals in data.items():
        if scene in colors:
            axes[0].plot(vals['n'], vals['bp_speedup'], label=labels[scene],
                         color=colors[scene], marker=markers[scene], markersize=5)
            axes[1].plot(vals['n'], vals['step_speedup'], label=labels[scene],
                         color=colors[scene], marker=markers[scene], markersize=5)
            
    axes[0].axhline(1.0, color='black', linestyle=':', alpha=0.7)
    axes[0].set_xscale('log', base=2)
    axes[0].set_xticks([64, 128, 256, 512, 1024])
    axes[0].get_xaxis().set_major_formatter(plt.ScalarFormatter())
    axes[0].set_title("(a) Speedup na Broad-Phase ($T_{\\text{nat}} / T_{\\text{sdbvh}}$)")
    axes[0].set_xlabel("Número de Corpos ($N$)")
    axes[0].set_ylabel("Aceleração Relativa ($\times$)")
    axes[0].grid(True)
    axes[0].legend(loc='upper right', fontsize=8)
    
    axes[1].axhline(1.0, color='black', linestyle=':', alpha=0.7)
    axes[1].set_xscale('log', base=2)
    axes[1].set_xticks([64, 128, 256, 512, 1024])
    axes[1].get_xaxis().set_major_formatter(plt.ScalarFormatter())
    axes[1].set_title("(b) Speedup no Step Global de Física")
    axes[1].set_xlabel("Número de Corpos ($N$)")
    axes[1].grid(True)
    
    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_speedup_escala.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_speedup_escala.png"), dpi=300, bbox_inches='tight')
    fig.savefig(os.path.join(OUTPUT_DIR, "fig_13_grafico_speedup_escala.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Generated: grafico_speedup_escala")

# -----------------------------------------------------------------------------
# 6. Combined 4-Panel Telemetry Dashboard (Para compor figura ampla na monografia)
# -----------------------------------------------------------------------------
def plot_combined_4panel():
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 5.0))
    
    nat = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_convex_pile_native.csv"))
    sd = load_csv_timeseries(os.path.join(SUITE_1000_DIR, "bench1000_convex_pile_sdbvh.csv"))
    
    if nat and sd:
        # (0,0) Broad-phase time
        w = 11
        f_cut = nat['frame'][w-1:]
        axes[0, 0].plot(f_cut, moving_average(nat['pairs_ms'], w), label='Nativo', color='#1f77b4', linestyle='--')
        axes[0, 0].plot(f_cut, moving_average(sd['pairs_ms'], w), label='SDBVH', color='#2ca02c', linestyle='-')
        axes[0, 0].set_title("(a) Tempo de Broad-Phase (convex_pile, 1k)")
        axes[0, 0].set_ylabel("Tempo (ms)")
        axes[0, 0].grid(True)
        axes[0, 0].legend()
        
        # (0,1) Tree Height
        axes[0, 1].plot(nat['frame'], nat['tree_height'], label='Nativo', color='#1f77b4', linestyle='--')
        axes[0, 1].plot(sd['frame'], sd['tree_height'], label='SDBVH', color='#d62728', linestyle='-')
        axes[0, 1].set_title("(b) Variação de Altura da Hierarquia ($H$)")
        axes[0, 1].set_ylabel("Profundidade ($H$)")
        axes[0, 1].grid(True)
        axes[0, 1].legend()
        
        # (1,0) Step Time
        axes[1, 0].plot(f_cut, moving_average(nat['step_ms'], w), label='Nativo', color='#1f77b4', linestyle='--')
        axes[1, 0].plot(f_cut, moving_average(sd['step_ms'], w), label='SDBVH', color='#9467bd', linestyle='-')
        axes[1, 0].set_title("(c) Tempo Global do Passo Físico (step_ms)")
        axes[1, 0].set_xlabel("Passo de Simulação (step)")
        axes[1, 0].set_ylabel("Tempo Total (ms)")
        axes[1, 0].grid(True)
        axes[1, 0].legend()
        
        # (1,1) Contact Count Parity
        axes[1, 1].plot(nat['frame'], nat['contact_count'], label='Nativo', color='#1f77b4', alpha=0.8, linewidth=1.2)
        axes[1, 1].plot(sd['frame'], sd['contact_count'], label='SDBVH', color='#ff7f0e', linestyle=':', linewidth=1.5)
        axes[1, 1].set_title("(d) Contatos Físicos Confirmados")
        axes[1, 1].set_xlabel("Passo de Simulação (step)")
        axes[1, 1].set_ylabel("Contatos")
        axes[1, 1].grid(True)
        axes[1, 1].legend()
        
    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_telemetria_completa.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(OUTPUT_DIR, "grafico_telemetria_completa.png"), dpi=300, bbox_inches='tight')
    fig.savefig(os.path.join(OUTPUT_DIR, "fig_10_grafico_telemetria_completa.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("Generated: grafico_telemetria_completa")

if __name__ == "__main__":
    print("Generating academic figures from benchmark data...")
    plot_height_evolution()
    plot_broadphase_time()
    plot_contacts_parity()
    plot_step_time()
    plot_speedup_scale()
    plot_combined_4panel()
    print("All charts successfully generated in:", OUTPUT_DIR)

