#pragma once

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C"
{
#endif

// ============================================================================
// Tipos e Estruturas da SDBVH (Stable Dynamic Bounding Volume Hierarchy)
// ============================================================================

typedef struct sdbvh_tree_t sdbvh_tree_t;

sdbvh_tree_t* sdbvh_create(size_t initialCapacity);
void sdbvh_destroy(sdbvh_tree_t* tree);

// Inserção com máscara de categoria (aabb array: {minX, minY, minZ, maxX, maxY, maxZ})
int32_t sdbvh_insert_with_category(sdbvh_tree_t* tree, const float aabb[6], int32_t userData, uint64_t categoryBits);
void sdbvh_remove(sdbvh_tree_t* tree, int32_t leafIndex);

// Movimentação com expansão preditiva de velocidade
int32_t sdbvh_move(sdbvh_tree_t* tree, int32_t leafIndex, const float aabb[6], const float velocity[3], float epsilon);

// Alargamento/refit de proxy
void sdbvh_enlarge_proxy(sdbvh_tree_t* tree, int32_t proxyId, const float aabb[6]);

int32_t sdbvh_get_user_data(sdbvh_tree_t* tree, int32_t leafIndex);
void sdbvh_get_aabb(sdbvh_tree_t* tree, int32_t leafIndex, float aabb[6]);

// Callback de auto-colisão
typedef void (*sdbvh_pairs_callback_t)(int32_t shapeIdA, int32_t shapeIdB, void* context);
void sdbvh_query_pairs(sdbvh_tree_t* tree, sdbvh_pairs_callback_t callback, void* context);

// Estruturas e callbacks para emissão em lote e paralelismo por tarefas
typedef struct sdbvh_pair_t {
    int32_t shapeIdA;
    int32_t shapeIdB;
} sdbvh_pair_t;

typedef struct sdbvh_seed_t {
    int32_t a;
    int32_t b;
} sdbvh_seed_t;

typedef void (*sdbvh_pairs_batch_callback_t)(const sdbvh_pair_t* pairs, int count, void* context);
void sdbvh_query_pairs_batched(sdbvh_tree_t* tree, sdbvh_pairs_batch_callback_t callback, void* context);

// Geração e execução de sementes para tarefas em paralelo (b3ParallelFor)
int32_t sdbvh_gather_seeds(sdbvh_tree_t* tree, sdbvh_seed_t* seeds, int32_t maxSeeds);
void sdbvh_query_seed_batched(sdbvh_tree_t* tree, const sdbvh_seed_t* seed, sdbvh_pairs_batch_callback_t callback, void* context);

// Callback de consulta de AABB
typedef bool (*sdbvh_query_aabb_callback_t)(int32_t leafIndex, int32_t userData, void* context);
void sdbvh_query_aabb(sdbvh_tree_t* tree, const float aabb[6], sdbvh_query_aabb_callback_t callback, void* context);
void sdbvh_query_aabb_mask(sdbvh_tree_t* tree, const float aabb[6], uint64_t maskBits, sdbvh_query_aabb_callback_t callback, void* context);
void sdbvh_query_aabb_mask_moved(sdbvh_tree_t* tree, const float aabb[6], uint64_t maskBits, sdbvh_query_aabb_callback_t callback, void* context);

// Manutenção de flags de movimento
void sdbvh_clear_moved(sdbvh_tree_t* tree);
void sdbvh_mark_moved(sdbvh_tree_t* tree, int32_t proxyId);

// Callback Raycast
typedef float (*sdbvh_ray_cast_callback_t)(int32_t leafIndex, int32_t userData, void* context);
void sdbvh_ray_cast(sdbvh_tree_t* tree, const float translation[3], const float p1[3], float maxFraction, sdbvh_ray_cast_callback_t callback, void* context);

// Algoritmos de particionamento para reconstrução
typedef enum sdbvh_partition_algorithm_t {
    SDBVH_PARTITION_BINNED_SAH = 0,
    SDBVH_PARTITION_MEDIAN_SPLIT = 1,
} sdbvh_partition_algorithm_t;

// Métricas de degradação
typedef enum sdbvh_degradation_metric_t {
    SDBVH_METRIC_AREA_RATIO = 0,
    SDBVH_METRIC_SUBTREE_SAH = 1,
} sdbvh_degradation_metric_t;

typedef struct sdbvh_config_t {
    bool enableRebuild;
    bool enableFattening;
    bool enablePredictive;
    bool enableRotations;
    bool enableAdaptiveRebuild;
    sdbvh_degradation_metric_t degradationMetric;
    float areaRatioThreshold;
    float subtreeSAHThreshold;
    int32_t rebuildInterval;
    int32_t maxRebuildsPerFrame;
    int32_t maxSubtreeLeaves;
    sdbvh_partition_algorithm_t partitionAlgorithm;
} sdbvh_config_t;

void sdbvh_set_config(sdbvh_tree_t* tree, const sdbvh_config_t* config);

// Operações de Reconstrução Adaptativa
void sdbvh_rebuild(sdbvh_tree_t* tree);
int32_t sdbvh_rebuild_degraded_adaptive(sdbvh_tree_t* tree, float threshold, sdbvh_degradation_metric_t metric, int32_t maxRebuilds, int32_t maxSubtreeLeaves);

// Diagnósticos e métricas de qualidade SAH
int32_t sdbvh_get_height(const sdbvh_tree_t* tree);
float sdbvh_get_degradation_alpha(const sdbvh_tree_t* tree);
float sdbvh_get_total_tree_area(const sdbvh_tree_t* tree);
void sdbvh_get_root_bounds(const sdbvh_tree_t* tree, float aabb[6]);

typedef struct sdbvh_tree_metrics_t {
    float sahCostStandard;
    float sahCostNormalized;
    float rootArea;
    int32_t treeHeight;
    int32_t leafCount;
    int32_t nodeCount;
} sdbvh_tree_metrics_t;

void sdbvh_get_quality_metrics(const sdbvh_tree_t* tree, sdbvh_tree_metrics_t* metrics, float traversalCost, float isectCost);
void sdbvh_get_ideal_quality_metrics(const sdbvh_tree_t* tree, sdbvh_tree_metrics_t* idealMetrics, float traversalCost, float isectCost);
void sdbvh_compute_ideal_from_aabbs(const float* aabbArray, int32_t leafCount, sdbvh_tree_metrics_t* idealMetrics, float traversalCost, float isectCost);

#ifdef __cplusplus
}
#endif