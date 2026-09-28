# Guia de Automação de Benchmarks e Avaliação de Qualidade de Árvore (TCC)

Este documento descreve a infraestrutura de benchmarks automatizados do **Box3D**, o cálculo analítico de custo SAH contra a árvore de referência **Ground Truth (Full Binned SAH)** e o pipeline de geração de relatórios e gráficos estatísticos.

---

## 1. Executável de Benchmark (`benchmark.exe`)

O binário `build/bin/benchmark.exe` executa simulações sem interface gráfica a 60 Hz, coletando tempos de perfil e métricas de qualidade estrutural a cada quadro.

### 1.1. Sintaxe Geral

```powershell
.\build\bin\benchmark.exe -b=<nome> [opções]
```

### 1.2. Tabela de Argumentos

| Argumento | Descrição | Valores Possíveis | Padrão |
| :--- | :--- | :--- | :--- |
| `-b, --benchmark` | Nome do benchmark a executar | `convex_pile`, `washer`, `junkyard`, `rain`, etc. | Todos |
| `--steps` | Quantidade de quadros (steps) de simulação | Inteiro $\ge 1$ | Definido pelo teste |
| `-w, --workers` | Número fixo de threads de processamento | Inteiro $1 \dots 16$ | $1$ |
| `-r, --repeats` | Número de repetições por teste | Inteiro $\ge 1$ | $4$ |
| `-bp, --broadphase` | Implementação de Broad-Phase | `native` (Box3D `b3DynamicTree`) ou `dbvh` | `native` |
| `-m, --metric` | Métrica de gatilho para Rebuild na DBVH | `area_ratio` (ou `0`) / `subtree_sah` (ou `1`) | `area_ratio` |
| `-th, --threshold` | Limiar para disparar o Rebuild | Float $> 0$ | `1.50` (AreaRatio) / `0.40` (SubtreeSAH) |
| `--rebuild` | Habilita/desabilita manutenção por rebuild | `on` / `off` | `on` |
| `--fattening` | Expansão de segurança (fat AABB) | `on` / `off` | `on` |
| `--predictive` | Expansão preditiva baseada em velocidade | `on` / `off` | `on` |
| `--rotations` | Rotações locais de árvore (`tryRotate`) | `on` / `off` | `off` |
| `-gt, --ground-truth` | Constrói a árvore ideal Full Binned SAH a cada frame | Flag (sem valor) | Desativado |
| `-c, --csv` | Exporta métricas detalhadas em `.csv` | Flag (sem valor) | Desativado |
| `-o, --output-csv` | Nome do arquivo CSV de saída (salvo em `benchmark_results/`) | String | Auto-gerado |
| `-nc, --no-continuous`| Desabilita detecção contínua de colisão (CCD) | Flag | Ativado |
| `-l, --list` | Lista todos os benchmarks disponíveis | Flag | — |
| `-h, --help` | Exibe a mensagem de ajuda | Flag | — |

---

## 2. Exemplos de Execução Comparativa

### Comparando Box3D Nativo vs. DBVH (Area Ratio) vs. DBVH (Subtree SAH)

Execute os três testes a partir da raiz do projeto:

```powershell
# 1. Box3D Nativo (com Ground Truth)
.\build\bin\benchmark.exe -b convex_pile --steps 100 -w 1 -r 1 -bp native -gt -o results_native.csv

# 2. DBVH com Rebuild por Razão de Área (Area Ratio = 1.50)
.\build\bin\benchmark.exe -b convex_pile --steps 100 -w 1 -r 1 -bp dbvh -m area_ratio -th 1.50 -gt -o results_dbvh_arearatio.csv

# 3. DBVH com Rebuild por Métrica Analítica (Subtree SAH alpha = 0.40)
.\build\bin\benchmark.exe -b convex_pile --steps 100 -w 1 -r 1 -bp dbvh -m subtree_sah -th 0.40 -gt -o results_dbvh_subtreesah.csv
```

Todos os arquivos `.csv` serão gravados automaticamente dentro do diretório `benchmark_results/`.

---

## 3. Script de Visualização e Estatísticas (`tools/plot_benchmarks.py`)

O script `tools/plot_benchmarks.py` lê os arquivos `.csv` exportados, imprime um resumo estatístico no terminal e gera um dashboard HTML interativo com gráficos vetoriais SVG de alta resolução.

### 3.1. Como Executar

```powershell
# Processa automaticamente todos os CSVs presentes em benchmark_results/
python tools/plot_benchmarks.py

# Ou especifica arquivos e rótulos personalizados:
python tools/plot_benchmarks.py benchmark_results/results_native.csv benchmark_results/results_dbvh_arearatio.csv benchmark_results/results_dbvh_subtreesah.csv --labels "Box3D Nativo" "DBVH (Area Ratio)" "DBVH (Subtree SAH alpha)"
```

### 3.2. Saídas Geradas

O script gera os seguintes arquivos dentro do diretório `benchmark_results/`:
* **`report_dashboard.html`**: Dashboard visual completo contendo a tabela estatística e todos os gráficos vetoriais SVG incorporados (pode ser aberto diretamente no navegador).

---

## 4. Estrutura dos Arquivos CSV e Métricas

Cada arquivo `.csv` possui as seguintes colunas por frame:

| Coluna | Significado | Unidade |
| :--- | :--- | :--- |
| `frame` | Índice do passo de simulação (0, 1, 2, ...) | Número inteiro |
| `step_ms` | Tempo total do passo de física | Milissegundos (ms) |
| `pairs_ms` | Tempo gasto na Broad-Phase (`FindPairs`) | Milissegundos (ms) |
| `collide_ms` | Tempo gasto na Narrow-Phase (detecção detalhada) | Milissegundos (ms) |
| `solve_ms` | Tempo gasto no Solver de Restrições (contatos/juntas) | Milissegundos (ms) |
| `tree_height` | Altura máxima da árvore ativa | Níveis |
| `leaf_count` | Quantidade de folhas ativas | Inteiro |
| `node_count` | Quantidade total de nós (folhas + internos) | Inteiro |
| `sah_standard` | Custo SAH da árvore corrente: $C_t \sum SA_{\text{internos}} + C_i \sum SA_{\text{folhas}}$ | Unidades de Área |
| `sah_normalized` | Custo SAH normalizado da árvore corrente: $\sum SA(n_i) / SA(\text{raiz})$ | Adimensional |
| `ideal_sah_standard`| Custo SAH da árvore ideal (construída do zero via Full Binned SAH) | Unidades de Área |
| `ideal_sah_normalized` | Custo SAH normalizado da árvore ideal | Adimensional |
| `ideal_tree_height` | Altura da árvore ideal Full Binned SAH | Níveis |
| `quality_ratio_standard` | Razão de qualidade: $Q(t) = C_{\text{SAH}}(t) / C_{\text{Ideal}}(t)$ | Adimensional ($1.000\text{x} = \text{Ideal}$) |
| `quality_ratio_normalized`| Razão de qualidade normalizada: $Q_{\text{norm}}(t)$ | Adimensional ($1.000\text{x} = \text{Ideal}$) |

---

## 5. Fundamentação Teórica das Métricas

### 5.1. Custo SAH Padrão ($C_{\text{SAH}}$)
$$C_{\text{SAH}}(T) = C_t \sum_{n \in \text{Internos}} SA(n) + C_i \sum_{n \in \text{Folhas}} SA(n)$$
Mede a probabilidade geométrica média de um raio ou volume colisor atravessar os nós internos da árvore.

### 5.2. Custo SAH Normalizado ($\text{Cost}_{\text{Norm}}$)
$$\text{Cost}_{\text{Norm}}(T) = \frac{\sum_{n \in T} SA(n)}{SA(\text{Raiz})}$$
Independe da escala do mundo e mede a eficiência de empacotamento volumétrico da hierarquia.

### 5.3. Métrica de Degradação $\alpha$ da Subárvore
$$\alpha_k = \frac{\sum_{i \in T_k} SA(n_i)}{SA(n_k) \cdot N_k \log_2(N_k)}$$
Avalia se a subárvore $T_k$ está degenerando em comparação à sua complexidade ótima teórica $N \log_2 N$. Limiar ótimo calibrado: $\mathbf{0.35 \sim 0.50}$.

### 5.4. Razão de Eficiência Estrutural ($Q(t)$)
$$Q(t) = \frac{C_{\text{SAH}}(T)}{C_{\text{SAH}}(T_{\text{Ideal}})} \ge 1.000\text{x}$$
Quando $Q(t) \approx 1.000\text{x}$, a árvore dinâmica opera no limite de qualidade de uma árvore totalmente reconstruída do zero com o estado ótimo dos objetos naquele instante.
