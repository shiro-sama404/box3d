# Ferramentas de Benchmark, Telemetria e Compilação

Este diretório contém a suíte unificada de ferramentas para executar benchmarks, processar telemetria estatística, gerar figuras e diagramas de desempenho e compilar a documentação técnica em LaTeX para o Box3D e SDBVH.

---

## 1. Visão Geral das Ferramentas

| Ferramenta | Descrição Principal | Comandos Típicos |
| :--- | :--- | :--- |
| [`run_benchmarks.py`](run_benchmarks.py) | **Executor e Analisador Geral de Benchmarks** | Presets (`--preset canonical-1000`, `scale-sweep`), análise (`--analyze`) e comparação de CSVs (`--compare`) |
| [`run_scale_sweep.py`](run_scale_sweep.py) | **Suíte Automatizada de Varredura de Escala** | Bateria completa (64 a 1.024 corpos) em mono (-w 1) e multithread (-w 8), com variância e agregação |
| [`plot_charts.py`](plot_charts.py) | **Gerador Unificado de Gráficos e Diagramas** | Comparação multi-escala (`--comparison-suite`), painéis de telemetria (`--telemetry-suite`), diagramas SVG/PNG (`--diagrams`) e `--all` |
| [`compile_docs.py`](compile_docs.py) | **Compilador e Verificador de Documentação** | Compilação via Tectonic (`main.tex` -> `main.pdf`), contagem de páginas e checagem de referências quebradas |
| [`download_tectonic.ps1`](download_tectonic.ps1) | **Instalador Automatizado do Tectonic** | Download e extração do binário do Tectonic MSVC para `tools/tectonic/` |

---

## 2. `run_benchmarks.py` — Executor e Analisador de Benchmarks

O script `run_benchmarks.py` gerencia o executável de testes do Box3D (`bin/benchmark.exe` ou `build/bin/benchmark.exe`).

### 2.1 Presets Padronizados
```bash
# Suíte canônica com 1.000 corpos (5 cenas calibradas)
python tools/run_benchmarks.py --preset canonical-1000

# Varredura de escala
python tools/run_benchmarks.py --preset scale-sweep

# Testes de estresse com 10.000 e 100.000 corpos
python tools/run_benchmarks.py --preset stress-10k
python tools/run_benchmarks.py --preset stress-100k
```

### 2.2 Parâmetros Customizados
```bash
python tools/run_benchmarks.py \
  --scenes convex_pile,ragdoll_pile,spinner \
  --actors 1000 \
  --steps 400 \
  --repeats 3 \
  --workers 8 \
  --broadphases native,sdbvh \
  --threshold 1.8 \
  --output-dir benchmark_results/custom_run
```

### 2.3 Inspeção e Comparação de Resultados
```bash
# Analisa métricas sumarizadas de um arquivo CSV:
python tools/run_benchmarks.py --analyze benchmark_results/exemplo.csv

# Compara dois arquivos lado a lado:
python tools/run_benchmarks.py --compare run_native.csv run_sdbvh.csv
```

---

## 3. `run_scale_sweep.py` — Varredura de Escala Automatizada

Automatiza a bateria completa de 25 configurações de escala ($N \in \{64, 128, 256, 512, 1024\}$ corpos) nas 5 cenas canônicas com 5 repetições e passos calibrados por cena:

```bash
# Execução monothread (1 worker)
python tools/run_scale_sweep.py -w 1 -r 5

# Execução multithread (8 workers)
python tools/run_scale_sweep.py -w 8 -r 5

# Execução de ambas as baterias sequencialmente
python tools/run_scale_sweep.py -w 1,8 -r 5
```

Gera automaticamente os arquivos consolidados:
- `summary_scale_monothread.csv` (ou `summary_scale_multithread.csv`)
- `detailed_scale_monothread.csv` (com todas as repetições individuais)
- Sumários estruturados prontos para incorporação em relatórios técnicos.

---

## 4. `plot_charts.py` — Gerador Unificado de Gráficos e Diagramas

Centraliza toda a geração visual em alta resolução (vetorial PDF e imagens PNG a 300 DPI) para o diretório `local/text/figures/`:

```bash
# Gera TODAS as figuras comparativas, telemetria e diagramas:
python tools/plot_charts.py --all

# Gera a suíte de figuras comparativas multi-escala:
python tools/plot_charts.py --comparison-suite
```

### Figuras de Comparação Multi-Escala (`--comparison-suite`):
- `fig_12_heatmap_speedup.png / .pdf`: Matrizes de calor de speedup na fase ampla e passo global (mono e multithread).
- `fig_13_topologia_escala.png / .pdf`: Curvas de integridade topológica (altura $H$ e custo $C_{\text{SAH}}$ versus $N$).
- `fig_14_decomposicao_pipeline.png / .pdf`: Decomposição temporal do ciclo de simulação (*pipeline breakdown*).
- `fig_15_estresse_10k.png / .pdf`: Desempenho no teste de estresse assintótico com 10.000 corpos.

### Diagramas e Séries Temporais:
- `--diagrams`: Gera os diagramas arquiteturais `fig_6_dual_tier` e `fig_7_binned_sah` em SVG e PNG.
- `--telemetry-suite`: Gera gráficos de altura, fase ampla, contatos e tempo total ao longo do tempo.
- `--speedup`: Curva de aceleração relativa por escala.

---

## 5. `compile_docs.py` — Compilação e Verificação de Documentação

Compila o documento LaTeX de documentação técnica através do compilador Tectonic e executa auditoria de formatação:

```bash
python tools/compile_docs.py
```

- Compila `local/text/main.tex` gerando `local/text/main.pdf`.
- Valida integridade das referências cruzadas (verifica se há `??`).
- Verifica a contagem de páginas e a correta extração de figuras e tabelas.
- Caso o Tectonic não esteja presente, utilize `powershell tools/download_tectonic.ps1` para instalação automática.
