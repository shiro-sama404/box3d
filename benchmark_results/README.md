# Catálogo de Resultados de Benchmark: SDBVH e Box3D

Este diretório contém os dados e gráficos dos benchmarks do Box3D e da SDBVH.

---

## 1. Estrutura de Diretórios

Os conjuntos de dados seguem a estrutura por data (`DD-MM-YYYY`):

```text
benchmark_results/
├── 01-11-2026/
│   ├── plots/
│   │   ├── fig_13_grafico_speedup_escala.png
│   │   ├── grafico_speedup_escala.pdf
│   │   └── grafico_speedup_escala.png
│   └── results/
│       ├── detailed_scale_64_to_1024.csv
│       └── summary_scale_64_to_1024.csv
│
├── 05-11-2026/
│   ├── plots/
│   │   ├── fig_10_grafico_telemetria_completa.png
│   │   ├── grafico_altura_tempo.pdf / .png
│   │   ├── grafico_broadphase_tempo.pdf / .png
│   │   ├── grafico_contatos_tempo.pdf / .png
│   │   ├── grafico_step_tempo.pdf / .png
│   │   └── grafico_telemetria_completa.pdf / .png
│   └── results/
│       ├── bench_convex_pile_1000_native.csv
│       ├── bench_convex_pile_1000_sdbvh.csv
│       ├── bench_junkyard_1500_native.csv
│       ├── bench_junkyard_1500_sdbvh.csv
│       ├── bench_many_pyramids_100_native.csv
│       ├── bench_many_pyramids_100_sdbvh.csv
│       ├── bench_ragdoll_pile_400_native.csv
│       ├── bench_ragdoll_pile_400_sdbvh.csv
│       ├── bench_ragdoll_pile_1000_native.csv
│       ├── bench_ragdoll_pile_1000_sdbvh.csv
│       ├── bench_spinner_400_native.csv
│       ├── bench_spinner_400_sdbvh.csv
│       └── summary.csv
│
└── 06-11-2026/
    ├── plots/
    │   └── custom_benchmark_comparison.png
    └── results/
        ├── bench_junkyard_1500_native.csv
        ├── bench_junkyard_1500_sdbvh.csv
        ├── bench_spinner_400_sdbvh.csv
        ├── detailed_large_scale_10k_100k.csv
        └── summary_large_scale_10k_100k.csv
```

---

## 2. Nomenclatura dos Arquivos

Cada subdiretório de data possui duas pastas:
- `/plots`: armazena as figuras e gráficos em formatos `.png` e `.pdf`.
- `/results`: armazena os arquivos de dados brutos `.csv` no formato `bench_nome_da_cena_quantidade_de_steps_[broadphase].csv`.

Exemplo: `bench_ragdoll_pile_1000_native.csv` ou `bench_ragdoll_pile_1000_sdbvh.csv`.

---

## 3. Resumo dos Conjuntos de Dados

### 3.1. `01-11-2026` (Varredura de Escala 64 a 1024 Corpos)
- Avalia o speedup para contagens de corpos de 64 a 1024.
- Contém 5 repetições para cada configuração.

### 3.2. `05-11-2026` (Suíte Canônica de 1.000 Corpos)
- Executa as cinco cenas de teste com 1.000 corpos:
  - `convex_pile` (1000 passos)
  - `junkyard` (1500 passos)
  - `many_pyramids` (100 passos)
  - `ragdoll_pile` (400 passos)
  - `spinner` (400 passos)
- Compara a implementação Box3D Nativo contra a SDBVH.

### 3.3. `06-11-2026` (Testes de Estresse de 10.000 e 100.000 Corpos)
- Avalia o comportamento assintótico sob alta contagem de corpos.
- Contém os ensaios de estresse extremo de memória e estabilidade da hierarquia.

---

## 4. Colunas dos Arquivos CSV

| Coluna | Unidade | Descrição |
| :--- | :---: | :--- |
| `frame` / `step` | inteiro | Índice do passo de integração física |
| `pairs_ms` | ms | Tempo na fase ampla (broad-phase) |
| `collide_ms` | ms | Tempo na fase estreita (narrow-phase GJK/EPA) |
| `solve_ms` | ms | Tempo no solucionador de restrições (PGS) |
| `step_ms` | ms | Tempo global do passo físico |
| `contact_count` | inteiro | Quantidade de pares de contato confirmados |
| `tree_height` | inteiro | Altura máxima da árvore delimitadora |
| `rebuild_count` | inteiro | Quantidade de subárvores reconstruídas no passo |

---

## 5. Como Executar os Benchmarks

Para executar novos benchmarks e gerar os gráficos:

1. **Compilar o projeto em modo Release:**
   ```powershell
   cmake -B build -G "Ninja" -DCMAKE_BUILD_TYPE=Release
   cmake --build build --config Release
   ```

2. **Executar a suíte canônica:**
   ```powershell
   python tools/run_benchmarks.py --preset canonical-1000
   ```

3. **Gerar os gráficos das suítes:**
   ```powershell
   python tools/plot_charts.py --all
   ```
