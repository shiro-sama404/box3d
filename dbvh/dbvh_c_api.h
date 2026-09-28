#pragma once

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C"
{
#endif

typedef struct dbvh_tree_t dbvh_tree_t;

dbvh_tree_t* dbvh_create(size_t initialCapacity);
void dbvh_destroy(dbvh_tree_t* tree);

// aabb array order: {minX, minY, minZ, maxX, maxY, maxZ}
int32_t dbvh_insert(dbvh_tree_t* tree, const float aabb[6], int32_t userData);
int32_t dbvh_insert_with_category(dbvh_tree_t* tree, const float aabb[6], int32_t userData, uint64_t categoryBits);
void dbvh_set_category_bits(dbvh_tree_t* tree, int32_t leafIndex, uint64_t categoryBits);

void dbvh_remove(dbvh_tree_t* tree, int32_t leafIndex);

// velocity order: {vx, vy, vz}
// Returns the same leafIndex (stable after detach/reattach refactor)
int32_t dbvh_move(dbvh_tree_t* tree, int32_t leafIndex, const float aabb[6], const float velocity[3], float epsilon);

// Enlarge proxy AABB upwards
void dbvh_enlarge_proxy(dbvh_tree_t* tree, int32_t proxyId, const float aabb[6]);

int32_t dbvh_get_user_data(dbvh_tree_t* tree, int32_t leafIndex);
void dbvh_get_aabb(dbvh_tree_t* tree, int32_t leafIndex, float aabb[6]);
void dbvh_get_proxy_info(const dbvh_tree_t* tree, int32_t proxyId, float outAABB[6], int32_t* outUserData);

typedef void (*dbvh_query_callback_t)(int32_t leafIndexA, int32_t leafIndexB, void* context);
void dbvh_query_pairs(dbvh_tree_t* tree, dbvh_query_callback_t callback, void* context);

typedef bool (*dbvh_query_aabb_callback_t)(int32_t leafIndex, int32_t userData, void* context);
void dbvh_query_aabb(dbvh_tree_t* tree, const float aabb[6], dbvh_query_aabb_callback_t callback, void* context);
void dbvh_query_aabb_mask(dbvh_tree_t* tree, const float aabb[6], uint64_t maskBits, dbvh_query_aabb_callback_t callback, void* context);

typedef bool (*dbvh_fast_query_callback_t)(int32_t proxyId, uint64_t userData, void* context);
void dbvh_query_aabb_fast(const dbvh_tree_t* tree, const float aabb[6], uint64_t maskBits, dbvh_fast_query_callback_t callback, void* context);

typedef float (*dbvh_ray_cast_callback_t)(int32_t leafIndex, int32_t userData, void* context);
void dbvh_ray_cast(dbvh_tree_t* tree, const float translation[3], const float p1[3], float maxFraction, dbvh_ray_cast_callback_t callback, void* context);

typedef enum dbvh_degradation_metric_t {
    DBVH_METRIC_AREA_RATIO = 0,
    DBVH_METRIC_SUBTREE_SAH = 1,
} dbvh_degradation_metric_t;

typedef struct dbvh_config_t {
    bool enableRebuild;
    bool enableFattening;
    bool enablePredictive;
    bool enableRotations;
    bool enableAdaptiveRebuild;
    dbvh_degradation_metric_t degradationMetric;
    float rebuildThreshold;
    float areaRatioThreshold;
    float subtreeSAHThreshold;
    int32_t rebuildInterval;
    int32_t maxRebuildsPerFrame;
    int32_t maxSubtreeLeaves;
} dbvh_config_t;

void dbvh_set_config(dbvh_tree_t* tree, const dbvh_config_t* config);
void dbvh_get_config(const dbvh_tree_t* tree, dbvh_config_t* config);

void dbvh_rebuild(dbvh_tree_t* tree);
void dbvh_rebuild_degraded(dbvh_tree_t* tree, float threshold, dbvh_degradation_metric_t metric);
int32_t dbvh_rebuild_degraded_ex(dbvh_tree_t* tree, float threshold, dbvh_degradation_metric_t metric, int32_t maxRebuilds);
int32_t dbvh_rebuild_degraded_adaptive(dbvh_tree_t* tree, float threshold, dbvh_degradation_metric_t metric, int32_t maxRebuilds, int32_t maxSubtreeLeaves);
int32_t dbvh_get_height(const dbvh_tree_t* tree);
float dbvh_get_degradation_alpha(const dbvh_tree_t* tree);
float dbvh_get_total_tree_area(const dbvh_tree_t* tree);
void dbvh_get_root_bounds(const dbvh_tree_t* tree, float aabb[6]);

typedef struct dbvh_tree_metrics_t {
    float sahCostStandard;
    float sahCostNormalized;
    float rootArea;
    int32_t treeHeight;
    int32_t leafCount;
    int32_t nodeCount;
} dbvh_tree_metrics_t;

void dbvh_get_quality_metrics(const dbvh_tree_t* tree, dbvh_tree_metrics_t* metrics, float traversalCost, float isectCost);
void dbvh_get_ideal_quality_metrics(const dbvh_tree_t* tree, dbvh_tree_metrics_t* idealMetrics, float traversalCost, float isectCost);
void dbvh_compute_ideal_from_aabbs(const float* aabbArray, int32_t leafCount, dbvh_tree_metrics_t* idealMetrics, float traversalCost, float isectCost);

#ifdef __cplusplus
}
#endif