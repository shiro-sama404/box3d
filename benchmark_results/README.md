# Catálogo de Resultados de Benchmark: SDBVH vs Box3D Nativo

Este diretório armazena todos os registros empíricos, séries temporais em formato CSV, relatórios analíticos em HTML e resumos estatísticos gerados durante a pesquisa e validação experimental da **SDBVH** (*Stable Dynamic Bounding Volume Hierarchy*), desenvolvida como Trabalho de Conclusão de Curso (TCC) em Ciência da Computação na UFMS.

---

## 1. Estrutura e Organização de Diretórios

Os conjuntos de dados estão organizados cronologicamente e categorizados pelo objetivo experimental:

```
benchmark_results/
├── 2026-09-28_heuristics_and_initial_scale/
│   ├── benchmark_*_500.csv / results_*.csv       # Exploração de heurísticas (Area Ratio vs Subtree SAH, predição, limiares)
│   ├── scale_128..1024_*.csv                     # Primeira varredura de escala em pilha de convexos
│   ├── scale_report_dashboard.html               # Relatório HTML visual da varredura preliminar
│   ├── report_dashboard.html                     # Painel consolidado da primeira bateria
│   └── plots_*/                                  # Curvas temporais e distribuições de área
│
├── 2026-10-05_pure_broadphase_and_grid/
│   ├── pure_broadphase_summary.csv               # Comparativo isolado da Broad-Phase sem resolvedor físico
│   └── grid_experiment/                          # Avaliação contra divisão espacial por Grade Uniforme / Spatial Hash
│
├── 2026-10-27_scale_sweep_128_to_10k/
│   ├── scale_<cenario>_<N>_<nativo|sdbvh>.csv    # Varredura completa em 5 cenas (128 a 10.000 corpos)
│   ├── benchmark_spinner_*.csv                   # Testes de concorrência com 1 vs 4 threads no Spinner
│   ├── summary_scale_128_to_10000_all_scenes.csv # Tabela resumo consolidada de todos os regimes
│   └── relatorio_escala_completa_128_10000.html  # Dashboard interativo com gráficos de escalabilidade
│
├── 2026-11-01_canonical_suite_1000/
│   ├── bench1000_<cenario>_<nativo|sdbvh>.csv    # Suíte canônica com 1.000 corpos ao longo de 500 passos
│   └── summary_1000_objects_5scenes.csv          # Resumo estatístico das 5 cenas canônicas
│
├── 2026-11-01_scale_sweep_64_to_1024/
│   ├── detailed_scale_64_to_1024.csv             # Amostras individuais por passo com 5 repetições
│   └── summary_scale_64_to_1024.csv              # Médias, medianas e desvio padrão para N in [64, 1024]
│
└── 2026-11-01_stress_test_10k_to_100k/
    ├── detailed_large_scale_10k_100k.csv         # Telemetria passo a passo para N = 10.000 e 100.000 corpos
    └── summary_large_scale_10k_100k.csv          # Resumo de tempo e altura assintótica para estresse extremo
```

---

## 2. Detalhamento das Baterias Experimentais

### 2.1. `2026-09-28_heuristics_and_initial_scale`
- **Objetivo:** Investigar e comparar diferentes métricas analíticas de qualidade para guiar a reconstrução seletiva da árvore dinâmica:
  - Heurística de Razão de Área ($\rho_{\text{area}} = S_{\text{atual}} / S_{\text{construção}}$);
  - Custo SAH acumulado de subárvore ($\alpha_k$);
  - Influência do multiplicador de predição cinemática ($\beta$) e limiares de ativação ($\tau \in [1.2, 2.0]$).
- **Cenário:** `convex_pile` inicial com 500 corpos e ensaios de 128 a 1024 corpos.

### 2.2. `2026-10-05_pure_broadphase_and_grid`
- **Objetivo:** Mensurar o tempo de processamento estritamente consumido pela *broad-phase* (inserção, remoção, refit e travessia mútua de pares) de forma desacoplada do restante do motor (sem despacho para o GJK/EPA e sem resolução de restrições do PGS solver).
- **Comparativo:** Box3D Nativo (`b3DynamicTree`), SDBVH e estrutura baseada em *Uniform Grid / Spatial Hash*.

### 2.3. `2026-10-27_scale_sweep_128_to_10k`
- **Objetivo:** Avaliar a evolução temporal e a estabilidade da altura da árvore sob varredura exponencial de $N \in \{128, 256, 512, 1.000, 10.000\}$ corpos através de cinco regimes físicos contrastantes:
  1. `convex_pile`: Colapso gravitacional violento seguido de repouso progressivo;
  2. `many_pyramids`: Empilhamento estruturado quase-estático;
  3. `spinner`: Agitação turbulenta contínua (pior caso teórico de coerência temporal);
  4. `junkyard`: Agitação induzida por atuador cinemático periódico;
  5. `ragdoll_pile`: Sistemas multicorpos articulados por restrições mecânicas.
- **Destaque:** Demonstração empírica da contenção da altura da árvore na SDBVH ($H = 16$ versus $H = 47$ no Nativo para 10.000 corpos).

### 2.4. `2026-11-01_canonical_suite_1000`
- **Objetivo:** Estabelecer uma linha de base estável e de alta amostragem estatística com exatamente **1.000 corpos** e **500 passos temporais** ($dt = 1/60\,\text{s}$) nas cinco cenas representativas, comparando o Box3D nativo contra a SDBVH com o pipeline de otimização integrado.
- **Métricas:** Resumo direto das médias em regime permanente em `summary_1000_objects_5scenes.csv`.

### 2.5. `2026-11-01_scale_sweep_64_to_1024`
- **Objetivo:** Varredura detalhada de baixa e média densidade ($N \in \{64, 128, 256, 512, 1024\}$) com **5 repetições completas** por configuração para análise de dispersão amostral, variância e determinação do ponto de inflexão de custo fixo (*overhead* vs *gain*).

### 2.6. `2026-11-01_stress_test_10k_to_100k`
- **Objetivo:** Teste de estresse assintótico em escala extrema ($10.000$ e $100.000$ corpos) em regime consolidado para avaliar a retenção em cache da CPU, o consumo de memória RAM e a estabilidade numérica da hierarquia.

---

## 3. Descrição das Colunas e Métricas Registradas

Os arquivos `.csv` registram telemetria detalhada a cada passo temporal de simulação:

| Coluna | Unidade | Descrição |
| :--- | :---: | :--- |
| `step` | inteiro | Índice sequencial do passo de integração física ($0, 1, 2, \dots$) |
| `pairs_ms` | milissegundos | Tempo gasto estritamente na fase ampla (*broad-phase*) para geração de pares |
| `collide_ms` | milissegundos | Tempo consumido pela fase estreita (*narrow-phase*) executando GJK/EPA |
| `solve_ms` | milissegundos | Tempo consumido pelo solucionador de restrições de contato (*Projected Gauss-Seidel*) |
| `step_ms` | milissegundos | Tempo global do passo físico completo do motor |
| `pairs_count` | inteiro | Quantidade de pares candidatos a colisão gerados pela *broad-phase* |
| `contacts_count` | inteiro | Quantidade de pares com contato físico real confirmados pela *narrow-phase* |
| `tree_height` | inteiro | Altura máxima atual da árvore delimitadora ($H$) |
| `rebuild_count` | inteiro | Quantidade de ramos de subárvore reconstruídos via *Binned SAH* no passo |

---

## 4. Como Executar e Reproduzir os Experimentos

Os scripts de execução encontram-se em `tools/` e utilizam o binário de benchmark compilado (`build/bin/benchmark.exe`):

1. **Compilação do motor em modo Release:**
   ```powershell
   cmake -B build -G "Ninja" -DCMAKE_BUILD_TYPE=Release
   cmake --build build --config Release
   ```

2. **Executar a Suíte Canônica de 1.000 Corpos:**
   ```powershell
   python tools/run_benchmark_1000.py
   ```

3. **Executar a Varredura 64 a 1024 Corpos:**
   ```powershell
   python tools/run_scale_64_to_1024.py
   ```

4. **Executar os Testes de Larga Escala (10k e 100k):**
   ```powershell
   python tools/run_large_scale_10k_100k.py
   ```

