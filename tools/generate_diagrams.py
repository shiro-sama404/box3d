import os
import subprocess

def create_dual_tier_svg():
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

  <!-- Background -->
  <rect width="{width}" height="{height}" fill="#FFFFFF"/>

  <!-- Title & Subtitle Bar -->
  <text x="600" y="32" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="20" font-weight="bold" fill="#263238" text-anchor="middle">
    Arquitetura Concorrente Dual-Tier: Simulação Síncrona e Reconstrução por Árvore-Sombra
  </text>

  <!-- Thread Swimlanes -->
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

  <!-- ==================== (a) PASSO t: Simulação Síncrona e Detecção ==================== -->
  <!-- Step t Container -->
  <g transform="translate(60, 95)">
    <rect width="320" height="150" rx="8" fill="#FFFFFF" stroke="#64B5F6" stroke-width="1.5" filter="url(#shadow)"/>
    <rect x="0" y="0" width="320" height="26" rx="6" fill="#E3F2FD"/>
    <text x="10" y="18" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" font-weight="bold" fill="#0D47A1">
      (a) Passo t: Manutenção Incremental SDBVH
    </text>

    <!-- Mini Flow within Step t -->
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

    <!-- Degradation check box -->
    <rect x="15" y="92" width="292" height="46" rx="4" fill="#FFEBEE" stroke="#E57373" stroke-width="1"/>
    <text x="25" y="108" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#C62828">
      Monitor de Degradação: Avalia ρ_area(Nk) = S(Nk) / S_base
    </text>
    <text x="25" y="125" font-family="Segoe UI, Arial" font-size="10" fill="#B71C1C">
      Condição atendida: <tspan font-weight="bold">ρ_area ≥ 1.8</tspan> → <tspan fill="#D32F2F" font-weight="bold">Dispara Sinal de Reconstrução</tspan>
    </text>
  </g>

  <!-- Dispatch Signal Down Arrow -->
  <path d="M 220 248 L 220 330" fill="none" stroke="#D32F2F" stroke-width="2.5" stroke-dasharray="5,4" marker-end="url(#arrowOrange)"/>
  <rect x="150" y="260" width="140" height="24" rx="4" fill="#FFFFFF" stroke="#D32F2F" stroke-width="1" filter="url(#shadow)"/>
  <text x="220" y="276" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#C62828" text-anchor="middle">
    b3Semaphore Post()
  </text>

  <!-- ==================== (b) WORKER: Reconstrução Binned SAH ==================== -->
  <g transform="translate(180, 335)">
    <rect width="450" height="145" rx="8" fill="#FFFFFF" stroke="#FFB74D" stroke-width="1.5" filter="url(#shadow)"/>
    <rect x="0" y="0" width="450" height="26" rx="6" fill="#FFF3E0"/>
    <text x="10" y="18" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" font-weight="bold" fill="#E65100">
      (b) Execução Concorrente: Reconstrução por Árvore-Sombra (Shadow Tree)
    </text>

    <!-- Step b details -->
    <!-- Stage 1 -->
    <rect x="15" y="38" width="125" height="52" rx="4" fill="#FFE0B2" stroke="#FB8C00" stroke-width="1"/>
    <text x="77" y="55" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#E65100" text-anchor="middle">1. Clonagem Isolada</text>
    <text x="77" y="70" font-family="Segoe UI, Arial" font-size="9" fill="#BF360C" text-anchor="middle">Cópia do ramo Nk para</text>
    <text x="77" y="82" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#BF360C" text-anchor="middle">Árvore-Sombra</text>

    <line x1="142" y1="64" x2="158" y2="64" stroke="#FB8C00" stroke-width="1.5" marker-end="url(#arrowOrange)"/>

    <!-- Stage 2 -->
    <rect x="160" y="38" width="140" height="52" rx="4" fill="#FFE0B2" stroke="#FB8C00" stroke-width="1"/>
    <text x="230" y="55" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#E65100" text-anchor="middle">2. Binned SAH (12 Baldes)</text>
    <text x="230" y="70" font-family="Segoe UI, Arial" font-size="9" fill="#BF360C" text-anchor="middle">Varredura prefixo/sufixo</text>
    <text x="230" y="82" font-family="Segoe UI, Arial" font-size="9" fill="#BF360C" text-anchor="middle">Partição ótima de folhas</text>

    <line x1="302" y1="64" x2="318" y2="64" stroke="#FB8C00" stroke-width="1.5" marker-end="url(#arrowOrange)"/>

    <!-- Stage 3 -->
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

  <!-- Concurrent steps on Main Thread while worker runs -->
  <g transform="translate(420, 95)">
    <!-- Step t+1 -->
    <rect width="140" height="90" rx="6" fill="#F5F5F5" stroke="#B0BEC5" stroke-width="1"/>
    <text x="70" y="20" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#455A64" text-anchor="middle">Passo t+1</text>
    <text x="70" y="42" font-family="Segoe UI, Arial" font-size="9" fill="#607D8B" text-anchor="middle">Simulação Ativa</text>
    <text x="70" y="58" font-family="Segoe UI, Arial" font-size="9" fill="#607D8B" text-anchor="middle">(refit + micro-rot.)</text>
    <text x="70" y="76" font-family="Segoe UI, Arial" font-size="9" font-style="italic" fill="#78909C" text-anchor="middle">Worker executando...</text>
  </g>
  <g transform="translate(580, 95)">
    <!-- Step t+2 -->
    <rect width="140" height="90" rx="6" fill="#F5F5F5" stroke="#B0BEC5" stroke-width="1"/>
    <text x="70" y="20" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#455A64" text-anchor="middle">Passo t+2</text>
    <text x="70" y="42" font-family="Segoe UI, Arial" font-size="9" fill="#607D8B" text-anchor="middle">Simulação Ativa</text>
    <text x="70" y="58" font-family="Segoe UI, Arial" font-size="9" fill="#607D8B" text-anchor="middle">(refit + micro-rot.)</text>
    <text x="70" y="76" font-family="Segoe UI, Arial" font-size="9" font-style="italic" fill="#78909C" text-anchor="middle">Worker finalizando...</text>
  </g>

  <!-- Arrow from Worker finish to Sync point -->
  <path d="M 630 380 C 720 380, 750 330, 770 230" fill="none" stroke="#2E7D32" stroke-width="2.5" marker-end="url(#arrowGreen)"/>

  <!-- ==================== (c) SINCRONIZAÇÃO: Pointer Swap ==================== -->
  <g transform="translate(750, 95)">
    <rect width="380" height="150" rx="8" fill="url(#swapGrad)" stroke="#81C784" stroke-width="2" filter="url(#shadow)"/>
    <rect x="0" y="0" width="380" height="26" rx="6" fill="#C8E6C9"/>
    <text x="10" y="18" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" font-weight="bold" fill="#1B5E20">
      (c) Início do Passo t+3: Troca Atômica (Pointer Swap)
    </text>

    <!-- Pointer Swap Box -->
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

  <!-- Legend bottom -->
  <g transform="translate(300, 508)">
    <rect x="0" y="0" width="14" height="14" rx="2" fill="#1976D2"/>
    <text x="20" y="12" font-family="Segoe UI, Arial" font-size="11" fill="#37474F">Main Thread (Física Síncrona)</text>

    <rect x="200" y="0" width="14" height="14" rx="2" fill="#F57C00"/>
    <text x="220" y="12" font-family="Segoe UI, Arial" font-size="11" fill="#37474F">Worker Thread (Shadow Tree)</text>

    <rect x="420" y="0" width="14" height="14" rx="2" fill="#2E7D32"/>
    <text x="440" y="12" font-family="Segoe UI, Arial" font-size="11" fill="#37474F">Sincronização Atômica O(1)</text>
  </g>
</svg>'''
    with open('local/text/figures/fig_6_dual_tier.svg', 'w', encoding='utf-8') as f:
        f.write(svg)
    print("Created fig_6_dual_tier.svg")

def create_binned_sah_svg():
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

  <!-- Background -->
  <rect width="{width}" height="{height}" fill="#FFFFFF"/>

  <!-- Title -->
  <text x="600" y="32" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="20" font-weight="bold" fill="#263238" text-anchor="middle">
    Partição Linear Binned SAH com 12 Baldes Discretos
  </text>

  <!-- ==================== PAINEL (a): EIXO DE MAIOR EXTENSÃO ==================== -->
  <g transform="translate(30, 55)">
    <rect width="360" height="450" rx="8" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1.5" filter="url(#shadow2)"/>
    <rect x="0" y="0" width="360" height="32" rx="6" fill="#E2E8F0"/>
    <text x="12" y="21" font-family="Segoe UI, Arial" font-size="13" font-weight="bold" fill="#1E293B">
      (a) Seleção do Eixo de Maior Extensão
    </text>

    <!-- Subtitle -->
    <text x="180" y="54" font-family="Segoe UI, Arial" font-size="11" fill="#64748B" text-anchor="middle">
      Caixa Envoltória dos Centróides (B_centróides)
    </text>

    <!-- Bounding box of centroids (dashed) -->
    <rect x="40" y="80" width="280" height="150" fill="#F1F5F9" stroke="#0284C7" stroke-width="2" stroke-dasharray="6,4"/>
    <text x="180" y="74" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#0284C7" text-anchor="middle">
      Δx = max(Δx, Δy, Δz) → EIXO X SELECIONADO
    </text>

    <!-- Dimension arrows -->
    <!-- Width dx -->
    <line x1="40" y1="240" x2="320" y2="240" stroke="#0284C7" stroke-width="1.5" marker-start="url(#arrowB)" marker-end="url(#arrowB)"/>
    <text x="180" y="255" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#0284C7" text-anchor="middle">
      Extensão Δx = 28.0 m (Maior Dispersão)
    </text>

    <!-- Height dy -->
    <line x1="335" y1="80" x2="335" y2="230" stroke="#64748B" stroke-width="1.5" marker-start="url(#arrowB)" marker-end="url(#arrowB)"/>
    <text x="340" y="160" font-family="Segoe UI, Arial" font-size="10" fill="#64748B" transform="rotate(90, 340, 160)" text-anchor="middle">
      Δy = 15.0 m
    </text>

    <!-- Sample leaves and centroids inside -->
    <!-- Leaf 1 -->
    <rect x="55" y="100" width="35" height="40" fill="#E2E8F0" stroke="#94A3B8" stroke-width="1" rx="3"/>
    <circle cx="72" cy="120" r="4" fill="#EF4444"/>
    <text x="72" y="112" font-family="Segoe UI, Arial" font-size="8" fill="#1E293B" text-anchor="middle">c1</text>

    <!-- Leaf 2 -->
    <rect x="100" y="150" width="45" height="30" fill="#E2E8F0" stroke="#94A3B8" stroke-width="1" rx="3"/>
    <circle cx="122" cy="165" r="4" fill="#EF4444"/>
    <text x="122" y="157" font-family="Segoe UI, Arial" font-size="8" fill="#1E293B" text-anchor="middle">c2</text>

    <!-- Leaf 3 -->
    <rect x="160" y="95" width="40" height="45" fill="#E2E8F0" stroke="#94A3B8" stroke-width="1" rx="3"/>
    <circle cx="180" cy="117" r="4" fill="#EF4444"/>
    <text x="180" y="109" font-family="Segoe UI, Arial" font-size="8" fill="#1E293B" text-anchor="middle">c3</text>

    <!-- Leaf 4 -->
    <rect x="220" y="140" width="30" height="35" fill="#E2E8F0" stroke="#94A3B8" stroke-width="1" rx="3"/>
    <circle cx="235" cy="157" r="4" fill="#EF4444"/>
    <text x="235" y="149" font-family="Segoe UI, Arial" font-size="8" fill="#1E293B" text-anchor="middle">c4</text>

    <!-- Leaf 5 -->
    <rect x="265" y="110" width="45" height="50" fill="#E2E8F0" stroke="#94A3B8" stroke-width="1" rx="3"/>
    <circle cx="287" cy="135" r="4" fill="#EF4444"/>
    <text x="287" y="127" font-family="Segoe UI, Arial" font-size="8" fill="#1E293B" text-anchor="middle">c5</text>

    <!-- Explanation Box at bottom of Panel a -->
    <rect x="15" y="280" width="330" height="150" rx="6" fill="#EFF6FF" stroke="#BFDBFE" stroke-width="1"/>
    <text x="25" y="302" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#1E40AF">Procedimento:</text>
    <text x="25" y="322" font-family="Segoe UI, Arial" font-size="10" fill="#1E3A8A">1. Extrai K folhas da subárvore degradada.</text>
    <text x="25" y="342" font-family="Segoe UI, Arial" font-size="10" fill="#1E3A8A">2. Calcula centróide ci = 0.5 * (min + max) de cada folha.</text>
    <text x="25" y="362" font-family="Segoe UI, Arial" font-size="10" fill="#1E3A8A">3. Encontra bounding box de todos os centróides.</text>
    <text x="25" y="382" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#0284C7">4. Eixo com maior dispersão (ΔE) é escolhido</text>
    <text x="35" y="398" font-family="Segoe UI, Arial" font-size="10" fill="#0369A1">para garantir partições com menor sobreposição.</text>
    <text x="25" y="418" font-family="Segoe UI, Arial" font-size="9" fill="#64748B">• Círculos vermelhos: Centróides das geometrias</text>
  </g>

  <!-- ==================== PAINEL (b): PROJEÇÃO EM 12 BALDES ==================== -->
  <g transform="translate(410, 55)">
    <rect width="370" height="450" rx="8" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1.5" filter="url(#shadow2)"/>
    <rect x="0" y="0" width="370" height="32" rx="6" fill="#E2E8F0"/>
    <text x="12" y="21" font-family="Segoe UI, Arial" font-size="13" font-weight="bold" fill="#1E293B">
      (b) Discretização em 12 Baldes Uniformes
    </text>

    <!-- Formula Display -->
    <rect x="15" y="45" width="340" height="42" rx="4" fill="#F1F5F9" stroke="#E2E8F0" stroke-width="1"/>
    <text x="185" y="62" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#334155" text-anchor="middle">
      Mapeamento O(K) de cada Centróide ci:
    </text>
    <text x="185" y="78" font-family="Consolas, monospace" font-size="10" fill="#0369A1" text-anchor="middle">
      b_i = clamp( ⌊12 * (c_i,x - min_x) / Δx⌋, 0, 11 )
    </text>

    <!-- 12 Buckets Visualization -->
    <g transform="translate(15, 105)">
      <!-- 12 Buckets Boxes -->
'''
    # Render 12 bucket bars
    bucket_w = 28
    bucket_gap = 1
    total_w = 12 * (bucket_w + bucket_gap)
    # Buckets counts
    counts = [1, 0, 2, 0, 3, 1, 4, 2, 0, 1, 2, 1]
    for b in range(12):
        bx = b * (bucket_w + bucket_gap)
        svg += f'''
      <rect x="{bx}" y="40" width="{bucket_w}" height="90" fill="#E0F2FE" stroke="#0284C7" stroke-width="1" rx="2"/>
      <text x="{bx + bucket_w/2}" y="32" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#0369A1" text-anchor="middle">B{b}</text>
      <!-- Count badge -->
      <rect x="{bx + 3}" y="{130 - counts[b]*15}" width="{bucket_w - 6}" height="{counts[b]*15}" fill="#38BDF8" rx="2"/>
      <text x="{bx + bucket_w/2}" y="125" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#0C4A6E" text-anchor="middle">{counts[b]}</text>
'''
    svg += f'''
      <!-- Axis line below -->
      <line x1="0" y1="140" x2="{total_w}" y2="140" stroke="#0284C7" stroke-width="2"/>
      <text x="0" y="155" font-family="Segoe UI, Arial" font-size="9" fill="#0369A1">min_x</text>
      <text x="{total_w}" y="155" font-family="Segoe UI, Arial" font-size="9" fill="#0369A1" text-anchor="end">max_x</text>
      <text x="{total_w/2}" y="155" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#0369A1" text-anchor="middle">Eixo X (12 Baldes)</text>
    </g>

    <!-- Accumulated state of buckets -->
    <rect x="15" y="280" width="340" height="150" rx="6" fill="#F0FDF4" stroke="#BBF7D0" stroke-width="1"/>
    <text x="25" y="302" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#166534">Dados Acumulados por Balde:</text>
    <text x="25" y="322" font-family="Segoe UI, Arial" font-size="10" fill="#14532D">• <tspan font-weight="bold">count[b]:</tspan> Quantidade de geometrias no balde b.</text>
    <text x="25" y="342" font-family="Segoe UI, Arial" font-size="10" fill="#14532D">• <tspan font-weight="bold">aabb[b]:</tspan> União das AABBs dos corpos mapeados.</text>
    <text x="25" y="365" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#15803D">Complexidade O(K):</text>
    <text x="25" y="382" font-family="Segoe UI, Arial" font-size="10" fill="#166534">Uma única varredura linear projeta todas as K folhas</text>
    <text x="25" y="398" font-family="Segoe UI, Arial" font-size="10" fill="#166534">nos 12 baldes sem ordenar os centróides (evita O(K log K)).</text>
    <text x="25" y="418" font-family="Segoe UI, Arial" font-size="9" fill="#64748B">Inspirado na implementação Ds (Pagliosa) e PBRT.</text>
  </g>

  <!-- ==================== PAINEL (c): VARREDURAS PREFIXO/SUFIXO E PLANO ÓTIMO ==================== -->
  <g transform="translate(800, 55)">
    <rect width="370" height="450" rx="8" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1.5" filter="url(#shadow2)"/>
    <rect x="0" y="0" width="370" height="32" rx="6" fill="#E2E8F0"/>
    <text x="12" y="21" font-family="Segoe UI, Arial" font-size="13" font-weight="bold" fill="#1E293B">
      (c) Varreduras e Plano Ótimo (11 Candidatos)
    </text>

    <!-- Two scan arrows -->
    <!-- Prefix scan (left to right) -->
    <g transform="translate(20, 48)">
      <rect width="330" height="30" rx="4" fill="#EFF6FF" stroke="#BFDBFE" stroke-width="1"/>
      <line x1="10" y1="15" x2="310" y2="15" stroke="#1D4ED8" stroke-width="2" marker-end="url(#arrowBlue2)"/>
      <text x="160" y="12" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#1D4ED8" text-anchor="middle">
        Varredura de Prefixo (Esq → Dir): B_esq[p], N_esq[p]
      </text>
    </g>

    <!-- Suffix scan (right to left) -->
    <g transform="translate(20, 85)">
      <rect width="330" height="30" rx="4" fill="#FFF7ED" stroke="#FFEDD5" stroke-width="1"/>
      <line x1="310" y1="15" x2="10" y2="15" stroke="#EA580C" stroke-width="2" marker-end="url(#arrowOrange2)"/>
      <text x="160" y="12" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#EA580C" text-anchor="middle">
        Varredura de Sufixo (Dir → Esq): B_dir[p], N_dir[p]
      </text>
    </g>

    <!-- SAH Cost Evaluation Curve -->
    <g transform="translate(20, 125)">
      <rect width="330" height="140" rx="6" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1"/>
      <text x="165" y="18" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#334155" text-anchor="middle">
        Curva de Custo SAH dos 11 Planos Candidatos
      </text>

      <!-- Grid lines -->
      <line x1="30" y1="110" x2="310" y2="110" stroke="#CBD5E1" stroke-width="1"/>
      <line x1="30" y1="30" x2="30" y2="110" stroke="#CBD5E1" stroke-width="1"/>

      <!-- Cost curve path -->
      <path d="M 40 45 Q 90 75, 140 100 T 200 85 T 260 55 T 300 40" fill="none" stroke="#64748B" stroke-width="2"/>

      <!-- Cost points on each split plane p0 to p10 -->
'''
    # Cost points for p0 to p10
    cost_pts = [
        (45, 50), (70, 68), (95, 82), (120, 93),
        (145, 102), # p4 = minimum
        (170, 95), (195, 88), (220, 75), (245, 63), (270, 52), (295, 42)
    ]
    for idx, (px, py) in enumerate(cost_pts):
        is_min = (idx == 4)
        col = "#16A34A" if is_min else "#64748B"
        r = 5 if is_min else 3
        svg += f'''      <circle cx="{px}" cy="{py}" r="{r}" fill="{col}"/>
'''
    svg += f'''
      <!-- Highlight Minimum Point (p4 / p_ótimo) -->
      <line x1="145" y1="28" x2="145" y2="110" stroke="#16A34A" stroke-width="1.5" stroke-dasharray="3,3"/>
      <rect x="105" y="22" width="80" height="18" rx="3" fill="#DCFCE7" stroke="#16A34A" stroke-width="1"/>
      <text x="145" y="34" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#15803D" text-anchor="middle">p_ótimo (C_min)</text>
      <text x="145" y="122" font-family="Segoe UI, Arial" font-size="8" font-weight="bold" fill="#16A34A" text-anchor="middle">Plano 4</text>

      <text x="25" y="30" font-family="Segoe UI, Arial" font-size="8" fill="#64748B">Custo</text>
      <text x="310" y="122" font-family="Segoe UI, Arial" font-size="8" fill="#64748B">Planos p0..p10</text>
    </g>

    <!-- SAH Cost Formula & In-Place Partition -->
    <rect x="15" y="280" width="340" height="150" rx="6" fill="#FEF3C7" stroke="#FDE68A" stroke-width="1"/>
    <text x="25" y="302" font-family="Segoe UI, Arial" font-size="11" font-weight="bold" fill="#92400E">Decisão de Partição Ótima:</text>
    <text x="25" y="322" font-family="Segoe UI, Arial" font-size="9" fill="#78350F">C_split(p) = C_T + (S(B_esq)/S_total)*N_esq*C_I + (S(B_dir)/S_total)*N_dir*C_I</text>
    <text x="25" y="346" font-family="Segoe UI, Arial" font-size="10" font-weight="bold" fill="#B45309">1. Seleciona plano p com menor C_split.</text>
    <text x="25" y="366" font-family="Segoe UI, Arial" font-size="10" fill="#92400E">2. Particiona o vetor de folhas no local (in-place).</text>
    <text x="25" y="386" font-family="Segoe UI, Arial" font-size="10" fill="#92400E">3. Recursão para filho esquerdo e direito.</text>
    <text x="25" y="412" font-family="Segoe UI, Arial" font-size="9" font-weight="bold" fill="#15803D">Resultado: Árvore SAH compacta com O(K) total!</text>
  </g>
</svg>'''
    with open('local/text/figures/fig_7_binned_sah.svg', 'w', encoding='utf-8') as f:
        f.write(svg)
    print("Created fig_7_binned_sah.svg")

def render_svg_to_png(svg_path, png_path, width, height):
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge_path):
        print(f"Edge not found at {edge_path}")
        return

    # Wrap in minimal HTML for perfect viewport scaling
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

    cmd = [
        edge_path,
        "--headless",
        "--disable-gpu",
        f"--window-size={width},{height}",
        f"--screenshot={abs_png}",
        f"file:///{abs_html}"
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    if os.path.exists(html_path):
        os.remove(html_path)
    print(f"Rendered {abs_png} ({width}x{height})")

if __name__ == '__main__':
    create_dual_tier_svg()
    create_binned_sah_svg()
    render_svg_to_png('local/text/figures/fig_6_dual_tier.svg', 'local/text/figures/fig_6_dual_tier.png', 1200, 540)
    render_svg_to_png('local/text/figures/fig_7_binned_sah.svg', 'local/text/figures/fig_7_binned_sah.png', 1200, 560)

