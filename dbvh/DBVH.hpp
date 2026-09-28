/// @file DBVH.hpp
/// Dynamic Bounding Volume Hierarchy (DBVH) para detecção de colisões

#pragma once

#include "Vec3.h"
#include "AABB.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace dbvh
{

// ============================================================================
// Constantes e aliases
// ============================================================================

static constexpr int32_t NULL_NODE = -1;

using NodeIndex = int32_t;
using LeafPair = std::pair<size_t, size_t>;

/// @brief Métricas para avaliação de degradação da árvore.
enum class DegradationMetric : uint8_t
{
    AreaRatio = 0,   // Métrica clássica: Área Atual / Área de Construção (threshold 1.5)
    SubtreeSAH = 1,  // Métrica normalizada alpha_k: sum(SA_descendentes) / (SA_k * N_k * log2(N_k))
};

/// @brief Configurações de execução e manutenção da DBVH.
struct DBVHConfig
{
    bool enableRebuild{true};
    bool enableFattening{true};
    bool enablePredictive{false};
    bool enableRotations{false};
    DegradationMetric metric{DegradationMetric::AreaRatio};
    float areaRatioThreshold{1.8f};
    float subtreeSAHThreshold{1.8f};
    float rebuildThreshold{1.8f}; // Compatibilidade
    int32_t rebuildInterval{30};
    int32_t maxRebuildsPerFrame{2};
    bool enableAdaptiveRebuild{true};
    int32_t maxSubtreeLeaves{64};
};

/// @brief Métricas e custo SAH da árvore para avaliação de qualidade e benchmarks.
struct TreeQualityMetrics
{
    float sahCostStandard{0.0f};   // C_t * sum(SA_internos) + C_i * sum(SA_folhas)
    float sahCostNormalized{0.0f}; // sum(SA_todos) / SA_raiz
    float rootArea{0.0f};
    int treeHeight{0};
    int leafCount{0};
    int nodeCount{0};
};

/// @brief Pilha pré-alocada para travessias iterativas.
/// Elimina alocações heap em hot-paths e maximiza localidade de cache L1.
/// @tparam T Tipo do elemento.
/// @tparam N Capacidade máxima.
template <typename T, size_t N>
struct FixedStack
{
    std::array<T, N> data;
    std::vector<T> overflow;
    size_t top{0};

    void push(const T& val)
    {
        if (top < N)
            data[top] = val;
        else
            overflow.push_back(val);
        top++;
    }

    T pop() noexcept
    {
        assert(top > 0 && "FixedStack underflow");
        top--;
        if (top < N)
            return data[top];
        else
        {
            T val = overflow.back();
            overflow.pop_back();
            return val;
        }
    }

    [[nodiscard]] T& peek() noexcept
    {
        assert(top > 0 && "FixedStack peek on empty");
        if (top - 1 < N)
            return data[top - 1];
        else
            return overflow.back();
    }

    [[nodiscard]] bool empty() const noexcept { return top == 0; }
    [[nodiscard]] size_t size() const noexcept { return top; }
};

// ============================================================================
// Traits — Configuração de tipos geométricos
// ============================================================================

/// @brief Traits padrão que mapeia para os tipos dbvh::AABB e dbvh::Vec3.
struct DefaultBVHTraits
{
    using AABBType = AABB;
    using VecType  = Vec3;

    [[nodiscard]] static constexpr float surfaceArea(const AABBType& a) noexcept
    { return a.surfaceArea(); }

    [[nodiscard]] static constexpr bool overlaps(const AABBType& a, const AABBType& b) noexcept
    { return a.overlaps(b); }

    [[nodiscard]] static constexpr bool contains(const AABBType& a, const AABBType& b) noexcept
    { return a.contains(b); }

    [[nodiscard]] static constexpr AABBType unite(const AABBType& a, const AABBType& b) noexcept
    { return AABBType::unite(a, b); }

    [[nodiscard]] static constexpr VecType centroid(const AABBType& a) noexcept
    { return a.centroid(); }

    static constexpr void expand(AABBType& a, float eps) noexcept
    { a.expand(eps); }

    static void expandPredictive(AABBType& a, const VecType& vel, float dt = (1.0f / 60.0f)) noexcept
    { a.expandPredictive(vel, dt); }

    [[nodiscard]] static constexpr bool rayIntersects(const AABBType& a, const VecType& origin, const VecType& invDir, float maxFraction) noexcept
    { return a.rayIntersects(origin, invDir, maxFraction); }

    /// @brief Acessa o componente do eixo (0=x, 1=y, 2=z) de um vetor.
    [[nodiscard]] static constexpr float getAxis(const VecType& v, int axis) noexcept
    { return (axis == 0) ? v.x : (axis == 1) ? v.y : v.z; }

    /// @brief Acessa o min do eixo de um AABB.
    [[nodiscard]] static constexpr float getMin(const AABBType& a, int axis) noexcept
    { return (axis == 0) ? a.min.x : (axis == 1) ? a.min.y : a.min.z; }

    /// @brief Acessa o max do eixo de um AABB.
    [[nodiscard]] static constexpr float getMax(const AABBType& a, int axis) noexcept
    { return (axis == 0) ? a.max.x : (axis == 1) ? a.max.y : a.max.z; }

    /// @brief Constrói o inverso da direção (para ray cast).
    [[nodiscard]] static VecType inverseDirection(const VecType& dir) noexcept
    {
        return VecType(
            dir.x != 0.0f ? 1.0f / dir.x : 0.0f,
            dir.y != 0.0f ? 1.0f / dir.y : 0.0f,
            dir.z != 0.0f ? 1.0f / dir.z : 0.0f
        );
    }
};

// ============================================================================
// Node — Nó da árvore
// ============================================================================

/// @brief Nó da árvore: folha ou interno.
/// @tparam T Tipo do dado de usuário (apenas folhas).
/// @tparam AABBType Tipo do bounding box (derivado dos Traits).
template <typename T, typename AABBType = AABB>
struct alignas(64) Node
{
    AABBType aabb;                                           // 24 bytes
    NodeIndex parent{NULL_NODE};                             //  4 bytes
    std::array<NodeIndex, 2> child = {NULL_NODE, NULL_NODE}; //  8 bytes
    T userData{};                                            //  4 bytes (apenas folhas)
    uint64_t categoryBits{0xFFFFFFFFFFFFFFFFull};            //  8 bytes (filtro de colisão)
    float constructionArea{0.0f};                            //  4 bytes
    float subtreeArea{0.0f};                                 //  4 bytes (Soma de SA de toda a subárvore)
    uint32_t leafCount{1};                                   //  4 bytes (Quantidade de folhas)
    uint16_t flags{0};                                       //  2 bytes
    uint16_t pad{0};                                         //  2 bytes

    [[nodiscard]] bool isLeaf() const noexcept { return child[0] == NULL_NODE; }
    [[nodiscard]] bool isEnlarged() const noexcept { return (flags & 0x02) != 0; }

    void setEnlarged() noexcept { flags |= 0x02; }
    void clearEnlarged() noexcept { flags &= static_cast<uint16_t>(~0x02); }
};

// ============================================================================
// DBVH – Dynamic Bounding Volume Hierarchy
// ============================================================================

/// @brief Estrutura dinâmica de hierarquia de volumes envolventes.
/// @tparam T Tipo do dado armazenado nas folhas.
/// @tparam Traits Struct de traits que define tipos geométricos e operações.
template <typename T, typename Traits = DefaultBVHTraits>
class DBVH
{
public:
    using AABBType = typename Traits::AABBType;
    using VecType  = typename Traits::VecType;
    using NodeType = Node<T, AABBType>;

    DBVH() = default;
    explicit DBVH(size_t initialCapacity);

    // Desabilita cópia
    DBVH(const DBVH&) = delete;
    DBVH& operator=(const DBVH&) = delete;
    DBVH(DBVH&&) = default;
    DBVH& operator=(DBVH&&) = default;

    // --- Operações principais ---

    /// @brief Insere um novo objeto na árvore.
    /// @param leafAABB AABB do objeto
    /// @param userData Dado associado à folha.
    /// @param categoryBits Máscara de bits de categoria para filtragem.
    /// @return Índice da folha criada.
    [[nodiscard]] size_t insert(const AABBType& leafAABB, const T& userData, uint64_t categoryBits = 0xFFFFFFFFFFFFFFFFull);

    /// @brief Define ou atualiza a máscara de bits de categoria de uma folha.
    void setCategoryBits(size_t leafIndex, uint64_t categoryBits);

    /// @brief Remove uma folha da árvore.
    /// @param leafIndex Índice da folha a ser removida.
    void remove(size_t leafIndex);

    /// @brief Move um objeto: atualiza sua AABB e só reinsere se saiu da caixa engordada.
    /// @param leafIndex Índice da folha.
    /// @param newAABB Nova AABB (não engordada).
    /// @param velocity Velocidade do objeto (para expansão preditiva).
    /// @param epsilon Margem de segurança fixa (padrão 0.01).
    [[nodiscard]] size_t moveObject(size_t leafIndex, const AABBType& newAABB, const VecType& velocity, float epsilon = 0.01f);

    /// @brief Amplia a AABB de uma folha e propaga para os ancestrais.
    void enlargeProxy(size_t leafIndex, const AABBType& newAABB);

    // --- Consultas ---

    /// @brief Consulta todas as folhas cujo AABB sobrepõe queryAABB.
    /// @param queryAABB Caixa de consulta.
    /// @param callback Chamado com (leafIndex, userData) para cada folha sobreposta.
    ///        Deve retornar true para continuar ou false para interromper.
    /// @param maskBits Máscara de bits de categoria para filtragem antecipada.
    template <typename F>
    void query(const AABBType& queryAABB, F&& callback, uint64_t maskBits = 0xFFFFFFFFFFFFFFFFull) const;

    /// @brief Consulta rápida repassada diretamente a callback C.
    void queryFast(const AABBType& queryAABB, uint64_t maskBits, bool (*callback)(int32_t proxyId, uint64_t userData, void* context), void* context) const;

    /// @brief Lança um raio contra a árvore.
    /// @param origin Ponto de origem do raio.
    /// @param direction Direção (não necessariamente normalizada; comprimento = alcance).
    /// @param maxFraction Fração máxima [0, 1].
    /// @param callback Chamado com (leafIndex, userData). Deve retornar nova maxFraction.
    template <typename F>
    void rayCast(const VecType& origin, const VecType& direction, float maxFraction, F&& callback) const;

    /// @brief Retorna todos os pares de folhas com AABBs sobrepostos (broad phase).
    /// @return Vetor de pares (leafA, leafB) com leafA <= leafB.
    [[nodiscard]] std::vector<LeafPair> queryPairs() const;

    /// @brief Versão com callback (evita alocação do vetor).
    /// @param callback Função chamada para cada par (leafA, leafB).
    template <typename F>
    void queryPairs(F&& callback) const;

    // --- Manutenção Global ---

    /// @brief Atualiza todos os AABBs da árvore em uma única passagem pós-ordem.
    /// Usado em BLASes deformáveis onde todas as folhas mudam simultaneamente.
    /// @param computeAABB Função que recebe userData de uma folha e retorna seu AABB atualizado.
    template <typename F>
    void refitAll(F&& computeAABB);

    /// @brief Limpa as flags `enlarged` de todos os nós alocados.
    /// Deve ser chamado após cada ciclo de queryPairs.
    void clearAllEnlarged();

    /// @brief Reconstrói uma subárvore (ou a árvore inteira) via SAH top-down binned.
    /// @param subtreeRoot Raiz da subárvore a reconstruir (NULL_NODE = árvore inteira).
    /// @param updateArea Se verdadeiro, recalcula totalTreeArea.
    void rebuild(NodeIndex subtreeRoot = NULL_NODE, bool updateArea = true);

    /// @brief Reconstrói automaticamente subárvores degradadas.
    /// @param threshold Limiar de degradação.
    /// @param metric Métrica utilizada para avaliação da degradação.
    /// @param maxRebuilds Orçamento máximo de subárvores reconstruídas por chamada.
    /// @param maxSubtreeLeaves Limite máximo de folhas por subárvore reconstruída.
    /// @return Número de candidatos a ramos degradados identificados.
    int rebuildDegraded(float threshold, DegradationMetric metric, int maxRebuilds = 2, int maxSubtreeLeaves = 64);

    /// @brief Executa rebuild degraded utilizando as configurações correntes da DBVH.
    int rebuildDegraded()
    {
        if (config.enableRebuild)
        {
            float th = (config.metric == DegradationMetric::AreaRatio) ? config.areaRatioThreshold : config.subtreeSAHThreshold;
            return rebuildDegraded(th, config.metric, config.maxRebuildsPerFrame, config.maxSubtreeLeaves);
        }
        return 0;
    }

    // --- Configuração ---
    void setConfig(const DBVHConfig& cfg) noexcept { config = cfg; }
    [[nodiscard]] const DBVHConfig& getConfig() const noexcept { return config; }
    [[nodiscard]] DBVHConfig& getConfig() noexcept { return config; }

    // --- Acesso e Diagnóstico ---

    [[nodiscard]] const NodeType& getNode(size_t index) const { return nodes[index]; }
    [[nodiscard]] NodeType& getNode(size_t index) { return nodes[index]; }
    [[nodiscard]] NodeIndex getRoot() const { return root; }
    [[nodiscard]] bool isLeaf(size_t index) const { return nodes[index].isLeaf(); }
    [[nodiscard]] size_t nodeCount() const { return nodes.size() - freeList.size(); }
    [[nodiscard]] size_t getLeafCount() const noexcept { return leafCount; }
    [[nodiscard]] float getTotalTreeArea() const noexcept { return totalTreeArea; }
    [[nodiscard]] float getDegradationAlpha() const;
    [[nodiscard]] float computeTotalSurfaceArea() const;
    [[nodiscard]] AABBType getRootBounds() const { return (root != NULL_NODE) ? nodes[root].aabb : AABBType(); }
    [[nodiscard]] int getHeight() const;

    // --- Avaliação de Qualidade e Métricas SAH ---
    [[nodiscard]] TreeQualityMetrics computeQualityMetrics(float traversalCost = 1.0f, float isectCost = 1.0f) const;
    [[nodiscard]] TreeQualityMetrics computeIdealQualityMetrics(float traversalCost = 1.0f, float isectCost = 1.0f) const;
    static TreeQualityMetrics computeIdealFromAABBs(const std::vector<AABBType>& leafAABBs, float traversalCost = 1.0f, float isectCost = 1.0f);

private:
    std::vector<NodeType> nodes;
    std::vector<size_t> freeList;
    NodeIndex root{NULL_NODE};
    DBVHConfig config;
    float totalTreeArea{0.0f};
    size_t leafCount{0};

    int computeSubtreeHeight(NodeIndex nodeIdx) const;

    // --- Gerenciamento de memória ---
    size_t allocateNode();
    void freeNode(size_t idx);

    // --- Manutenção da árvore ---
    void detachLeaf(size_t leafIndex);
    void reinsertLeaf(size_t leafIndex);
    void refitAndRotateAncestors(NodeIndex startNode);                       // Refit + rotação em passada única
    void tryRotate(NodeIndex idx);                                           // Tenta rotações no nó idx
    [[nodiscard]] NodeIndex findBestSibling(const AABBType& leafAABB) const; // Branch‑and‑bound

    // --- Rebuild ---

    /// @brief Coleta todas as folhas de uma subárvore.
    void collectLeaves(NodeIndex node, std::vector<NodeIndex>& out) const;

    /// @brief Libera todos os nós internos de uma subárvore.
    void freeInternalNodes(NodeIndex node);

    /// @brief Constrói uma subárvore via SAH top-down binned.
    NodeIndex buildSubtree(std::vector<NodeIndex>& leaves, size_t start, size_t end);
};

// ============================================================================
// Implementações dos métodos
// ============================================================================

template <typename T, typename Traits>
DBVH<T, Traits>::DBVH(size_t initialCapacity)
{
    nodes.reserve(initialCapacity);
}

template <typename T, typename Traits>
size_t DBVH<T, Traits>::allocateNode()
{
    if (!freeList.empty())
    {
        size_t idx = freeList.back();
        freeList.pop_back();
        nodes[idx] = NodeType(); // Reseta o nó
        return idx;
    }
    nodes.emplace_back();
    return nodes.size() - 1;
}

template <typename T, typename Traits>
void DBVH<T, Traits>::freeNode(size_t idx)
{
    freeList.push_back(idx);
}

template <typename T, typename Traits>
size_t DBVH<T, Traits>::insert(const AABBType& leafAABB, const T& userData, uint64_t categoryBits)
{
    size_t leaf = allocateNode();
    nodes[leaf].aabb = leafAABB;
    nodes[leaf].userData = userData;
    nodes[leaf].categoryBits = categoryBits;
    nodes[leaf].child = {NULL_NODE, NULL_NODE}; // Marca como folha
    nodes[leaf].leafCount = 1;
    nodes[leaf].subtreeArea = Traits::surfaceArea(leafAABB);
    nodes[leaf].constructionArea = nodes[leaf].subtreeArea;
    totalTreeArea += nodes[leaf].subtreeArea;
    leafCount++;

    if (root == NULL_NODE)
    {
        root = static_cast<NodeIndex>(leaf);
        nodes[leaf].parent = NULL_NODE;
        return leaf;
    }

    NodeIndex bestSibling = findBestSibling(leafAABB);
    NodeIndex oldParent = nodes[bestSibling].parent;

    NodeIndex newParent = allocateNode();
    nodes[newParent].aabb = Traits::unite(leafAABB, nodes[bestSibling].aabb);
    nodes[newParent].constructionArea = Traits::surfaceArea(nodes[newParent].aabb);
    nodes[newParent].parent = oldParent;
    nodes[newParent].child = {bestSibling, static_cast<NodeIndex>(leaf)};
    nodes[newParent].categoryBits = nodes[bestSibling].categoryBits | categoryBits;
    nodes[newParent].leafCount = nodes[bestSibling].leafCount + 1;
    nodes[newParent].subtreeArea = nodes[newParent].constructionArea + nodes[bestSibling].subtreeArea + nodes[leaf].subtreeArea;
    totalTreeArea += nodes[newParent].constructionArea;

    nodes[bestSibling].parent = newParent;
    nodes[leaf].parent = newParent;

    if (oldParent == NULL_NODE)
        root = newParent;
    else
        // Substitui bestSibling por newParent no avô
        if (nodes[oldParent].child[0] == bestSibling)
            nodes[oldParent].child[0] = newParent;
        else
            nodes[oldParent].child[1] = newParent;

    refitAndRotateAncestors(newParent);

    return leaf;
}

template <typename T, typename Traits>
void DBVH<T, Traits>::setCategoryBits(size_t leafIndex, uint64_t categoryBits)
{
    assert(isLeaf(leafIndex) && "setCategoryBits() chamado em nó não-folha");
    nodes[leafIndex].categoryBits = categoryBits;
    refitAndRotateAncestors(leafIndex);
}

template <typename T, typename Traits>
void DBVH<T, Traits>::detachLeaf(size_t leafIndex)
{
    if (leafIndex == static_cast<size_t>(root))
    {
        root = NULL_NODE;
        return;
    }

    NodeIndex parent = nodes[leafIndex].parent;
    NodeIndex grandpa = nodes[parent].parent;

    NodeIndex sibling = (nodes[parent].child[0] == static_cast<NodeIndex>(leafIndex))
                        ? nodes[parent].child[1]
                        : nodes[parent].child[0];

    if (grandpa != NULL_NODE)
    {
        if (nodes[grandpa].child[0] == parent)
            nodes[grandpa].child[0] = sibling;
        else
            nodes[grandpa].child[1] = sibling;
        nodes[sibling].parent = grandpa;

        refitAndRotateAncestors(grandpa);
    }
    else
    {
        root = sibling;
        nodes[sibling].parent = NULL_NODE;
    }

    totalTreeArea -= Traits::surfaceArea(nodes[parent].aabb);
    freeNode(parent);
}

template <typename T, typename Traits>
void DBVH<T, Traits>::reinsertLeaf(size_t leafIndex)
{
    const AABBType& leafAABB = nodes[leafIndex].aabb;

    if (root == NULL_NODE)
    {
        root = static_cast<NodeIndex>(leafIndex);
        nodes[leafIndex].parent = NULL_NODE;
        return;
    }

    NodeIndex bestSibling = findBestSibling(leafAABB);
    NodeIndex oldParent = nodes[bestSibling].parent;

    NodeIndex newParent = allocateNode();
    nodes[newParent].aabb = Traits::unite(leafAABB, nodes[bestSibling].aabb);
    nodes[newParent].constructionArea = Traits::surfaceArea(nodes[newParent].aabb);
    nodes[newParent].parent = oldParent;
    nodes[newParent].child = {bestSibling, static_cast<NodeIndex>(leafIndex)};
    nodes[newParent].categoryBits = nodes[bestSibling].categoryBits | nodes[leafIndex].categoryBits;
    nodes[newParent].leafCount = nodes[bestSibling].leafCount + nodes[leafIndex].leafCount;
    nodes[newParent].subtreeArea = nodes[newParent].constructionArea + nodes[bestSibling].subtreeArea + nodes[leafIndex].subtreeArea;
    totalTreeArea += nodes[newParent].constructionArea;

    nodes[bestSibling].parent = newParent;
    nodes[leafIndex].parent = newParent;

    if (oldParent == NULL_NODE)
        root = newParent;
    else
        if (nodes[oldParent].child[0] == bestSibling)
            nodes[oldParent].child[0] = newParent;
        else
            nodes[oldParent].child[1] = newParent;

    refitAndRotateAncestors(newParent);
}

template <typename T, typename Traits>
void DBVH<T, Traits>::remove(size_t leafIndex)
{
    assert(isLeaf(leafIndex) && "remove() chamado em nó não-folha");
    totalTreeArea -= Traits::surfaceArea(nodes[leafIndex].aabb);
    if (leafCount > 0) leafCount--;
    detachLeaf(leafIndex);
    freeNode(leafIndex);
}

template <typename T, typename Traits>
size_t DBVH<T, Traits>::moveObject(size_t leafIndex, const AABBType& newAABB, const VecType& velocity, float epsilon)
{
    assert(isLeaf(leafIndex) && "moveObject() chamado em nó não-folha");

    if (Traits::contains(nodes[leafIndex].aabb, newAABB))
        return leafIndex;

    AABBType fatAABB = newAABB;
    if (config.enableFattening && epsilon > 0.0f)
        Traits::expand(fatAABB, epsilon);
    if (config.enablePredictive)
        Traits::expandPredictive(fatAABB, velocity, 1.0f / 60.0f);

    totalTreeArea -= Traits::surfaceArea(nodes[leafIndex].aabb);
    detachLeaf(leafIndex);
    nodes[leafIndex].aabb = fatAABB;
    nodes[leafIndex].subtreeArea = Traits::surfaceArea(fatAABB);
    nodes[leafIndex].constructionArea = nodes[leafIndex].subtreeArea;
    totalTreeArea += nodes[leafIndex].subtreeArea;
    reinsertLeaf(leafIndex);

    return leafIndex;
}

template <typename T, typename Traits>
void DBVH<T, Traits>::enlargeProxy(size_t leafIndex, const AABBType& newAABB)
{
    assert(isLeaf(leafIndex) && "enlargeProxy() chamado em nó não-folha");

    float oldArea = Traits::surfaceArea(nodes[leafIndex].aabb);
    nodes[leafIndex].aabb = newAABB;
    float newArea = Traits::surfaceArea(newAABB);
    totalTreeArea += (newArea - oldArea);
    nodes[leafIndex].subtreeArea = newArea;
    nodes[leafIndex].setEnlarged();

    NodeIndex idx = nodes[leafIndex].parent;
    while (idx != NULL_NODE)
    {
        NodeType& node = nodes[idx];
        const auto& left = nodes[node.child[0]];
        const auto& right = nodes[node.child[1]];

        AABBType combined = Traits::unite(left.aabb, right.aabb);
        if (Traits::contains(node.aabb, combined))
        {
            break;
        }

        float oldParentArea = Traits::surfaceArea(node.aabb);
        node.aabb = combined;
        float newParentArea = Traits::surfaceArea(node.aabb);
        totalTreeArea += (newParentArea - oldParentArea);
        node.subtreeArea = newParentArea + left.subtreeArea + right.subtreeArea;
        node.setEnlarged();

        idx = node.parent;
    }
}

template <typename T, typename Traits>
template <typename F>
void DBVH<T, Traits>::query(const AABBType& queryAABB, F&& callback, uint64_t maskBits) const
{
    if (root == NULL_NODE) return;

    const NodeType& rootNode = nodes[root];
    if ((rootNode.categoryBits & maskBits) == 0 || !Traits::overlaps(rootNode.aabb, queryAABB))
        return;

    NodeIndex stack[256];
    int stackCount = 0;
    NodeIndex current = root;

    while (current != NULL_NODE)
    {
        const NodeType& node = nodes[current];

        if (node.isLeaf())
        {
            if (!callback(static_cast<size_t>(current), node.userData))
                return;
            current = (stackCount > 0) ? stack[--stackCount] : NULL_NODE;
        }
        else
        {
            NodeIndex c0 = node.child[0];
            NodeIndex c1 = node.child[1];
            const NodeType& n0 = nodes[c0];
            const NodeType& n1 = nodes[c1];

            bool hit0 = ((n0.categoryBits & maskBits) != 0) && Traits::overlaps(n0.aabb, queryAABB);
            bool hit1 = ((n1.categoryBits & maskBits) != 0) && Traits::overlaps(n1.aabb, queryAABB);

            if (hit0 && hit1)
            {
                if (stackCount < 256)
                    stack[stackCount++] = c1;
                current = c0;
            }
            else if (hit0)
                current = c0;
            else if (hit1)
                current = c1;
            else
                current = (stackCount > 0) ? stack[--stackCount] : NULL_NODE;
        }
    }
}

template <typename T, typename Traits>
void DBVH<T, Traits>::queryFast(const AABBType& queryAABB, uint64_t maskBits, bool (*callback)(int32_t proxyId, uint64_t userData, void* context), void* context) const
{
    if (root == NULL_NODE) return;

    const NodeType& rootNode = nodes[root];
    if ((rootNode.categoryBits & maskBits) == 0 || !Traits::overlaps(rootNode.aabb, queryAABB))
        return;

    NodeIndex stack[256];
    int stackCount = 0;
    NodeIndex current = root;

    while (current != NULL_NODE)
    {
        const NodeType& node = nodes[current];

        if (node.isLeaf())
        {
            if (!callback(static_cast<int32_t>(current), static_cast<uint64_t>(node.userData), context))
                return;
            current = (stackCount > 0) ? stack[--stackCount] : NULL_NODE;
        }
        else
        {
            NodeIndex c0 = node.child[0];
            NodeIndex c1 = node.child[1];
            const NodeType& n0 = nodes[c0];
            const NodeType& n1 = nodes[c1];

            bool hit0 = ((n0.categoryBits & maskBits) != 0) && Traits::overlaps(n0.aabb, queryAABB);
            bool hit1 = ((n1.categoryBits & maskBits) != 0) && Traits::overlaps(n1.aabb, queryAABB);

            if (hit0 && hit1)
            {
                if (stackCount < 256)
                    stack[stackCount++] = c1;
                current = c0;
            }
            else if (hit0)
                current = c0;
            else if (hit1)
                current = c1;
            else
                current = (stackCount > 0) ? stack[--stackCount] : NULL_NODE;
        }
    }
}

template <typename T, typename Traits>
template <typename F>
void DBVH<T, Traits>::rayCast(const VecType& origin, const VecType& direction, float maxFraction, F&& callback) const
{
    if (root == NULL_NODE) return;

    VecType invDir = Traits::inverseDirection(direction);

    FixedStack<NodeIndex, 256> stack;
    stack.push(root);

    while (!stack.empty())
    {
        NodeIndex idx = stack.pop();
        const NodeType& node = nodes[idx];

        if (!Traits::rayIntersects(node.aabb, origin, invDir, maxFraction))
            continue;

        if (node.isLeaf())
        {
            float newMaxFraction = callback(static_cast<size_t>(idx), node.userData);
            if (newMaxFraction == 0.0f)
                return;
            if (newMaxFraction < maxFraction)
                maxFraction = newMaxFraction;
        }
        else
        {
            stack.push(node.child[0]);
            stack.push(node.child[1]);
        }
    }
}

template <typename T, typename Traits>
std::vector<LeafPair> DBVH<T, Traits>::queryPairs() const
{
    std::vector<LeafPair> pairs;
    if (root == NULL_NODE) return pairs;

    pairs.reserve(256);

    struct StackEntry { NodeIndex a, b; };
    FixedStack<StackEntry, 256> stack;
    stack.push({root, root});

    while (!stack.empty())
    {
        StackEntry e = stack.pop();

        NodeIndex A = e.a, B = e.b;
        const NodeType& nodeA = nodes[A];
        const NodeType& nodeB = nodes[B];

        if (!Traits::overlaps(nodeA.aabb, nodeB.aabb))
            continue;

        if (A == B)
        {
            if (!nodeA.isLeaf())
            {
                NodeIndex c0 = nodeA.child[0];
                NodeIndex c1 = nodeA.child[1];
                stack.push({c0, c0});
                stack.push({c1, c1});
                stack.push({c0, c1});
            }
            continue;
        }

        if (nodeA.isLeaf() && nodeB.isLeaf())
        {
            if (A <= B)
                pairs.emplace_back(static_cast<size_t>(A), static_cast<size_t>(B));
            continue;
        }

        if (nodeB.isLeaf() || (!nodeA.isLeaf() && Traits::surfaceArea(nodeA.aabb) >= Traits::surfaceArea(nodeB.aabb)))
        {
            stack.push({nodeA.child[0], B});
            stack.push({nodeA.child[1], B});
        }
        else
        {
            stack.push({A, nodeB.child[0]});
            stack.push({A, nodeB.child[1]});
        }
    }

    return pairs;
}

template <typename T, typename Traits>
template <typename F>
void DBVH<T, Traits>::queryPairs(F&& callback) const
{
    if (root == NULL_NODE) return;

    struct StackEntry { NodeIndex a, b; };
    FixedStack<StackEntry, 256> stack;
    stack.push({root, root});

    while (!stack.empty())
    {
        StackEntry e = stack.pop();

        NodeIndex A = e.a, B = e.b;
        const NodeType& nodeA = nodes[A];
        const NodeType& nodeB = nodes[B];

        if (!Traits::overlaps(nodeA.aabb, nodeB.aabb))
            continue;

        if (A == B)
        {
            if (!nodeA.isLeaf())
            {
                NodeIndex c0 = nodeA.child[0];
                NodeIndex c1 = nodeA.child[1];
                stack.push({c0, c0});
                stack.push({c1, c1});
                stack.push({c0, c1});
            }
            continue;
        }

        if (nodeA.isLeaf() && nodeB.isLeaf())
        {
            if (A <= B)
                callback(static_cast<size_t>(A), static_cast<size_t>(B));
            continue;
        }

        if (nodeB.isLeaf() || (!nodeA.isLeaf() && Traits::surfaceArea(nodeA.aabb) >= Traits::surfaceArea(nodeB.aabb)))
        {
            stack.push({nodeA.child[0], B});
            stack.push({nodeA.child[1], B});
        }
        else
        {
            stack.push({A, nodeB.child[0]});
            stack.push({A, nodeB.child[1]});
        }
    }
}

// ============================================================================
// Manutenção da árvore
// ============================================================================

template <typename T, typename Traits>
void DBVH<T, Traits>::refitAndRotateAncestors(NodeIndex startNode)
{
    NodeIndex idx = startNode;
    while (idx != NULL_NODE)
    {
        NodeType& node = nodes[idx];
        if (!node.isLeaf())
        {
            const auto& left = nodes[node.child[0]];
            const auto& right = nodes[node.child[1]];

            float oldArea = Traits::surfaceArea(node.aabb);
            node.aabb = Traits::unite(left.aabb, right.aabb);
            float newArea = Traits::surfaceArea(node.aabb);
            totalTreeArea += (newArea - oldArea);

            node.categoryBits = left.categoryBits | right.categoryBits;
            node.leafCount = left.leafCount + right.leafCount;
            node.subtreeArea = newArea + left.subtreeArea + right.subtreeArea;
            node.setEnlarged();

            if (config.enableRotations)
                tryRotate(idx);
        }
        idx = node.parent;
    }
}

template <typename T, typename Traits>
void DBVH<T, Traits>::tryRotate(NodeIndex idx)
{
    NodeType& A = nodes[idx];
    if (A.isLeaf()) return;

    NodeIndex B = A.child[0];
    NodeIndex C = A.child[1];

    float currentCost = Traits::surfaceArea(nodes[B].aabb) + Traits::surfaceArea(nodes[C].aabb);
    float bestCost = currentCost;

    struct RotationCandidate { NodeIndex X, Y; int gIdx; };
    RotationCandidate candidates[4] = {
        {B, C, 0}, {B, C, 1},
        {C, B, 0}, {C, B, 1}
    };

    int bestRotation = -1;

    for (int r = 0; r < 4; ++r)
    {
        auto [X, Y, gIdx] = candidates[r];
        if (nodes[Y].isLeaf()) continue;

        NodeIndex G = nodes[Y].child[gIdx];
        NodeIndex O = nodes[Y].child[1 - gIdx];

        float hypotheticalYArea = Traits::surfaceArea(Traits::unite(nodes[X].aabb, nodes[O].aabb));
        float newCost = Traits::surfaceArea(nodes[G].aabb) + hypotheticalYArea;

        if (newCost < bestCost)
        {
            bestCost = newCost;
            bestRotation = r;
        }
    }

    if (bestRotation < 0) return;

    auto [X, Y, gIdx] = candidates[bestRotation];
    NodeIndex G = nodes[Y].child[gIdx];
    NodeIndex O = nodes[Y].child[1 - gIdx];

    float oldAreaA = Traits::surfaceArea(A.aabb);
    float oldAreaY = Traits::surfaceArea(nodes[Y].aabb);

    if (A.child[0] == X)
        A.child[0] = G;
    else
        A.child[1] = G;
    nodes[G].parent = idx;

    nodes[Y].child[gIdx] = X;
    nodes[X].parent = Y;

    nodes[Y].aabb = Traits::unite(nodes[X].aabb, nodes[O].aabb);
    A.aabb = Traits::unite(nodes[A.child[0]].aabb, nodes[A.child[1]].aabb);

    float newAreaA = Traits::surfaceArea(A.aabb);
    float newAreaY = Traits::surfaceArea(nodes[Y].aabb);
    totalTreeArea += (newAreaA - oldAreaA) + (newAreaY - oldAreaY);

    nodes[Y].categoryBits = nodes[X].categoryBits | nodes[O].categoryBits;
    nodes[Y].leafCount = nodes[X].leafCount + nodes[O].leafCount;
    nodes[Y].subtreeArea = newAreaY + nodes[X].subtreeArea + nodes[O].subtreeArea;

    A.categoryBits = nodes[A.child[0]].categoryBits | nodes[A.child[1]].categoryBits;
    A.leafCount = nodes[A.child[0]].leafCount + nodes[A.child[1]].leafCount;
    A.subtreeArea = newAreaA + nodes[A.child[0]].subtreeArea + nodes[A.child[1]].subtreeArea;
}

template <typename T, typename Traits>
NodeIndex DBVH<T, Traits>::findBestSibling(const AABBType& leafAABB) const
{
    if (root == NULL_NODE) return NULL_NODE;

    VecType centerD = Traits::centroid(leafAABB);
    float areaD = Traits::surfaceArea(leafAABB);

    NodeIndex rootIndex = root;
    const NodeType& rootNode = nodes[rootIndex];
    float areaBase = Traits::surfaceArea(rootNode.aabb);
    float directCost = Traits::surfaceArea(Traits::unite(rootNode.aabb, leafAABB));
    float inheritedCost = 0.0f;

    NodeIndex bestSibling = rootIndex;
    float bestCost = directCost;

    NodeIndex index = rootIndex;
    while (!nodes[index].isLeaf())
    {
        NodeIndex child1 = nodes[index].child[0];
        NodeIndex child2 = nodes[index].child[1];

        float cost = directCost + inheritedCost;
        if (cost < bestCost)
        {
            bestSibling = index;
            bestCost = cost;
        }

        inheritedCost += directCost - areaBase;

        bool leaf1 = nodes[child1].isLeaf();
        bool leaf2 = nodes[child2].isLeaf();

        float lowerCost1 = std::numeric_limits<float>::max();
        const auto& box1 = nodes[child1].aabb;
        float directCost1 = Traits::surfaceArea(Traits::unite(box1, leafAABB));
        float area1 = 0.0f;
        if (leaf1)
        {
            float cost1 = directCost1 + inheritedCost;
            if (cost1 < bestCost)
            {
                bestSibling = child1;
                bestCost = cost1;
            }
        }
        else
        {
            area1 = Traits::surfaceArea(box1);
            lowerCost1 = inheritedCost + directCost1 + std::min(areaD - area1, 0.0f);
        }

        float lowerCost2 = std::numeric_limits<float>::max();
        const auto& box2 = nodes[child2].aabb;
        float directCost2 = Traits::surfaceArea(Traits::unite(box2, leafAABB));
        float area2 = 0.0f;
        if (leaf2)
        {
            float cost2 = directCost2 + inheritedCost;
            if (cost2 < bestCost)
            {
                bestSibling = child2;
                bestCost = cost2;
            }
        }
        else
        {
            area2 = Traits::surfaceArea(box2);
            lowerCost2 = inheritedCost + directCost2 + std::min(areaD - area2, 0.0f);
        }

        if (leaf1 && leaf2)
            break;

        if (bestCost <= lowerCost1 && bestCost <= lowerCost2)
            break;

        if (lowerCost1 == lowerCost2 && !leaf1)
        {
            VecType d1 = Traits::centroid(box1) - centerD;
            VecType d2 = Traits::centroid(box2) - centerD;
            lowerCost1 = (d1.x * d1.x + d1.y * d1.y + d1.z * d1.z);
            lowerCost2 = (d2.x * d2.x + d2.y * d2.y + d2.z * d2.z);
        }

        if (lowerCost1 < lowerCost2 && !leaf1)
        {
            index = child1;
            areaBase = area1;
            directCost = directCost1;
        }
        else
        {
            index = child2;
            areaBase = area2;
            directCost = directCost2;
        }
    }

    return bestSibling;
}

template <typename T, typename Traits>
template <typename F>
void DBVH<T, Traits>::refitAll(F&& computeAABB)
{
    if (root == NULL_NODE) return;

    struct StackEntry
    {
        NodeIndex node;
        bool expanded;
    };
    FixedStack<StackEntry, 64> stack;
    stack.push({root, false});

    while (!stack.empty())
    {
        auto& top = stack.peek();
        NodeType& node = nodes[top.node];

        if (node.isLeaf())
        {
            node.aabb = computeAABB(node.userData);
            node.setEnlarged();
            stack.pop();
            continue;
        }

        if (!top.expanded)
        {
            top.expanded = true;
            stack.push({node.child[0], false});
            stack.push({node.child[1], false});
        }
        else
        {
            node.aabb = Traits::unite(nodes[node.child[0]].aabb, nodes[node.child[1]].aabb);
            node.setEnlarged();
            stack.pop();
        }
    }
}

template <typename T, typename Traits>
void DBVH<T, Traits>::clearAllEnlarged()
{
    for (auto& node : nodes)
        node.clearEnlarged();
}

// ============================================================================
// Rebuild — Reconstrução SAH top-down
// ============================================================================

template <typename T, typename Traits>
void DBVH<T, Traits>::collectLeaves(NodeIndex node, std::vector<NodeIndex>& out) const
{
    if (node == NULL_NODE) return;

    FixedStack<NodeIndex, 64> stack;
    stack.push(node);

    while (!stack.empty())
    {
        NodeIndex idx = stack.pop();
        const NodeType& n = nodes[idx];

        if (n.isLeaf())
            out.push_back(idx);
        else
        {
            if (n.child[0] != NULL_NODE) stack.push(n.child[0]);
            if (n.child[1] != NULL_NODE) stack.push(n.child[1]);
        }
    }
}

template <typename T, typename Traits>
void DBVH<T, Traits>::freeInternalNodes(NodeIndex node)
{
    if (node == NULL_NODE) return;

    FixedStack<NodeIndex, 64> stack;
    stack.push(node);

    while (!stack.empty())
    {
        NodeIndex idx = stack.pop();
        const NodeType& n = nodes[idx];

        if (!n.isLeaf())
        {
            if (n.child[0] != NULL_NODE) stack.push(n.child[0]);
            if (n.child[1] != NULL_NODE) stack.push(n.child[1]);
            freeNode(static_cast<size_t>(idx));
        }
    }
}

template <typename T, typename Traits>
NodeIndex DBVH<T, Traits>::buildSubtree(std::vector<NodeIndex>& leaves, size_t start, size_t end)
{
    size_t count = end - start;

    if (count == 1)
    {
        NodeIndex leaf = static_cast<NodeIndex>(leaves[start]);
        nodes[leaf].parent = NULL_NODE;
        nodes[leaf].leafCount = 1;
        nodes[leaf].subtreeArea = Traits::surfaceArea(nodes[leaf].aabb);
        nodes[leaf].constructionArea = nodes[leaf].subtreeArea;
        return leaf;
    }

    if (count == 2)
    {
        NodeIndex internal = static_cast<NodeIndex>(allocateNode());
        NodeIndex left  = static_cast<NodeIndex>(leaves[start]);
        NodeIndex right = static_cast<NodeIndex>(leaves[start + 1]);

        nodes[left].leafCount = 1;
        nodes[left].subtreeArea = Traits::surfaceArea(nodes[left].aabb);
        nodes[left].constructionArea = nodes[left].subtreeArea;

        nodes[right].leafCount = 1;
        nodes[right].subtreeArea = Traits::surfaceArea(nodes[right].aabb);
        nodes[right].constructionArea = nodes[right].subtreeArea;

        nodes[internal].child = {left, right};
        nodes[internal].aabb = Traits::unite(nodes[left].aabb, nodes[right].aabb);
        nodes[internal].constructionArea = Traits::surfaceArea(nodes[internal].aabb);
        nodes[internal].categoryBits = nodes[left].categoryBits | nodes[right].categoryBits;
        nodes[internal].leafCount = 2;
        nodes[internal].subtreeArea = nodes[internal].constructionArea + nodes[left].subtreeArea + nodes[right].subtreeArea;
        nodes[left].parent = internal;
        nodes[right].parent = internal;

        return internal;
    }

    // Calcula os limites dos centróides
    VecType c0 = Traits::centroid(nodes[leaves[start]].aabb);
    AABBType centroidBounds(c0, c0);

    for (size_t i = start + 1; i < end; ++i)
    {
        VecType c = Traits::centroid(nodes[leaves[i]].aabb);
        centroidBounds = Traits::unite(centroidBounds, AABBType(c, c));
    }

    // Escolhe o eixo de maior extensão dos centróides
    float ex = Traits::getMax(centroidBounds, 0) - Traits::getMin(centroidBounds, 0);
    float ey = Traits::getMax(centroidBounds, 1) - Traits::getMin(centroidBounds, 1);
    float ez = Traits::getMax(centroidBounds, 2) - Traits::getMin(centroidBounds, 2);

    int axis = 0;
    if (ey > ex) axis = 1;
    if (ez > ((axis == 0) ? ex : ey)) axis = 2;

    float axisMin = Traits::getMin(centroidBounds, axis);
    float axisMax = Traits::getMax(centroidBounds, axis);

    // Se todos os centróides coincidem, particiona no meio
    if (axisMax - axisMin < 1e-7f)
    {
        size_t mid = start + count / 2;
        NodeIndex internal = static_cast<NodeIndex>(allocateNode());
        NodeIndex left  = buildSubtree(leaves, start, mid);
        NodeIndex right = buildSubtree(leaves, mid, end);

        nodes[internal].child = {left, right};
        nodes[internal].aabb = Traits::unite(nodes[left].aabb, nodes[right].aabb);
        nodes[internal].constructionArea = Traits::surfaceArea(nodes[internal].aabb);
        nodes[left].parent = internal;
        nodes[right].parent = internal;

        return internal;
    }

    constexpr int NUM_BINS = 12;
    struct Bin { AABBType bounds; size_t count{0}; };
    std::array<Bin, NUM_BINS> bins{};

    float scale = static_cast<float>(NUM_BINS) / (axisMax - axisMin);

    // Distribui folhas nos bins pelo centróide
    for (size_t i = start; i < end; ++i)
    {
        VecType c = Traits::centroid(nodes[leaves[i]].aabb);
        float cv = Traits::getAxis(c, axis);
        int b = std::min(static_cast<int>((cv - axisMin) * scale), NUM_BINS - 1);

        if (bins[b].count == 0)
            bins[b].bounds = nodes[leaves[i]].aabb;
        else
            bins[b].bounds = Traits::unite(bins[b].bounds, nodes[leaves[i]].aabb);
        bins[b].count++;
    }

    // Avalia o custo SAH para cada plano de partição
    float bestCost = std::numeric_limits<float>::max();
    int   bestSplit = -1;

    for (int s = 0; s < NUM_BINS - 1; ++s)
    {
        AABBType leftBounds{}, rightBounds{};
        size_t leftCount = 0, rightCount = 0;
        bool leftInit = false, rightInit = false;

        for (int j = 0; j <= s; ++j)
            if (bins[j].count > 0)
            {
                leftBounds = leftInit ? Traits::unite(leftBounds, bins[j].bounds) : bins[j].bounds;
                leftInit = true;
                leftCount += bins[j].count;
            }
            
        for (int j = s + 1; j < NUM_BINS; ++j)
            if (bins[j].count > 0)
            {
                rightBounds = rightInit ? Traits::unite(rightBounds, bins[j].bounds) : bins[j].bounds;
                rightInit = true;
                rightCount += bins[j].count;
            }

        if (leftCount == 0 || rightCount == 0) continue;

        float cost = static_cast<float>(leftCount) * Traits::surfaceArea(leftBounds)
                   + static_cast<float>(rightCount) * Traits::surfaceArea(rightBounds);

        if (cost < bestCost)
        {
            bestCost = cost;
            bestSplit = s;
        }
    }

    // Particiona as folhas de acordo com o melhor split
    size_t mid;
    if (bestSplit < 0)
        mid = start + count / 2;
    else
    {
        auto it = std::partition(
            leaves.begin() + static_cast<std::ptrdiff_t>(start),
            leaves.begin() + static_cast<std::ptrdiff_t>(end),
            [&](NodeIndex leaf)
            {
                VecType c = Traits::centroid(nodes[leaf].aabb);
                float cv = Traits::getAxis(c, axis);
                int b = std::min(static_cast<int>((cv - axisMin) * scale), NUM_BINS - 1);
                return b <= bestSplit;
            }
        );
        mid = static_cast<size_t>(it - leaves.begin());

        if (mid == start) mid = start + 1;
        if (mid == end)   mid = end - 1;
    }

    NodeIndex internal = static_cast<NodeIndex>(allocateNode());
    NodeIndex left  = buildSubtree(leaves, start, mid);
    NodeIndex right = buildSubtree(leaves, mid, end);

    nodes[internal].child = {left, right};
    nodes[internal].aabb = Traits::unite(nodes[left].aabb, nodes[right].aabb);
    nodes[internal].constructionArea = Traits::surfaceArea(nodes[internal].aabb);
    nodes[internal].categoryBits = nodes[left].categoryBits | nodes[right].categoryBits;
    nodes[internal].leafCount = nodes[left].leafCount + nodes[right].leafCount;
    nodes[internal].subtreeArea = nodes[internal].constructionArea + nodes[left].subtreeArea + nodes[right].subtreeArea;
    nodes[left].parent = internal;
    nodes[right].parent = internal;

    return internal;
}

template <typename T, typename Traits>
float DBVH<T, Traits>::computeTotalSurfaceArea() const
{
    if (root == NULL_NODE) return 0.0f;
    float sum = 0.0f;
    FixedStack<NodeIndex, 128> stack;
    stack.push(root);
    while (!stack.empty())
    {
        NodeIndex idx = stack.pop();
        if (idx == NULL_NODE) continue;
        const auto& node = nodes[idx];
        sum += Traits::surfaceArea(node.aabb);
        if (!node.isLeaf())
        {
            if (node.child[0] != NULL_NODE) stack.push(node.child[0]);
            if (node.child[1] != NULL_NODE) stack.push(node.child[1]);
        }
    }
    return sum;
}

template <typename T, typename Traits>
float DBVH<T, Traits>::getDegradationAlpha() const
{
    if (root == NULL_NODE || leafCount <= 1) return 0.0f;
    float rootArea = Traits::surfaceArea(nodes[root].aabb);
    if (rootArea <= 1e-7f) return 0.0f;
    float denom = rootArea * static_cast<float>(leafCount) * std::log2(static_cast<float>(leafCount));
    if (denom <= 1e-7f) return 0.0f;
    return totalTreeArea / denom;
}

template <typename T, typename Traits>
void DBVH<T, Traits>::rebuild(NodeIndex subtreeRoot, bool updateArea)
{
    NodeIndex target = (subtreeRoot == NULL_NODE) ? root : subtreeRoot;
    if (target == NULL_NODE) return;

    std::vector<NodeIndex> leaves;
    leaves.reserve(64);
    collectLeaves(target, leaves);

    if (leaves.empty()) return;

    NodeIndex parentOfSubtree = nodes[target].parent;
    int childIdx = (parentOfSubtree != NULL_NODE)
        ? (nodes[parentOfSubtree].child[0] == target) ? 0 : 1
        : NULL_NODE;

    freeInternalNodes(target);

    NodeIndex newRoot = buildSubtree(leaves, 0, leaves.size());

    if (parentOfSubtree == NULL_NODE)
    {
        root = newRoot;
        nodes[newRoot].parent = NULL_NODE;
    }
    else
    {
        nodes[parentOfSubtree].child[childIdx] = newRoot;
        nodes[newRoot].parent = parentOfSubtree;

        refitAndRotateAncestors(parentOfSubtree);
    }

    if (updateArea)
        totalTreeArea = computeTotalSurfaceArea();
}

template <typename T, typename Traits>
int DBVH<T, Traits>::computeSubtreeHeight(NodeIndex nodeIdx) const
{
    if (nodeIdx == NULL_NODE || nodes[nodeIdx].isLeaf()) return 0;
    int hL = (nodes[nodeIdx].child[0] != NULL_NODE) ? computeSubtreeHeight(nodes[nodeIdx].child[0]) : 0;
    int hR = (nodes[nodeIdx].child[1] != NULL_NODE) ? computeSubtreeHeight(nodes[nodeIdx].child[1]) : 0;
    return 1 + std::max(hL, hR);
}

template <typename T, typename Traits>
int DBVH<T, Traits>::getHeight() const
{
    if (root == NULL_NODE) return 0;
    return computeSubtreeHeight(root);
}

template <typename T, typename Traits>
TreeQualityMetrics DBVH<T, Traits>::computeQualityMetrics(float traversalCost, float isectCost) const
{
    TreeQualityMetrics metrics{};
    if (root == NULL_NODE) return metrics;

    metrics.rootArea = Traits::surfaceArea(nodes[root].aabb);
    metrics.treeHeight = getHeight();

    float sumInternalSA = 0.0f;
    float sumLeafSA = 0.0f;
    float sumAllSA = 0.0f;
    int leaves = 0;
    int totalNodes = 0;

    FixedStack<NodeIndex, 128> stack;
    stack.push(root);

    while (stack.top > 0)
    {
        NodeIndex idx = stack.pop();
        if (idx == NULL_NODE) continue;

        const auto& node = nodes[idx];
        float sa = Traits::surfaceArea(node.aabb);
        sumAllSA += sa;
        totalNodes++;

        if (node.isLeaf())
        {
            sumLeafSA += sa;
            leaves++;
        }
        else
        {
            sumInternalSA += sa;
            if (node.child[0] != NULL_NODE) stack.push(node.child[0]);
            if (node.child[1] != NULL_NODE) stack.push(node.child[1]);
        }
    }

    metrics.sahCostStandard = traversalCost * sumInternalSA + isectCost * sumLeafSA;
    metrics.sahCostNormalized = (metrics.rootArea > 0.0f) ? (sumAllSA / metrics.rootArea) : 0.0f;
    metrics.leafCount = leaves;
    metrics.nodeCount = totalNodes;

    return metrics;
}

template <typename T, typename Traits>
TreeQualityMetrics DBVH<T, Traits>::computeIdealFromAABBs(const std::vector<AABBType>& leafAABBs, float traversalCost, float isectCost)
{
    if (leafAABBs.empty()) return TreeQualityMetrics{};

    DBVH<T, Traits> idealTree;
    std::vector<NodeIndex> leaves;
    leaves.reserve(leafAABBs.size());

    for (size_t i = 0; i < leafAABBs.size(); ++i)
    {
        NodeIndex leaf = static_cast<NodeIndex>(idealTree.allocateNode());
        idealTree.nodes[leaf].aabb = leafAABBs[i];
        idealTree.nodes[leaf].userData = static_cast<T>(i);
        idealTree.nodes[leaf].constructionArea = Traits::surfaceArea(leafAABBs[i]);
        leaves.push_back(leaf);
    }

    idealTree.root = idealTree.buildSubtree(leaves, 0, leaves.size());
    if (idealTree.root != NULL_NODE)
        idealTree.nodes[idealTree.root].parent = NULL_NODE;

    return idealTree.computeQualityMetrics(traversalCost, isectCost);
}

template <typename T, typename Traits>
TreeQualityMetrics DBVH<T, Traits>::computeIdealQualityMetrics(float traversalCost, float isectCost) const
{
    if (root == NULL_NODE) return TreeQualityMetrics{};

    std::vector<NodeIndex> leafIndices;
    leafIndices.reserve(64);
    collectLeaves(root, leafIndices);

    if (leafIndices.empty()) return TreeQualityMetrics{};

    std::vector<AABBType> leafAABBs;
    leafAABBs.reserve(leafIndices.size());
    for (NodeIndex leafIdx : leafIndices)
        leafAABBs.push_back(nodes[leafIdx].aabb);

    return computeIdealFromAABBs(leafAABBs, traversalCost, isectCost);
}

template <typename T, typename Traits>
int DBVH<T, Traits>::rebuildDegraded(float threshold, DegradationMetric metric, int maxRebuilds, int maxSubtreeLeaves)
{
    if (root == NULL_NODE || maxRebuilds <= 0) return 0;

    struct CandidateInfo {
        NodeIndex idx;
        float score;
        uint32_t leafCount;
    };
    std::vector<CandidateInfo> candidates;

    if (metric == DegradationMetric::AreaRatio)
    {
        NodeIndex stack[256];
        int stackCount = 0;
        stack[stackCount++] = root;

        while (stackCount > 0)
        {
            NodeIndex idx = stack[--stackCount];
            const NodeType& node = nodes[idx];

            if (node.isLeaf()) continue;

            float currentArea = Traits::surfaceArea(node.aabb);
            float ratio = (node.constructionArea > 0.0f)
                        ? currentArea / node.constructionArea
                        : 1.0f;

            if (ratio > threshold)
            {
                if (maxSubtreeLeaves <= 0 || static_cast<int>(node.leafCount) <= maxSubtreeLeaves || (node.child[0] == NULL_NODE && node.child[1] == NULL_NODE))
                    candidates.push_back({idx, ratio, node.leafCount});
                else
                {
                    // Branch is too large; descend into children to find smaller degraded subtrees
                    if (node.child[0] != NULL_NODE && stackCount < 254) stack[stackCount++] = node.child[0];
                    if (node.child[1] != NULL_NODE && stackCount < 254) stack[stackCount++] = node.child[1];
                }
            }
            else
            {
                if (node.child[0] != NULL_NODE && stackCount < 254) stack[stackCount++] = node.child[0];
                if (node.child[1] != NULL_NODE && stackCount < 254) stack[stackCount++] = node.child[1];
            }
        }

        std::sort(candidates.begin(), candidates.end(), [](const CandidateInfo& a, const CandidateInfo& b) {
            return a.score > b.score;
        });
    }
    else if (metric == DegradationMetric::SubtreeSAH)
    {
        NodeIndex stack[256];
        int stackCount = 0;
        stack[stackCount++] = root;

        while (stackCount > 0)
        {
            NodeIndex idx = stack[--stackCount];
            const NodeType& node = nodes[idx];

            if (node.isLeaf() || node.leafCount < 2) continue;

            float sa_k = Traits::surfaceArea(node.aabb);
            float denom = sa_k * static_cast<float>(node.leafCount) * std::log2(static_cast<float>(node.leafCount));
            float alpha_k = (denom > 1e-7f) ? (node.subtreeArea / denom) : 0.0f;

            if (alpha_k > threshold)
            {
                if (maxSubtreeLeaves <= 0 || static_cast<int>(node.leafCount) <= maxSubtreeLeaves || (node.child[0] == NULL_NODE && node.child[1] == NULL_NODE))
                    candidates.push_back({idx, alpha_k, node.leafCount});
                else
                {
                    if (node.child[0] != NULL_NODE && stackCount < 254) stack[stackCount++] = node.child[0];
                    if (node.child[1] != NULL_NODE && stackCount < 254) stack[stackCount++] = node.child[1];
                }
            }
            else
            {
                if (node.child[0] != NULL_NODE && stackCount < 254) stack[stackCount++] = node.child[0];
                if (node.child[1] != NULL_NODE && stackCount < 254) stack[stackCount++] = node.child[1];
            }
        }

        if (candidates.empty() && getDegradationAlpha() > threshold)
        {
            if (maxSubtreeLeaves <= 0 || static_cast<int>(nodes[root].leafCount) <= maxSubtreeLeaves)
                candidates.push_back({root, getDegradationAlpha(), nodes[root].leafCount});
        }
        else
            std::sort(candidates.begin(), candidates.end(), [](const CandidateInfo& a, const CandidateInfo& b) {
                return a.leafCount > b.leafCount;
            });
    }

    int rebuildCount = 0;
    for (const auto& cand : candidates)
    {
        if (rebuildCount >= maxRebuilds) break;
        NodeIndex candidate = cand.idx;
        if (candidate < static_cast<NodeIndex>(nodes.size()) && !nodes[candidate].isLeaf() && nodes[candidate].child[0] != NULL_NODE)
        {
            rebuild(candidate, false);
            rebuildCount++;
        }
    }

    if (rebuildCount > 0)
        totalTreeArea = computeTotalSurfaceArea();

    return rebuildCount;
}

} // namespace dbvh