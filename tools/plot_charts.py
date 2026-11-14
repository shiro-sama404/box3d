#!/usr/bin/env python3
"""
tools/plot_charts.py
Plot and diagram generator for Box3D and SDBVH benchmarks.

Features:
1. Performance and telemetry figures (--telemetry-suite, --all):
   - Make vector PDF files and 300 DPI PNG files for engine telemetry:
     - 4-panel telemetry dashboard (fig_10_grafico_telemetria_completa)
     - Scale sweep speedup chart (grafico_speedup_escala / fig_13_grafico_speedup_escala)
     - Tree height over time (grafico_altura_tempo)
     - Broadphase query time over time (grafico_broadphase_tempo)
     - Physical contact count (grafico_contatos_tempo)
     - Total step time over time (grafico_step_tempo)
2. Architecture diagrams (--diagrams, --all):
   - Make vector SVG files and PNG image files:
     - Dual-tier concurrent architecture (fig_6_dual_tier)
     - Binned SAH linear partition (fig_7_binned_sah)
3. Custom benchmark comparison:
   - Calculate average and peak metrics for given CSV files.
   - Make comparison charts from multiple CSV files.

Examples:
  python tools/plot_charts.py --all
  python tools/plot_charts.py --telemetry-suite
  python tools/plot_charts.py --diagrams
  python tools/plot_charts.py --telemetry
  python tools/plot_charts.py --speedup
  python tools/plot_charts.py run_native.csv run_sdbvh.csv --labels "Native" "SDBVH"
"""

import argparse
import csv
import glob
import math
import os
import subprocess
import sys

# -----------------------------------------------------------------------------
# Matplotlib Configuration
# -----------------------------------------------------------------------------
try:
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    HAS_MATPLOTLIB = True
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
except ImportError:
    HAS_MATPLOTLIB = False

DEFAULT_OUTPUT_DIR = os.path.join("local", "text", "figures")
DEFAULT_SUITE_1000_DIR = os.path.join("benchmark_results", "05-11-2026", "results")
DEFAULT_SCALE_SWEEP_CSV = os.path.join("benchmark_results", "07-11-2026", "results", "summary_scale_64_to_1024.csv")
DEFAULT_SCALE_8T_CSV = os.path.join("benchmark_results", "08-11-2026", "results", "summary_scale_multithread.csv")
DEFAULT_STRESS_10K_CSV = os.path.join("benchmark_results", "08-11-2026", "results", "summary_stress_10k.csv")

PAPER_SCENES = ['convex_pile', 'ragdoll_pile', 'junkyard', 'spinner', 'many_pyramids']
PAPER_SCENE_NAMES = {
    'convex_pile': 'convex_pile',
    'ragdoll_pile': 'ragdoll_pile',
    'junkyard': 'junkyard',
    'spinner': 'spinner',
    'many_pyramids': 'many_pyramids'
}
PAPER_SCALES = [64, 128, 256, 512, 1024]
PAPER_SCENE_COLORS = {
    'convex_pile': '#d62728',
    'ragdoll_pile': '#2ca02c',
    'junkyard': '#ff7f0e',
    'spinner': '#1f77b4',
    'many_pyramids': '#7f7f7f'
}
PAPER_SCENE_MARKERS = {
    'convex_pile': 'o',
    'ragdoll_pile': 's',
    'junkyard': '^',
    'spinner': 'v',
    'many_pyramids': 'D'
}


def find_benchmark_csv(suite_dir, scene, bp):
    """Find the CSV file for a given scene and broadphase in suite_dir."""
    import glob
    patterns = [
        os.path.join(suite_dir, f"bench_{scene}_*_{bp}.csv"),
        os.path.join(suite_dir, f"bench_{scene}_{bp}.csv"),
        os.path.join(suite_dir, f"bench1000_{scene}_{bp}.csv"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return os.path.join(suite_dir, f"bench_{scene}_{bp}.csv")


def moving_average(a, n=15):
    """Calculate the moving average of an array."""
    if len(a) < n:
        return a
    ret = np.cumsum(a, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    return ret[n - 1:] / n


def load_csv_timeseries(csv_path):
    """Read timeseries data from a CSV file."""
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
            try:
                data['frame'].append(int(r.get('frame', len(data['frame']))))
                data['step_ms'].append(float(r.get('step_ms', 0.0)))
                data['pairs_ms'].append(float(r.get('pairs_ms', 0.0)))
                data['collide_ms'].append(float(r.get('collide_ms', 0.0)))
                data['solve_ms'].append(float(r.get('solve_ms', 0.0)))
                data['contact_count'].append(float(r.get('contact_count', 0.0)))
                data['tree_height'].append(float(r.get('tree_height', 0.0)))
            except (ValueError, TypeError):
                continue
    return {k: np.array(v) for k, v in data.items()}


# =============================================================================
# Performance & Telemetry Charts
# =============================================================================

def plot_height_evolution(suite_dir, output_dir):
    """Plot the hierarchy height over simulation steps."""
    if not HAS_MATPLOTLIB:
        print("[WARNING] Matplotlib is not available. Skip plot_height_evolution.")
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7), sharey=True)

    nat = load_csv_timeseries(find_benchmark_csv(suite_dir, "convex_pile", "native"))
    sd = load_csv_timeseries(find_benchmark_csv(suite_dir, "convex_pile", "sdbvh"))
    if nat and sd:
        axes[0].plot(nat['frame'], nat['tree_height'], label='Box3D Nativo', color='#1f77b4', linestyle='--')
        axes[0].plot(sd['frame'], sd['tree_height'], label='Box3D SDBVH', color='#d62728', linestyle='-')
        axes[0].set_title("(a) Pilha de Convexos (convex_pile)")
        axes[0].set_xlabel("Passo de Simulação (step)")
        axes[0].set_ylabel("Altura da Hierarquia ($H$)")
        axes[0].grid(True)
        axes[0].legend(loc='upper left')
        axes[0].set_ylim(8, 28)

    nat_rag = load_csv_timeseries(find_benchmark_csv(suite_dir, "ragdoll_pile", "native"))
    sd_rag = load_csv_timeseries(find_benchmark_csv(suite_dir, "ragdoll_pile", "sdbvh"))
    if nat_rag and sd_rag:
        axes[1].plot(nat_rag['frame'], nat_rag['tree_height'], label='Box3D Nativo', color='#1f77b4', linestyle='--')
        axes[1].plot(sd_rag['frame'], sd_rag['tree_height'], label='Box3D SDBVH', color='#d62728', linestyle='-')
        axes[1].set_title("(b) Corpos Articulados (ragdoll_pile)")
        axes[1].set_xlabel("Passo de Simulação (step)")
        axes[1].grid(True)
        axes[1].legend(loc='upper left')

    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, "grafico_altura_tempo.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, "grafico_altura_tempo.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  [OK] grafico_altura_tempo (.pdf, .png)")


def plot_broadphase_time(suite_dir, output_dir):
    """Plot the broadphase time over simulation steps."""
    if not HAS_MATPLOTLIB:
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))

    nat = load_csv_timeseries(find_benchmark_csv(suite_dir, "ragdoll_pile", "native"))
    sd = load_csv_timeseries(find_benchmark_csv(suite_dir, "ragdoll_pile", "sdbvh"))
    if nat and sd:
        w = 11
        f_cut = nat['frame'][w-1:]
        axes[0].plot(f_cut, moving_average(nat['pairs_ms'], w), label='Nativo (média móvel)', color='#1f77b4', linestyle='--')
        axes[0].plot(f_cut, moving_average(sd['pairs_ms'], w), label='SDBVH (média móvel)', color='#2ca02c', linestyle='-')
        axes[0].set_title("(a) Broad-Phase: ragdoll_pile (1.000 corpos)")
        axes[0].set_xlabel("Passo de Simulação (step)")
        axes[0].set_ylabel("Tempo de Broad-Phase (ms)")
        axes[0].grid(True)
        axes[0].legend()

    nat_junk = load_csv_timeseries(find_benchmark_csv(suite_dir, "junkyard", "native"))
    sd_junk = load_csv_timeseries(find_benchmark_csv(suite_dir, "junkyard", "sdbvh"))
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
    fig.savefig(os.path.join(output_dir, "grafico_broadphase_tempo.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, "grafico_broadphase_tempo.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  [OK] grafico_broadphase_tempo (.pdf, .png)")


def plot_contacts_parity(suite_dir, output_dir):
    """Plot the confirmed contact count over simulation steps."""
    if not HAS_MATPLOTLIB:
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))

    nat = load_csv_timeseries(find_benchmark_csv(suite_dir, "convex_pile", "native"))
    sd = load_csv_timeseries(find_benchmark_csv(suite_dir, "convex_pile", "sdbvh"))
    if nat and sd:
        axes[0].plot(nat['frame'], nat['contact_count'], label='Nativo', color='#1f77b4', alpha=0.8, linewidth=1.2)
        axes[0].plot(sd['frame'], sd['contact_count'], label='SDBVH', color='#ff7f0e', linestyle=':', linewidth=1.5)
        axes[0].set_title("(a) Contatos: convex_pile (1.000 corpos)")
        axes[0].set_xlabel("Passo de Simulação (step)")
        axes[0].set_ylabel("Pares de Contato Confirmados")
        axes[0].grid(True)
        axes[0].legend()

    nat_sp = load_csv_timeseries(find_benchmark_csv(suite_dir, "spinner", "native"))
    sd_sp = load_csv_timeseries(find_benchmark_csv(suite_dir, "spinner", "sdbvh"))
    if nat_sp and sd_sp:
        axes[1].plot(nat_sp['frame'], nat_sp['contact_count'], label='Nativo', color='#1f77b4', alpha=0.8, linewidth=1.2)
        axes[1].plot(sd_sp['frame'], sd_sp['contact_count'], label='SDBVH', color='#ff7f0e', linestyle=':', linewidth=1.5)
        axes[1].set_title("(b) Contatos: spinner (1.000 corpos)")
        axes[1].set_xlabel("Passo de Simulação (step)")
        axes[1].set_ylabel("Pares de Contato Confirmados")
        axes[1].grid(True)
        axes[1].legend()

    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, "grafico_contatos_tempo.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, "grafico_contatos_tempo.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  [OK] grafico_contatos_tempo (.pdf, .png)")


def plot_step_time(suite_dir, output_dir):
    """Plot the total step time over simulation steps."""
    if not HAS_MATPLOTLIB:
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))

    nat = load_csv_timeseries(find_benchmark_csv(suite_dir, "convex_pile", "native"))
    sd = load_csv_timeseries(find_benchmark_csv(suite_dir, "convex_pile", "sdbvh"))
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

    nat_rag = load_csv_timeseries(find_benchmark_csv(suite_dir, "ragdoll_pile", "native"))
    sd_rag = load_csv_timeseries(find_benchmark_csv(suite_dir, "ragdoll_pile", "sdbvh"))
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
    fig.savefig(os.path.join(output_dir, "grafico_step_tempo.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, "grafico_step_tempo.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  [OK] grafico_step_tempo (.pdf, .png)")


def plot_speedup_scale(scale_csv, output_dir):
    """Plot the relative speedup as a function of actor count N."""
    if not HAS_MATPLOTLIB:
        return
    if not os.path.exists(scale_csv):
        print(f"[WARNING] Scale sweep CSV not found at {scale_csv}")
        return

    data = {}
    with open(scale_csv, 'r', encoding='utf-8') as f:
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
    axes[0].set_title(r"(a) Speedup na Broad-Phase ($T_{\text{nat}} / T_{\text{sdbvh}}$)")
    axes[0].set_xlabel(r"Número de Corpos ($N$)")
    axes[0].set_ylabel(r"Aceleração Relativa ($\times$)")
    axes[0].grid(True)
    axes[0].legend(loc='upper right', fontsize=8)

    axes[1].axhline(1.0, color='black', linestyle=':', alpha=0.7)
    axes[1].set_xscale('log', base=2)
    axes[1].set_xticks([64, 128, 256, 512, 1024])
    axes[1].get_xaxis().set_major_formatter(plt.ScalarFormatter())
    axes[1].set_title(r"(b) Speedup no Step Global de Física")
    axes[1].set_xlabel(r"Número de Corpos ($N$)")
    axes[1].grid(True)

    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, "grafico_speedup_escala.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, "grafico_speedup_escala.png"), dpi=300, bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, "fig_13_grafico_speedup_escala.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  [OK] grafico_speedup_escala (.pdf, .png) & fig_13_grafico_speedup_escala.png")


def plot_combined_4panel(suite_dir, output_dir):
    """Plot the 4-panel telemetry dashboard."""
    if not HAS_MATPLOTLIB:
        return
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 5.0))

    nat = load_csv_timeseries(find_benchmark_csv(suite_dir, "convex_pile", "native"))
    sd = load_csv_timeseries(find_benchmark_csv(suite_dir, "convex_pile", "sdbvh"))

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
        axes[0, 1].set_title(r"(b) Variação de Altura da Hierarquia ($H$)")
        axes[0, 1].set_ylabel(r"Profundidade ($H$)")
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
    fig.savefig(os.path.join(output_dir, "grafico_telemetria_completa.pdf"), bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, "grafico_telemetria_completa.png"), dpi=300, bbox_inches='tight')
    fig.savefig(os.path.join(output_dir, "fig_10_grafico_telemetria_completa.png"), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print("  [OK] grafico_telemetria_completa (.pdf, .png) & fig_10_grafico_telemetria_completa.png")


# =============================================================================
# Architectural Diagrams (SVG + Headless Browser PNG)
# =============================================================================

def create_dual_tier_svg(output_path):
    width = 1200
    height = 540
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <linearGradient id="mainGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#E3F2FD"/>
      <stop offset="100%" stop-color="#BBDEFB"/>
    </linearGradient>
    <linearGradient id="workerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#FFF3E0"/>
      <stop offset="100%" stop-color="#FFE0B2"/>
    </linearGradient>
    <linearGradient id="swapGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#E8F5E9"/>
      <stop offset="100%" stop-color="#C8E6C9"/>
    </linearGradient>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="115%" filterUnits="userSpaceOnUse">
      <feDropShadow dx="1" dy="2" stdDeviation="2" flood-color="#000000" flood-opacity="0.12"/>
    </filter>
    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#37474F"/>
    </marker>
    <marker id="arrowBlue" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#1565C0"/>
    </marker>
    <marker id="arrowOrange" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#E65100"/>
    </marker>
    <marker id="arrowGreen" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#2E7D32"/>
    </marker>
  </defs>

  <rect width="{width}" height="{height}" fill="#FFFFFF"/>

  <text x="600" y="32" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="20" font-weight="bold" fill="#263238" text-anchor="middle">
    Arquitetura Concorrente Dual-Tier: Simulação Síncrona e Reconstrução por Árvore-Sombra
  </text>

  <!-- Main Thread Lane -->
  <rect x="40" y="55" width="1120" height="205" rx="10" fill="url(#mainGrad)" stroke="#90CAF9" stroke-width="1.5"/>
  <rect x="40" y="55" width="180" height="30" rx="6" fill="#1976D2"/>
  <text x="130" y="75" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" font-weight="bold" fill="#FFFFFF" text-anchor="middle">
    MAIN THREAD (Síncrona)
  </text>
  <text x="1000" y="75" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" fill="#546E7A" text-anchor="middle">
    Passo temporal fixo (60 Hz / 16.6 ms) — Sem pausas na física
  </text>

  <!-- Worker Thread Lane -->
  <rect x="40" y="285" width="1120" height="210" rx="10" fill="url(#workerGrad)" stroke="#FFCC80" stroke-width="1.5"/>
  <rect x="40" y="285" width="180" height="30" rx="6" fill="#F57C00"/>
  <text x="130" y="305" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" font-weight="bold" fill="#FFFFFF" text-anchor="middle">
    WORKER THREAD (Assíncrona)
  </text>
  <text x="1000" y="305" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" fill="#795548" text-anchor="middle">
    Execução concorrente desacoplada sobre a Shadow Tree
  </text>

  <!-- Timeline Axis -->
  <line x1="240" y1="272" x2="1140" y2="272" stroke="#B0BEC5" stroke-width="2" stroke-dasharray="4,4"/>
  <text x="1145" y="276" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" font-weight="bold" fill="#78909C">Tempo (t) →</text>

  <!-- (a) Step t -->
  <g transform="translate(60, 95)">
    <rect width="320" height="150" rx="8" fill="#FFFFFF" stroke="#64B5F6" stroke-width="1.5" filter="url(#shadow)"/>
    <rect x="0" y="0" width="320" height="26" rx="6" fill="#E3F2FD"/>
    <text x="10" y="18" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" font-weight="bold" fill="#0D47A1">
      (a) Passo t: Manutenção Incremental SDBVH
    </text>

    <rect x="15" y="38" width="85" height="42" rx="4" fill="#BBDEFB" stroke="#1976D2" stroke-width="1"/>
    <text x="57" y="55" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#0D47A1" text-anchor="middle">Refit AABB</text>
    <text x="57" y="68" font-family="Segoe UI, Arial" font-size="9" fill="#1565C0" text-anchor="middle">+ Rotações AVL</text>

    <line x1="102" y1="59" x2="118" y2="59" stroke="#1976D2" stroke-width="1.5" marker-end="url(#arrowBlue)"/>

    <rect x="120" y="38" width="95" height="42" rx="4" fill="#BBDEFB" stroke="#1976D2" stroke-width="1"/>
    <text x="167" y="55" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#0D47A1" text-anchor="middle">Travessia Mútua</text>
    <text x="167" y="68" font-family="Segoe UI, Arial" font-size="9" fill="#1565C0" text-anchor="middle">Dual-Tree SIMD</text>

    <line x1="217" y1="59" x2="233" y2="59" stroke="#1976D2" stroke-width="1.5" marker-end="url(#arrowBlue)"/>

    <rect x="235" y="38" width="72" height="42" rx="4" fill="#BBDEFB" stroke="#1976D2" stroke-width="1"/>
    <text x="271" y="55" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#0D47A1" text-anchor="middle">Resolução</text>
    <text x="271" y="68" font-family="Segoe UI, Arial" font-size="9" fill="#1565C0" text-anchor="middle">Solver Contatos</text>

    <rect x="15" y="92" width="292" height="46" rx="4" fill="#FFEBEE" stroke="#E57373" stroke-width="1"/>
    <text x="25" y="108" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#C62828">
      Monitor de Degradação: Avalia ρ_area(Nk) = S(Nk) / S_base
    </text>
    <text x="25" y="125" font-family="Segoe UI, Arial" font-size="10" fill="#B71C1C">
      Condição atendida: <tspan font-weight="bold">ρ_area ≥ 1.8</tspan> → <tspan fill="#D32F2F" font-weight="bold">Dispara Sinal de Reconstrução</tspan>
    </text>
  </g>

  <!-- Signal Arrow -->
  <path d="M 220 248 L 220 330" fill="none" stroke="#D32F2F" stroke-width="2.5" stroke-dasharray="5,4" marker-end="url(#arrowOrange)"/>
  <rect x="150" y="260" width="140" height="24" rx="4" fill="#FFFFFF" stroke="#D32F2F" stroke-width="1" filter="url(#shadow)"/>
  <text x="220" y="276" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#C62828" text-anchor="middle">
    b3Semaphore Post()
  </text>

  <!-- (b) Worker -->
  <g transform="translate(180, 335)">
    <rect width="450" height="145" rx="8" fill="#FFFFFF" stroke="#FFB74D" stroke-width="1.5" filter="url(#shadow)"/>
    <rect x="0" y="0" width="450" height="26" rx="6" fill="#FFF3E0"/>
    <text x="10" y="18" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" font-weight="bold" fill="#E65100">
      (b) Execução Concorrente: Reconstrução por Árvore-Sombra (Shadow Tree)
    </text>

    <rect x="15" y="38" width="125" height="52" rx="4" fill="#FFE0B2" stroke="#FB8C00" stroke-width="1"/>
    <text x="77" y="55" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#E65100" text-anchor="middle">1. Clonagem Isolada</text>
    <text x="77" y="70" font-family="Segoe UI, Arial" font-size="9" fill="#BF360C" text-anchor="middle">Cópia do ramo Nk para</text>
    <text x="77" y="82" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#BF360C" text-anchor="middle">Árvore-Sombra</text>

    <line x1="142" y1="64" x2="158" y2="64" stroke="#FB8C00" stroke-width="1.5" marker-end="url(#arrowOrange)"/>

    <rect x="160" y="38" width="140" height="52" rx="4" fill="#FFE0B2" stroke="#FB8C00" stroke-width="1"/>
    <text x="230" y="55" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#E65100" text-anchor="middle">2. Binned SAH (12 Baldes)</text>
    <text x="230" y="70" font-family="Segoe UI, Arial" font-size="9" fill="#BF360C" text-anchor="middle">Varredura prefixo/sufixo</text>
    <text x="230" y="82" font-family="Segoe UI, Arial" font-size="9" fill="#BF360C" text-anchor="middle">Partição ótima de folhas</text>

    <line x1="302" y1="64" x2="318" y2="64" stroke="#FB8C00" stroke-width="1.5" marker-end="url(#arrowOrange)"/>

    <rect x="320" y="38" width="115" height="52" rx="4" fill="#FFE0B2" stroke="#FB8C00" stroke-width="1"/>
    <text x="377" y="55" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#E65100" text-anchor="middle">3. Atualiza Base</text>
    <text x="377" y="70" font-family="Segoe UI, Arial" font-size="9" fill="#BF360C" text-anchor="middle">S_base = S_novo</text>
    <text x="377" y="82" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#BF360C" text-anchor="middle">Sinaliza Conclusão</text>

    <rect x="15" y="100" width="420" height="34" rx="4" fill="#FBE9E7" stroke="#FFAB91" stroke-width="1"/>
    <text x="225" y="115" font-family="Segoe UI, Arial" font-size="10" fill="#D84315" text-anchor="middle">
      <tspan font-weight="bold">Não bloqueia a Main Thread:</tspan> a simulação continua avançando nos passos seguintes
    </text>
    <text x="225" y="128" font-family="Segoe UI, Arial" font-size="9" fill="#BF360C" text-anchor="middle">
      (Passos t+1, t+2 executam colisões normalmente sobre a árvore ativa)
    </text>
  </g>

  <!-- Intermediary steps -->
  <g transform="translate(420, 95)">
    <rect width="140" height="90" rx="6" fill="#F5F5F5" stroke="#B0BEC5" stroke-width="1"/>
    <text x="70" y="20" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#455A64" text-anchor="middle">Passo t+1</text>
    <text x="70" y="42" font-family="Segoe UI, Arial" font-size="9" fill="#607D8B" text-anchor="middle">Simulação Ativa</text>
    <text x="70" y="58" font-family="Segoe UI, Arial" font-size="9" fill="#607D8B" text-anchor="middle">(refit + micro-rot.)</text>
    <text x="70" y="76" font-family="Segoe UI, Arial" font-size="9" font-style="italic" fill="#78909C" text-anchor="middle">Worker executando...</text>
  </g>
  <g transform="translate(580, 95)">
    <rect width="140" height="90" rx="6" fill="#F5F5F5" stroke="#B0BEC5" stroke-width="1"/>
    <text x="70" y="20" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#455A64" text-anchor="middle">Passo t+2</text>
    <text x="70" y="42" font-family="Segoe UI, Arial" font-size="9" fill="#607D8B" text-anchor="middle">Simulação Ativa</text>
    <text x="70" y="58" font-family="Segoe UI, Arial" font-size="9" fill="#607D8B" text-anchor="middle">(refit + micro-rot.)</text>
    <text x="70" y="76" font-family="Segoe UI, Arial" font-size="9" font-style="italic" fill="#78909C" text-anchor="middle">Worker finalizando...</text>
  </g>

  <!-- Connect worker to swap -->
  <path d="M 630 380 C 720 380, 750 330, 770 230" fill="none" stroke="#2E7D32" stroke-width="2.5" marker-end="url(#arrowGreen)"/>

  <!-- (c) Swap -->
  <g transform="translate(750, 95)">
    <rect width="380" height="150" rx="8" fill="url(#swapGrad)" stroke="#81C784" stroke-width="2" filter="url(#shadow)"/>
    <rect x="0" y="0" width="380" height="26" rx="6" fill="#C8E6C9"/>
    <text x="10" y="18" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" font-weight="bold" fill="#1B5E20">
      (c) Início do Passo t+3: Troca Atômica (Pointer Swap)
    </text>

    <rect x="15" y="38" width="350" height="48" rx="6" fill="#FFFFFF" stroke="#4CAF50" stroke-width="1.5"/>
    <text x="190" y="56" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#2E7D32" text-anchor="middle">
      Troca Atômica de Índices: O(1) no Início do Step
    </text>
    <text x="190" y="72" font-family="Consolas, monospace" font-size="10" fill="#1B5E20" text-anchor="middle">
      tree.root_degraded ⇆ shadow_tree.root_rebuilt
    </text>

    <rect x="15" y="94" width="350" height="44" rx="4" fill="#E8F5E9" stroke="#A5D6A7" stroke-width="1"/>
    <text x="190" y="110" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#1B5E20" text-anchor="middle">
      Zero Frame Spike / Bloqueio Nulo
    </text>
    <text x="190" y="126" font-family="Segoe UI, Arial" font-size="9" fill="#2E7D32" text-anchor="middle">
      A subárvore SAH balanceada passa a responder pelas colisões imediatamente
    </text>
  </g>

  <!-- Legend -->
  <g transform="translate(300, 508)">
    <rect x="0" y="0" width="14" height="14" rx="2" fill="#1976D2"/>
    <text x="20" y="12" font-family="Segoe UI, Arial" font-size="11" fill="#37474F">Main Thread (Física Síncrona)</text>

    <rect x="200" y="0" width="14" height="14" rx="2" fill="#F57C00"/>
    <text x="220" y="12" font-family="Segoe UI, Arial" font-size="11" fill="#37474F">Worker Thread (Shadow Tree)</text>

    <rect x="420" y="0" width="14" height="14" rx="2" fill="#2E7D32"/>
    <text x="440" y="12" font-family="Segoe UI, Arial" font-size="11" fill="#37474F">Sincronização Atômica O(1)</text>
  </g>
</svg>'''
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"  [OK] Generated {output_path}")


def create_binned_sah_svg(output_path):
    width = 1200
    height = 560
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <filter id="shadow2" x="-5%" y="-5%" width="110%" height="115%" filterUnits="userSpaceOnUse">
      <feDropShadow dx="1" dy="2" stdDeviation="2" flood-color="#000000" flood-opacity="0.12"/>
    </filter>
    <marker id="arrowB" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#37474F"/>
    </marker>
    <marker id="arrowBlue2" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#1976D2"/>
    </marker>
    <marker id="arrowOrange2" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#F57C00"/>
    </marker>
  </defs>

  <rect width="{width}" height="{height}" fill="#FFFFFF"/>

  <text x="600" y="32" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="20" font-weight="bold" fill="#263238" text-anchor="middle">
    Partição Linear Binned SAH com 12 Baldes Discretos
  </text>

  <!-- Panel (a) -->
  <g transform="translate(30, 55)">
    <rect width="360" height="450" rx="8" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1.5" filter="url(#shadow2)"/>
    <rect x="0" y="0" width="360" height="32" rx="6" fill="#E2E8F0"/>
    <text x="12" y="21" font-family="Segoe UI, Arial" font-size="13" font-weight="bold" fill="#1E293B">
      (a) Seleção do Eixo de Maior Extensão
    </text>

    <text x="180" y="54" font-family="Segoe UI, Arial" font-size="11" fill="#64748B" text-anchor="middle">
      Caixa Envoltória dos Centróides (B_centróides)
    </text>

    <rect x="40" y="80" width="280" height="150" fill="#F1F5F9" stroke="#0284C7" stroke-width="2" stroke-dasharray="6,4"/>
    <text x="180" y="74" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#0284C7" text-anchor="middle">
      Δx = max(Δx, Δy, Δz) → EIXO X SELECIONADO
    </text>

    <line x1="40" y1="240" x2="320" y2="240" stroke="#0284C7" stroke-width="1.5" marker-start="url(#arrowB)" marker-end="url(#arrowB)"/>
    <text x="180" y="255" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#0284C7" text-anchor="middle">
      Extensão Δx = 28.0 m (Maior Dispersão)
    </text>

    <line x1="335" y1="80" x2="335" y2="230" stroke="#64748B" stroke-width="1.5" marker-start="url(#arrowB)" marker-end="url(#arrowB)"/>
    <text x="340" y="160" font-family="Segoe UI, Arial" font-size="10" fill="#64748B" transform="rotate(90, 340, 160)" text-anchor="middle">
      Δy = 15.0 m
    </text>

    <!-- Sample leaves and centroids -->
    <rect x="55" y="100" width="35" height="40" fill="#E2E8F0" stroke="#94A3B8" stroke-width="1" rx="3"/>
    <circle cx="72" cy="120" r="4" fill="#EF4444"/>
    <text x="72" y="112" font-family="Segoe UI, Arial" font-size="8" fill="#1E293B" text-anchor="middle">c1</text>

    <rect x="100" y="150" width="45" height="30" fill="#E2E8F0" stroke="#94A3B8" stroke-width="1" rx="3"/>
    <circle cx="122" cy="165" r="4" fill="#EF4444"/>
    <text x="122" y="157" font-family="Segoe UI, Arial" font-size="8" fill="#1E293B" text-anchor="middle">c2</text>

    <rect x="160" y="95" width="40" height="45" fill="#E2E8F0" stroke="#94A3B8" stroke-width="1" rx="3"/>
    <circle cx="180" cy="117" r="4" fill="#EF4444"/>
    <text x="180" y="109" font-family="Segoe UI, Arial" font-size="8" fill="#1E293B" text-anchor="middle">c3</text>

    <rect x="220" y="140" width="30" height="35" fill="#E2E8F0" stroke="#94A3B8" stroke-width="1" rx="3"/>
    <circle cx="235" cy="157" r="4" fill="#EF4444"/>
    <text x="235" y="149" font-family="Segoe UI, Arial" font-size="8" fill="#1E293B" text-anchor="middle">c4</text>

    <rect x="265" y="110" width="45" height="50" fill="#E2E8F0" stroke="#94A3B8" stroke-width="1" rx="3"/>
    <circle cx="287" cy="135" r="4" fill="#EF4444"/>
    <text x="287" y="127" font-family="Segoe UI, Arial" font-size="8" fill="#1E293B" text-anchor="middle">c5</text>

    <rect x="15" y="280" width="330" height="150" rx="6" fill="#EFF6FF" stroke="#BFDBFE" stroke-width="1"/>
    <text x="25" y="302" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#1E40AF">Procedimento:</text>
    <text x="25" y="322" font-family="Segoe UI, Arial" font-size="10" fill="#1E3A8A">1. Extrai K folhas da subárvore degradada.</text>
    <text x="25" y="342" font-family="Segoe UI, Arial" font-size="10" fill="#1E3A8A">2. Calcula centróide ci = 0.5 * (min + max) de cada folha.</text>
    <text x="25" y="362" font-family="Segoe UI, Arial" font-size="10" fill="#1E3A8A">3. Encontra bounding box de todos os centróides.</text>
    <text x="25" y="382" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#0284C7">4. Eixo com maior dispersão (ΔE) é escolhido</text>
    <text x="35" y="398" font-family="Segoe UI, Arial" font-size="10" fill="#0369A1">para garantir partições com menor sobreposição.</text>
    <text x="25" y="418" font-family="Segoe UI, Arial" font-size="9" fill="#64748B">• Círculos vermelhos: Centróides das geometrias</text>
  </g>

  <!-- Panel (b) -->
  <g transform="translate(410, 55)">
    <rect width="370" height="450" rx="8" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1.5" filter="url(#shadow2)"/>
    <rect x="0" y="0" width="370" height="32" rx="6" fill="#E2E8F0"/>
    <text x="12" y="21" font-family="Segoe UI, Arial" font-size="13" font-weight="bold" fill="#1E293B">
      (b) Discretização em 12 Baldes Uniformes
    </text>

    <rect x="15" y="45" width="340" height="42" rx="4" fill="#F1F5F9" stroke="#E2E8F0" stroke-width="1"/>
    <text x="185" y="62" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#334155" text-anchor="middle">
      Mapeamento O(K) de cada Centróide ci:
    </text>
    <text x="185" y="78" font-family="Consolas, monospace" font-size="10" fill="#0369A1" text-anchor="middle">
      b_i = clamp( ⌊12 * (c_i,x - min_x) / Δx⌋, 0, 11 )
    </text>

    <g transform="translate(15, 105)">
'''
    bucket_w = 28
    bucket_gap = 1
    total_w = 12 * (bucket_w + bucket_gap)
    counts = [1, 0, 2, 0, 3, 1, 4, 2, 0, 1, 2, 1]
    for b in range(12):
        bx = b * (bucket_w + bucket_gap)
        svg += f'''
      <rect x="{bx}" y="40" width="{bucket_w}" height="90" fill="#E0F2FE" stroke="#0284C7" stroke-width="1" rx="2"/>
      <text x="{bx + bucket_w/2}" y="32" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#0369A1" text-anchor="middle">B{b}</text>
      <rect x="{bx + 3}" y="{130 - counts[b]*15}" width="{bucket_w - 6}" height="{counts[b]*15}" fill="#38BDF8" rx="2"/>
      <text x="{bx + bucket_w/2}" y="125" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#0C4A6E" text-anchor="middle">{counts[b]}</text>
'''
    svg += f'''
      <line x1="0" y1="140" x2="{total_w}" y2="140" stroke="#0284C7" stroke-width="2"/>
      <text x="0" y="155" font-family="Segoe UI, Arial" font-size="9" fill="#0369A1">min_x</text>
      <text x="{total_w}" y="155" font-family="Segoe UI, Arial" font-size="9" fill="#0369A1" text-anchor="end">max_x</text>
      <text x="{total_w/2}" y="155" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#0369A1" text-anchor="middle">Eixo X (12 Baldes)</text>
    </g>

    <rect x="15" y="280" width="340" height="150" rx="6" fill="#F0FDF4" stroke="#BBF7D0" stroke-width="1"/>
    <text x="25" y="302" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#166534">Dados Acumulados por Balde:</text>
    <text x="25" y="322" font-family="Segoe UI, Arial" font-size="10" fill="#14532D">• <tspan font-weight="bold">count[b]:</tspan> Quantidade de geometrias no balde b.</text>
    <text x="25" y="342" font-family="Segoe UI, Arial" font-size="10" fill="#14532D">• <tspan font-weight="bold">aabb[b]:</tspan> União das AABBs dos corpos mapeados.</text>
    <text x="25" y="365" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#15803D">Complexidade O(K):</text>
    <text x="25" y="382" font-family="Segoe UI, Arial" font-size="10" fill="#166534">Uma única varredura linear projeta todas as K folhas</text>
    <text x="25" y="398" font-family="Segoe UI, Arial" font-size="10" fill="#166534">nos 12 baldes sem ordenar os centróides (evita O(K log K)).</text>
    <text x="25" y="418" font-family="Segoe UI, Arial" font-size="9" fill="#64748B">Inspirado na implementação Ds (Pagliosa) e PBRT.</text>
  </g>

  <!-- Panel (c) -->
  <g transform="translate(800, 55)">
    <rect width="370" height="450" rx="8" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1.5" filter="url(#shadow2)"/>
    <rect x="0" y="0" width="370" height="32" rx="6" fill="#E2E8F0"/>
    <text x="12" y="21" font-family="Segoe UI, Arial" font-size="13" font-weight="bold" fill="#1E293B">
      (c) Varreduras e Plano Ótimo (11 Candidatos)
    </text>

    <g transform="translate(20, 48)">
      <rect width="330" height="30" rx="4" fill="#EFF6FF" stroke="#BFDBFE" stroke-width="1"/>
      <line x1="10" y1="15" x2="310" y2="15" stroke="#1D4ED8" stroke-width="2" marker-end="url(#arrowBlue2)"/>
      <text x="160" y="12" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#1D4ED8" text-anchor="middle">
        Varredura de Prefixo (Esq → Dir): B_esq[p], N_esq[p]
      </text>
    </g>

    <g transform="translate(20, 85)">
      <rect width="330" height="30" rx="4" fill="#FFF7ED" stroke="#FFEDD5" stroke-width="1"/>
      <line x1="310" y1="15" x2="10" y2="15" stroke="#EA580C" stroke-width="2" marker-end="url(#arrowOrange2)"/>
      <text x="160" y="12" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#EA580C" text-anchor="middle">
        Varredura de Sufixo (Dir → Esq): B_dir[p], N_dir[p]
      </text>
    </g>

    <g transform="translate(20, 125)">
      <rect width="330" height="140" rx="6" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1"/>
      <text x="165" y="18" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#334155" text-anchor="middle">
        Curva de Custo SAH dos 11 Planos Candidatos
      </text>

      <line x1="30" y1="110" x2="310" y2="110" stroke="#CBD5E1" stroke-width="1"/>
      <line x1="30" y1="30" x2="30" y2="110" stroke="#CBD5E1" stroke-width="1"/>

      <path d="M 40 45 Q 90 75, 140 100 T 200 85 T 260 55 T 300 40" fill="none" stroke="#64748B" stroke-width="2"/>
'''
    cost_pts = [
        (45, 50), (70, 68), (95, 82), (120, 93),
        (145, 102),  # p4 = min
        (170, 95), (195, 88), (220, 75), (245, 63), (270, 52), (295, 42)
    ]
    for idx, (px, py) in enumerate(cost_pts):
        is_min = (idx == 4)
        col = "#16A34A" if is_min else "#64748B"
        r = 5 if is_min else 3
        svg += f'''      <circle cx="{px}" cy="{py}" r="{r}" fill="{col}"/>\n'''
    svg += f'''
      <line x1="145" y1="28" x2="145" y2="110" stroke="#16A34A" stroke-width="1.5" stroke-dasharray="3,3"/>
      <rect x="105" y="22" width="80" height="18" rx="3" fill="#DCFCE7" stroke="#16A34A" stroke-width="1"/>
      <text x="145" y="34" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#15803D" text-anchor="middle">p_ótimo (C_min)</text>
      <text x="145" y="122" font-family="Segoe UI, Arial" font-size="8" font-weight="bold" fill="#16A34A" text-anchor="middle">Plano 4</text>

      <text x="25" y="30" font-family="Segoe UI, Arial" font-size="8" fill="#64748B">Custo</text>
      <text x="310" y="122" font-family="Segoe UI, Arial" font-size="8" fill="#64748B">Planos p0..p10</text>
    </g>

    <rect x="15" y="280" width="340" height="150" rx="6" fill="#FEF3C7" stroke="#FDE68A" stroke-width="1"/>
    <text x="25" y="302" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#92400E">Decisão de Partição Ótima:</text>
    <text x="25" y="322" font-family="Segoe UI, Arial" font-size="9" fill="#78350F">C_split(p) = C_T + (S(B_esq)/S_total)*N_esq*C_I + (S(B_dir)/S_total)*N_dir*C_I</text>
    <text x="25" y="346" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#B45309">1. Seleciona plano p com menor C_split.</text>
    <text x="25" y="366" font-family="Segoe UI, Arial" font-size="10" fill="#92400E">2. Particiona o vetor de folhas no local (in-place).</text>
    <text x="25" y="386" font-family="Segoe UI, Arial" font-size="10" fill="#92400E">3. Recursão para filho esquerdo e direito.</text>
    <text x="25" y="412" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#15803D">Resultado: Árvore SAH compacta com O(K) total!</text>
  </g>
</svg>'''
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"  [OK] Generated {output_path}")


def render_svg_to_png(svg_path, png_path, width, height):
    """Convert an SVG file to a PNG image with a headless browser."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
    browser_path = None
    for c in candidates:
        if os.path.exists(c):
            browser_path = c
            break

    if not browser_path:
        print(f"[WARNING] No headless browser found to convert {svg_path} to PNG. Keep SVG.")
        return

    import tempfile
    abs_svg = os.path.abspath(svg_path).replace("\\", "/")
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: white; width: {width}px; height: {height}px; overflow: hidden; }}
  img {{ width: {width}px; height: {height}px; display: block; }}
</style>
</head>
<body>
<img src="file:///{abs_svg}">
</body>
</html>"""
    html_path = svg_path + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    abs_html = os.path.abspath(html_path).replace("\\", "/")
    abs_png = os.path.abspath(png_path)
    tmp_user_dir = os.path.join(tempfile.gettempdir(), "edge_render_profile")

    cmd = [
        browser_path,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-data-dir={tmp_user_dir}",
        f"--window-size={width},{height}",
        f"--screenshot={abs_png}",
        f"file:///{abs_html}"
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=15)
        print(f"  [OK] Rendered {abs_png} ({width}x{height})", flush=True)
    except subprocess.TimeoutExpired:
        print(f"  [WARN] Browser timed out for {svg_path}. SVG file kept.", flush=True)
    except Exception as e:
        print(f"  [WARN] Browser failed: {e}. SVG file kept.", flush=True)
    finally:
        if os.path.exists(html_path):
            os.remove(html_path)


# =============================================================================
# Custom Benchmark Analysis & Timeseries Plotting
# =============================================================================

def clean_label(filepath):
    """Make a clean label from a file path."""
    base = os.path.splitext(os.path.basename(filepath))[0]
    base = base.replace("bench1000_", "").replace("benchmark_", "").replace("bench_", "").replace("results_", "")
    return base.replace("_", " ").title()


def plot_custom_benchmarks(files, labels, output_dir):
    """Read custom CSV files, show metrics, and make comparison plots."""
    if not files:
        print("[WARNING] No CSV files given for comparison.")
        return

    os.makedirs(output_dir, exist_ok=True)
    datasets = []
    for f in files:
        ts = load_csv_timeseries(f)
        if ts is not None and len(ts['frame']) > 0:
            datasets.append((f, ts))
        else:
            print(f"[WARNING] Cannot read timeseries from {f}")

    if not datasets:
        print("[ERROR] No valid datasets loaded.")
        return

    # Print summary table to console
    print("\n" + "=" * 90)
    print("  RESUMO ESTATÍSTICO DE BENCHMARK (CUSTOM)")
    print("=" * 90)
    header = f"{'Dataset / Arquivo':<35} | {'Passo (ms)':<10} | {'Pares (ms)':<10} | {'Altura (H)':<10} | {'Contatos':<10}"
    print(header)
    print("-" * len(header))
    for idx, (path, data) in enumerate(datasets):
        lbl = labels[idx] if labels and idx < len(labels) else clean_label(path)
        step_mean = np.mean(data['step_ms']) if len(data['step_ms']) else 0.0
        pairs_mean = np.mean(data['pairs_ms']) if len(data['pairs_ms']) else 0.0
        h_mean = np.mean(data['tree_height']) if len(data['tree_height']) else 0.0
        c_mean = np.mean(data['contact_count']) if len(data['contact_count']) else 0.0
        print(f"{lbl:<35} | {step_mean:<10.3f} | {pairs_mean:<10.3f} | {h_mean:<10.1f} | {c_mean:<10.1f}")
    print("=" * 90 + "\n")

    if not HAS_MATPLOTLIB:
        print("[WARNING] Matplotlib not installed. Skip chart image creation.")
        return

    # Make 4 comparison charts
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.5))
    colors = ['#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']

    for idx, (path, data) in enumerate(datasets):
        lbl = labels[idx] if labels and idx < len(labels) else clean_label(path)
        color = colors[idx % len(colors)]
        w = 11
        if len(data['frame']) >= w:
            f_cut = data['frame'][w-1:]
            axes[0, 0].plot(f_cut, moving_average(data['pairs_ms'], w), label=lbl, color=color)
            axes[1, 0].plot(f_cut, moving_average(data['step_ms'], w), label=lbl, color=color)
        else:
            axes[0, 0].plot(data['frame'], data['pairs_ms'], label=lbl, color=color)
            axes[1, 0].plot(data['frame'], data['step_ms'], label=lbl, color=color)

        axes[0, 1].plot(data['frame'], data['tree_height'], label=lbl, color=color)
        axes[1, 1].plot(data['frame'], data['contact_count'], label=lbl, color=color)

    axes[0, 0].set_title("Tempo de Broad-Phase (pairs_ms)")
    axes[0, 0].set_xlabel("Passo (step)")
    axes[0, 0].set_ylabel("Tempo (ms)")
    axes[0, 0].grid(True)
    axes[0, 0].legend()

    axes[0, 1].set_title("Altura da Hierarquia (tree_height)")
    axes[0, 1].set_xlabel("Passo (step)")
    axes[0, 1].set_ylabel("Altura ($H$)")
    axes[0, 1].grid(True)
    axes[0, 1].legend()

    axes[1, 0].set_title("Tempo Global de Simulação (step_ms)")
    axes[1, 0].set_xlabel("Passo (step)")
    axes[1, 0].set_ylabel("Tempo (ms)")
    axes[1, 0].grid(True)
    axes[1, 0].legend()

    axes[1, 1].set_title("Pares de Contato Confirmados (contact_count)")
    axes[1, 1].set_xlabel("Passo (step)")
    axes[1, 1].set_ylabel("Contatos")
    axes[1, 1].grid(True)
    axes[1, 1].legend()

    plt.tight_layout()
    out_img = os.path.join(output_dir, "custom_benchmark_comparison.png")
    fig.savefig(out_img, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  [OK] Custom comparison saved to {out_img}")


# =============================================================================
# Benchmark Comparison Figures (Multi-scale Heatmaps, Topology, Breakdown, 10k)
# =============================================================================

def plot_speedup_heatmaps(scale_1t_csv=None, scale_8t_csv=None, output_dir=None):
    if not HAS_MATPLOTLIB:
        return
    csv_1t = scale_1t_csv or DEFAULT_SCALE_SWEEP_CSV
    csv_8t = scale_8t_csv or DEFAULT_SCALE_8T_CSV
    out_dir = output_dir or DEFAULT_OUTPUT_DIR

    if not os.path.exists(csv_1t) or not os.path.exists(csv_8t):
        print(f"  [SKIP] Multi-scale heatmaps skipped: CSV files not found ({csv_1t}, {csv_8t})")
        return

    data_1t_broad = np.zeros((len(PAPER_SCENES), len(PAPER_SCALES)))
    data_1t_step = np.zeros((len(PAPER_SCENES), len(PAPER_SCALES)))
    data_8t_broad = np.zeros((len(PAPER_SCENES), len(PAPER_SCALES)))
    data_8t_step = np.zeros((len(PAPER_SCENES), len(PAPER_SCALES)))

    with open(csv_1t, 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            s = r['scene']
            n = int(r['n'])
            if s in PAPER_SCENES:
                col_idx = 0
                for idx, sc in enumerate(PAPER_SCALES):
                    if abs(n - sc) <= 24:
                        col_idx = idx
                        break
                row_idx = PAPER_SCENES.index(s)
                data_1t_broad[row_idx, col_idx] = float(r['speedup_broadphase'])
                data_1t_step[row_idx, col_idx] = float(r['speedup_step'])

    with open(csv_8t, 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            s = r['scene']
            n = int(r['n'])
            if s in PAPER_SCENES:
                col_idx = 0
                for idx, sc in enumerate(PAPER_SCALES):
                    if abs(n - sc) <= 24:
                        col_idx = idx
                        break
                row_idx = PAPER_SCENES.index(s)
                data_8t_broad[row_idx, col_idx] = float(r['speedup_broadphase'])
                data_8t_step[row_idx, col_idx] = float(r['speedup_step'])

    colors = [
        (0.00, '#b2182b'),
        (0.20, '#d6604d'),
        (0.35, '#f4a582'),
        (0.46, '#fddbc7'),
        (0.50, '#ffffff'),
        (0.54, '#d9f0d3'),
        (0.65, '#a6dba0'),
        (0.80, '#5aae61'),
        (1.00, '#1b7837'),
    ]
    cmap = LinearSegmentedColormap.from_list('speedup_divergent', [(pos, col) for pos, col in colors], N=256)

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.0))
    panels = [
        (axes[0, 0], data_1t_broad, "(a) Broad-Phase Monothread", 0.35, 2.20),
        (axes[0, 1], data_8t_broad, "(b) Broad-Phase Multithread", 0.60, 1.25),
        (axes[1, 0], data_1t_step,  "(c) Step Global Monothread", 0.90, 1.15),
        (axes[1, 1], data_8t_step,  "(d) Step Global Multithread", 0.90, 1.15),
    ]
    scale_labels = ['64', '128', '256', '512', '1024']

    for ax, mat, title, vmin, vmax in panels:
        norm = TwoSlopeNorm(vmin=vmin, vcenter=1.00, vmax=vmax)
        im = ax.imshow(mat, cmap=cmap, norm=norm, aspect='auto')
        ax.set_title(title, fontweight='bold', pad=6)
        ax.set_xticks(range(len(PAPER_SCALES)))
        ax.set_xticklabels(scale_labels)
        ax.set_yticks(range(len(PAPER_SCENES)))
        ax.set_yticklabels([PAPER_SCENE_NAMES[s] for s in PAPER_SCENES])
        ax.set_xlabel("Número de Corpos ($N$)")

        for i in range(len(PAPER_SCENES)):
            for j in range(len(PAPER_SCALES)):
                val = mat[i, j]
                txt = f"{val:.2f}x"
                text_color = "white" if (val < 0.52 or val > 1.45) else "black"
                ax.text(j, i, txt, ha='center', va='center', fontsize=7.5,
                        fontweight='bold', color=text_color)

    plt.tight_layout()
    pdf_path = os.path.join(out_dir, "fig_heatmap_speedup.pdf")
    png_path = os.path.join(out_dir, "fig_heatmap_speedup.png")
    png12_path = os.path.join(out_dir, "fig_12_heatmap_speedup.png")
    fig.savefig(pdf_path, bbox_inches='tight')
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(png12_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  [OK] Speedup heatmap saved: {png12_path}")


def plot_topology_curves(scale_8t_csv=None, output_dir=None):
    if not HAS_MATPLOTLIB:
        return
    csv_8t = scale_8t_csv or DEFAULT_SCALE_8T_CSV
    out_dir = output_dir or DEFAULT_OUTPUT_DIR

    if not os.path.exists(csv_8t):
        print(f"  [SKIP] Topology curves skipped: CSV not found ({csv_8t})")
        return

    data = {s: {'n': [], 'nat_h': [], 'sd_h': [], 'nat_sah': [], 'sd_sah': []} for s in PAPER_SCENES}
    with open(csv_8t, 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            s = r['scene']
            if s in data:
                n = int(r['n'])
                data[s]['n'].append(n)
                data[s]['nat_h'].append(int(r['native_height']))
                data[s]['sd_h'].append(int(r['sdbvh_height']))
                data[s]['nat_sah'].append(float(r['native_sah']))
                data[s]['sd_sah'].append(float(r['sdbvh_sah']))

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2))

    n_ideal = np.array([64, 128, 256, 512, 1024])
    h_ideal = np.ceil(np.log2(n_ideal))
    axes[0].plot(n_ideal, h_ideal, 'k:', label=r'Piso Teórico $\lceil\log_2 N\rceil$', linewidth=1.4)

    for s in PAPER_SCENES:
        d = data[s]
        axes[0].plot(d['n'], d['nat_h'], linestyle='--', color=PAPER_SCENE_COLORS[s],
                     alpha=0.6, marker=PAPER_SCENE_MARKERS[s], markersize=4)
        axes[0].plot(d['n'], d['sd_h'], linestyle='-', color=PAPER_SCENE_COLORS[s],
                     label=PAPER_SCENE_NAMES[s], marker=PAPER_SCENE_MARKERS[s], markersize=5)

    axes[0].set_xscale('log', base=2)
    axes[0].set_xticks(PAPER_SCALES)
    axes[0].get_xaxis().set_major_formatter(ticker.ScalarFormatter())
    axes[0].set_title(r"(a) Altura da Hierarquia ($H$)")
    axes[0].set_xlabel("Número de Corpos ($N$)")
    axes[0].set_ylabel("Profundidade Máxima (Níveis)")
    axes[0].grid(True)
    axes[0].legend(loc='upper left', fontsize=7.5, framealpha=0.9)

    for s in PAPER_SCENES:
        d = data[s]
        axes[1].plot(d['n'], d['nat_sah'], linestyle='--', color=PAPER_SCENE_COLORS[s],
                     alpha=0.6, marker=PAPER_SCENE_MARKERS[s], markersize=4)
        axes[1].plot(d['n'], d['sd_sah'], linestyle='-', color=PAPER_SCENE_COLORS[s],
                     label=PAPER_SCENE_NAMES[s], marker=PAPER_SCENE_MARKERS[s], markersize=5)

    axes[1].set_xscale('log', base=2)
    axes[1].set_xticks(PAPER_SCALES)
    axes[1].get_xaxis().set_major_formatter(ticker.ScalarFormatter())
    axes[1].set_title(r"(b) Custo $C_{\text{SAH}}$ Normalizado Médio")
    axes[1].set_xlabel("Número de Corpos ($N$)")
    axes[1].set_ylabel(r"$C_{\text{SAH}}$")
    axes[1].grid(True)

    fig.text(0.5, -0.02, "Linhas sólidas (-) = SDBVH | Linhas tracejadas (--) = Box3D Nativo",
             ha='center', fontsize=8, style='italic')

    plt.tight_layout()
    pdf_path = os.path.join(out_dir, "fig_topologia_escala.pdf")
    png_path = os.path.join(out_dir, "fig_topologia_escala.png")
    png13_path = os.path.join(out_dir, "fig_13_topologia_escala.png")
    fig.savefig(pdf_path, bbox_inches='tight')
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(png13_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  [OK] Topology curves saved: {png13_path}")


def plot_stress_10k_bars(stress_10k_csv=None, output_dir=None):
    if not HAS_MATPLOTLIB:
        return
    csv_10k = stress_10k_csv or DEFAULT_STRESS_10K_CSV
    out_dir = output_dir or DEFAULT_OUTPUT_DIR

    if not os.path.exists(csv_10k):
        print(f"  [SKIP] Stress 10k chart skipped: CSV not found ({csv_10k})")
        return

    stress_data = {}
    with open(csv_10k, 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            s = r['scene']
            stress_data[s] = {
                'nat_h': int(r['native_height']),
                'sd_h': int(r['sdbvh_height']),
                'nat_sah': float(r['native_sah_norm']),
                'sd_sah': float(r['sdbvh_sah_norm']),
                'bp_speedup': float(r['speedup_broadphase']),
                'step_speedup': float(r['speedup_step']),
                'nat_pairs': float(r['native_pairs_ms']),
                'sd_pairs': float(r['sdbvh_pairs_ms']),
                'nat_step': float(r['native_step_ms']),
                'sd_step': float(r['sdbvh_step_ms'])
            }

    fig, axes = plt.subplots(1, 3, figsize=(8.2, 3.2))
    x = np.arange(len(PAPER_SCENES))
    width = 0.40

    color_box3d = '#1f77b4'
    color_sdbvh = '#d62728'

    nat_h = [stress_data[s]['nat_h'] for s in PAPER_SCENES]
    sd_h = [stress_data[s]['sd_h'] for s in PAPER_SCENES]
    ideal_h = 14

    axes[0].bar(x - width/2, nat_h, width, label='Box3D', color=color_box3d, alpha=0.9)
    axes[0].bar(x + width/2, sd_h, width, label='SDBVH', color=color_sdbvh, alpha=0.9)
    axes[0].axhline(ideal_h, color='k', linestyle=':', label=r'Piso $\approx 14$')
    axes[0].set_title(r"(a) Altura da Árvore ($H$)")
    axes[0].set_ylabel("Profundidade")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([s[:4] for s in PAPER_SCENES], rotation=0)
    axes[0].set_ylim(0, 60)
    axes[0].grid(axis='y')
    axes[0].legend(fontsize=7, loc='upper right', framealpha=0.95)

    for i in range(len(PAPER_SCENES)):
        axes[0].text(i - width/2, nat_h[i] + 1.5, f"{nat_h[i]}", ha='center', fontsize=7.2, fontweight='bold')
        axes[0].text(i + width/2, sd_h[i] + 1.5, f"{sd_h[i]}", ha='center', fontsize=7.2, fontweight='bold')

    nat_sah = [stress_data[s]['nat_sah'] for s in PAPER_SCENES]
    sd_sah = [stress_data[s]['sd_sah'] for s in PAPER_SCENES]

    axes[1].bar(x - width/2, nat_sah, width, label='Box3D', color=color_box3d, alpha=0.9)
    axes[1].bar(x + width/2, sd_sah, width, label='SDBVH', color=color_sdbvh, alpha=0.9)
    axes[1].set_title(r"(b) Custo $C_{\text{SAH}}$ Médio")
    axes[1].set_ylabel(r"$C_{\text{SAH}}$")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([s[:4] for s in PAPER_SCENES], rotation=0)
    axes[1].set_ylim(0, 165)
    axes[1].grid(axis='y')
    axes[1].legend(fontsize=7, loc='upper right', framealpha=0.95)

    bp_sp = [stress_data[s]['bp_speedup'] for s in PAPER_SCENES]
    step_sp = [stress_data[s]['step_speedup'] for s in PAPER_SCENES]
    color_bp = '#2b5c8f'
    color_step = '#e08214'

    axes[2].bar(x - width/2, bp_sp, width, label='Broad-Phase', color=color_bp, alpha=0.9)
    axes[2].bar(x + width/2, step_sp, width, label='Step Global', color=color_step, alpha=0.9)
    axes[2].axhline(1.0, color='k', linestyle=':', alpha=0.7)
    axes[2].set_title(r"(c) Speedup ($N=10.000$)")
    axes[2].set_ylabel(r"Speedup Relativo ($\times$)")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels([s[:4] for s in PAPER_SCENES], rotation=0)
    axes[2].set_ylim(0, 1.45)
    axes[2].grid(axis='y')
    axes[2].legend(fontsize=7, loc='upper right', framealpha=0.95)

    for i in range(len(PAPER_SCENES)):
        diff = abs(bp_sp[i] - step_sp[i])
        y_bp = bp_sp[i] + 0.02
        y_step = step_sp[i] + (0.06 if diff < 0.05 else 0.02)
        axes[2].text(i - width/2, y_bp, f"{bp_sp[i]:.2f}", ha='center', va='bottom',
                     color='black', fontsize=6.8, fontweight='bold')
        axes[2].text(i + width/2, y_step, f"{step_sp[i]:.2f}", ha='center', va='bottom',
                     color='black', fontsize=6.8, fontweight='bold')

    plt.tight_layout()
    pdf_path = os.path.join(out_dir, "fig_estresse_10k.pdf")
    png_path = os.path.join(out_dir, "fig_estresse_10k.png")
    png15_path = os.path.join(out_dir, "fig_15_estresse_10k.png")
    fig.savefig(pdf_path, bbox_inches='tight')
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(png15_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  [OK] Stress 10k bars saved: {png15_path}")


def plot_pipeline_breakdown(scale_8t_csv=None, output_dir=None):
    if not HAS_MATPLOTLIB:
        return
    csv_8t = scale_8t_csv or DEFAULT_SCALE_8T_CSV
    out_dir = output_dir or DEFAULT_OUTPUT_DIR

    if not os.path.exists(csv_8t):
        print(f"  [SKIP] Pipeline breakdown skipped: CSV not found ({csv_8t})")
        return

    breakdown = {}
    with open(csv_8t, 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            s = r['scene']
            n = int(r['n'])
            if n >= 1000:
                p = float(r['sdbvh_pairs_ms'])
                c = float(r['sdbvh_collide_ms'])
                sl = float(r['sdbvh_solve_ms'])
                tot = p + c + sl
                breakdown[s] = {
                    'pairs_pct': (p / tot) * 100.0,
                    'collide_pct': (c / tot) * 100.0,
                    'solve_pct': (sl / tot) * 100.0,
                    'step_ms': float(r['sdbvh_step_ms'])
                }

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    y = np.arange(len(PAPER_SCENES))
    height = 0.70

    pairs_pct = [breakdown[s]['pairs_pct'] for s in PAPER_SCENES]
    collide_pct = [breakdown[s]['collide_pct'] for s in PAPER_SCENES]
    solve_pct = [breakdown[s]['solve_pct'] for s in PAPER_SCENES]

    ax.barh(y, pairs_pct, height, label='Broad-Phase (pairs_ms)', color='#2ca02c', alpha=0.9)
    ax.barh(y, collide_pct, height, left=pairs_pct, label='Narrow-Phase (collide_ms)', color='#1f77b4', alpha=0.9)
    left_c = np.array(pairs_pct) + np.array(collide_pct)
    ax.barh(y, solve_pct, height, left=left_c, label='Constraint Solver (solve_ms)', color='#d62728', alpha=0.9)

    ax.set_yticks(y)
    ax.set_yticklabels([PAPER_SCENE_NAMES[s] for s in PAPER_SCENES])
    ax.set_xlabel("Fração do Tempo do Passo (%)", labelpad=8)
    ax.set_title("Decomposição do Pipeline de Física (8 Workers, $N \\approx 1024$)", pad=10)
    ax.set_xlim(0, 100)
    ax.grid(axis='x')

    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.24), ncol=3, frameon=True,
              facecolor='white', framealpha=0.95, fontsize=8)

    for i in range(len(PAPER_SCENES)):
        if pairs_pct[i] >= 6.0:
            ax.text(pairs_pct[i]/2, i, f"{pairs_pct[i]:.1f}%", ha='center', va='center',
                    color='white', fontsize=7.5, fontweight='bold')
        elif pairs_pct[i] >= 3.5:
            ax.text(pairs_pct[i]/2 + 0.4, i, f"{pairs_pct[i]:.1f}%", ha='center', va='center',
                    color='white', fontsize=6.2, fontweight='bold')
        ax.text(pairs_pct[i] + collide_pct[i]/2, i, f"{collide_pct[i]:.1f}%", ha='center', va='center',
                color='white', fontsize=8, fontweight='bold')
        ax.text(left_c[i] + solve_pct[i]/2, i, f"{solve_pct[i]:.1f}%", ha='center', va='center',
                color='white', fontsize=8, fontweight='bold')

    plt.tight_layout()
    pdf_path = os.path.join(out_dir, "fig_decomposicao_pipeline.pdf")
    png_path = os.path.join(out_dir, "fig_decomposicao_pipeline.png")
    png14_path = os.path.join(out_dir, "fig_14_decomposicao_pipeline.png")
    fig.savefig(pdf_path, bbox_inches='tight')
    fig.savefig(png_path, dpi=300, bbox_inches='tight')
    fig.savefig(png14_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  [OK] Pipeline breakdown saved: {png14_path}")


def plot_comparison_suite(output_dir=None, scale_1t_csv=None, scale_8t_csv=None, stress_10k_csv=None):
    print("\n--- Generating Benchmark Comparison Figures ---")
    plot_speedup_heatmaps(scale_1t_csv, scale_8t_csv, output_dir)
    plot_topology_curves(scale_8t_csv, output_dir)
    plot_stress_10k_bars(stress_10k_csv, output_dir)
    plot_pipeline_breakdown(scale_8t_csv, output_dir)

# Backward compatibility alias
plot_paper_suite = plot_comparison_suite


# =============================================================================
# CLI Main
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Plot and diagram generator for Box3D and SDBVH benchmarks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Make all figures, diagrams, and comparison charts:
  python tools/plot_charts.py --all

  # Make multi-scale benchmark comparison figures (heatmaps, topology curves, breakdown, 10k):
  python tools/plot_charts.py --comparison-suite

  # Make telemetry charts only:
  python tools/plot_charts.py --telemetry-suite

  # Make architectural diagrams in SVG and PNG format:
  python tools/plot_charts.py --diagrams

  # Plot custom benchmark CSV files:
  python tools/plot_charts.py file1.csv file2.csv --labels "Native" "SDBVH"
        """
    )
    parser.add_argument("files", nargs="*", help="Optional CSV files to compare.")
    parser.add_argument("--all", action="store_true", help="Make all charts, diagrams, and benchmark comparison figures.")
    parser.add_argument("--comparison-suite", "--paper", "--paper-charts", dest="paper_charts", action="store_true", help="Generate multi-scale benchmark comparison figures.")
    parser.add_argument("--telemetry-suite", "--metrics-suite", dest="telemetry_suite", action="store_true", help="Make all telemetry charts.")
    parser.add_argument("--diagrams", action="store_true", help="Make architectural diagrams in SVG and PNG format.")
    parser.add_argument("--telemetry", action="store_true", help="Make the 4-panel telemetry dashboard.")
    parser.add_argument("--speedup", action="store_true", help="Make the scale sweep speedup chart.")
    parser.add_argument("--timeseries", action="store_true", help="Make timeseries charts for height, broadphase, contacts, and step time.")
    parser.add_argument("--labels", nargs="*", help="Labels for the custom datasets.")
    parser.add_argument("-o", "--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"Directory to save figures (default: {DEFAULT_OUTPUT_DIR}).")
    parser.add_argument("--suite-dir", default=DEFAULT_SUITE_1000_DIR, help=f"Directory of 1000-body benchmark results (default: {DEFAULT_SUITE_1000_DIR}).")
    parser.add_argument("--scale-csv", default=DEFAULT_SCALE_SWEEP_CSV, help=f"Path to scale sweep summary CSV file (default: {DEFAULT_SCALE_SWEEP_CSV}).")
    parser.add_argument("--scale-8t-csv", default=DEFAULT_SCALE_8T_CSV, help=f"Path to multithread scale sweep CSV file (default: {DEFAULT_SCALE_8T_CSV}).")
    parser.add_argument("--stress-10k-csv", default=DEFAULT_STRESS_10K_CSV, help=f"Path to 10k stress test summary CSV file (default: {DEFAULT_STRESS_10K_CSV}).")
    return parser.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    if args.files:
        plot_custom_benchmarks(args.files, args.labels, args.output_dir)
        return

    has_specific = (args.paper_charts or args.telemetry_suite or args.diagrams or
                    args.telemetry or args.speedup or args.timeseries)
    run_all = args.all or not has_specific

    print("==================================================")
    print(" Box3D / SDBVH Plot & Diagram Generator")
    print(f" Output Directory: {args.output_dir}")
    print("==================================================")

    # 1. Multi-scale benchmark comparison figures
    if run_all or args.paper_charts:
        plot_comparison_suite(args.output_dir, args.scale_csv, args.scale_8t_csv, args.stress_10k_csv)

    # 2. Architectural diagrams
    if run_all or args.diagrams:
        print("\n--- Generating Architectural Diagrams ---")
        svg6 = os.path.join(args.output_dir, "fig_6_dual_tier.svg")
        png6 = os.path.join(args.output_dir, "fig_6_dual_tier.png")
        create_dual_tier_svg(svg6)
        render_svg_to_png(svg6, png6, 1200, 540)

        svg7 = os.path.join(args.output_dir, "fig_7_binned_sah.svg")
        png7 = os.path.join(args.output_dir, "fig_7_binned_sah.png")
        create_binned_sah_svg(svg7)
        render_svg_to_png(svg7, png7, 1200, 560)

    # 3. Performance and telemetry charts
    if run_all or args.telemetry_suite or args.timeseries:
        print("\n--- Generating Timeseries Charts ---")
        plot_height_evolution(args.suite_dir, args.output_dir)
        plot_broadphase_time(args.suite_dir, args.output_dir)
        plot_contacts_parity(args.suite_dir, args.output_dir)
        plot_step_time(args.suite_dir, args.output_dir)

    if run_all or args.telemetry_suite or args.speedup:
        print("\n--- Generating Scale Speedup Chart ---")
        plot_speedup_scale(args.scale_csv, args.output_dir)

    if run_all or args.telemetry_suite or args.telemetry:
        print("\n--- Generating 4-Panel Telemetry Dashboard ---")
        plot_combined_4panel(args.suite_dir, args.output_dir)

    print("\n[SUCCESS] All requested charts and diagrams successfully generated in:", args.output_dir)


if __name__ == "__main__":
    main()
