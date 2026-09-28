#include "dbvh_c_api.h"
#include "DBVH.hpp"
#include "AABB.h"
#include "Vec3.h"
#include <cstring>

extern "C"
{

dbvh_tree_t* dbvh_create(size_t initialCapacity) {
    return reinterpret_cast<dbvh_tree_t*>(new dbvh::DBVH<int32_t>(initialCapacity));
}

void dbvh_destroy(dbvh_tree_t* tree) {
    delete reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
}

int32_t dbvh_insert(dbvh_tree_t* tree, const float aabb[6], int32_t userData) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    return static_cast<int32_t>(bvh->insert(dbvh::AABB::fromArray(aabb), userData));
}

int32_t dbvh_insert_with_category(dbvh_tree_t* tree, const float aabb[6], int32_t userData, uint64_t categoryBits) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    return static_cast<int32_t>(bvh->insert(dbvh::AABB::fromArray(aabb), userData, categoryBits));
}

void dbvh_set_category_bits(dbvh_tree_t* tree, int32_t leafIndex, uint64_t categoryBits) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    bvh->setCategoryBits(static_cast<size_t>(leafIndex), categoryBits);
}

void dbvh_remove(dbvh_tree_t* tree, int32_t leafIndex) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    bvh->remove(static_cast<size_t>(leafIndex));
}

int32_t dbvh_move(dbvh_tree_t* tree, int32_t leafIndex, const float aabb[6], const float velocity[3], float epsilon) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    dbvh::Vec3 vel(velocity[0], velocity[1], velocity[2]);
    return static_cast<int32_t>(bvh->moveObject(static_cast<size_t>(leafIndex), *reinterpret_cast<const dbvh::AABB*>(aabb), vel, epsilon));
}

void dbvh_enlarge_proxy(dbvh_tree_t* tree, int32_t proxyId, const float aabb[6]) {
    if (!tree) return;
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    bvh->enlargeProxy(static_cast<size_t>(proxyId), *reinterpret_cast<const dbvh::AABB*>(aabb));
}

int32_t dbvh_get_user_data(dbvh_tree_t* tree, int32_t leafIndex) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    return bvh->getNode(static_cast<size_t>(leafIndex)).userData;
}

void dbvh_get_aabb(dbvh_tree_t* tree, int32_t leafIndex, float aabb[6]) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    bvh->getNode(static_cast<size_t>(leafIndex)).aabb.toArray(aabb);
}

void dbvh_get_proxy_info(const dbvh_tree_t* tree, int32_t proxyId, float outAABB[6], int32_t* outUserData) {
    if (!tree) return;
    const dbvh::DBVH<int32_t>* bvh = reinterpret_cast<const dbvh::DBVH<int32_t>*>(tree);
    const auto& node = bvh->getNode(static_cast<size_t>(proxyId));
    std::memcpy(outAABB, &node.aabb, sizeof(float) * 6);
    if (outUserData) *outUserData = node.userData;
}

typedef void (*dbvh_query_callback_t)(int32_t leafIndexA, int32_t leafIndexB, void* context);
void dbvh_query_pairs(dbvh_tree_t* tree, dbvh_query_callback_t callback, void* context) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    bvh->queryPairs([callback, context, bvh](size_t leafA, size_t leafB) {
        int32_t udA = bvh->getNode(leafA).userData;
        int32_t udB = bvh->getNode(leafB).userData;
        callback(udA, udB, context);
    });
}

void dbvh_query_aabb(dbvh_tree_t* tree, const float aabb[6], dbvh_query_aabb_callback_t callback, void* context) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    dbvh::AABB box = dbvh::AABB::fromArray(aabb);
    bvh->query(box, [callback, context](size_t leafIndex, int32_t userData) -> bool {
        return callback(static_cast<int32_t>(leafIndex), userData, context);
    });
}

void dbvh_query_aabb_mask(dbvh_tree_t* tree, const float aabb[6], uint64_t maskBits, dbvh_query_aabb_callback_t callback, void* context) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    dbvh::AABB box = dbvh::AABB::fromArray(aabb);
    bvh->query(box, [callback, context](size_t leafIndex, int32_t userData) -> bool {
        return callback(static_cast<int32_t>(leafIndex), userData, context);
    }, maskBits);
}

void dbvh_query_aabb_fast(const dbvh_tree_t* tree, const float aabb[6], uint64_t maskBits, dbvh_fast_query_callback_t callback, void* context) {
    if (!tree) return;
    const dbvh::DBVH<int32_t>* bvh = reinterpret_cast<const dbvh::DBVH<int32_t>*>(tree);
    bvh->queryFast(*reinterpret_cast<const dbvh::AABB*>(aabb), maskBits, callback, context);
}

void dbvh_ray_cast(dbvh_tree_t* tree, const float translation[3], const float p1[3], float maxFraction, dbvh_ray_cast_callback_t callback, void* context) {
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    dbvh::Vec3 trans = {translation[0], translation[1], translation[2]};
    dbvh::Vec3 p1_vec = {p1[0], p1[1], p1[2]};
    bvh->rayCast(trans, p1_vec, maxFraction, [callback, context](size_t leafIndex, int32_t userData) -> float {
        return callback(static_cast<int32_t>(leafIndex), userData, context);
    });
}

void dbvh_set_config(dbvh_tree_t* tree, const dbvh_config_t* config) {
    if (!tree || !config) return;
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    dbvh::DBVHConfig cfg;
    cfg.enableRebuild = config->enableRebuild;
    cfg.enableFattening = config->enableFattening;
    cfg.enablePredictive = config->enablePredictive;
    cfg.enableRotations = config->enableRotations;
    cfg.enableAdaptiveRebuild = config->enableAdaptiveRebuild;
    cfg.maxSubtreeLeaves = (config->maxSubtreeLeaves > 0) ? config->maxSubtreeLeaves : 64;
    cfg.metric = static_cast<dbvh::DegradationMetric>(config->degradationMetric);
    cfg.rebuildThreshold = config->rebuildThreshold;
    cfg.areaRatioThreshold = (config->areaRatioThreshold > 0.0f) ? config->areaRatioThreshold : config->rebuildThreshold;
    cfg.subtreeSAHThreshold = (config->subtreeSAHThreshold > 0.0f) ? config->subtreeSAHThreshold : config->rebuildThreshold;
    cfg.rebuildInterval = (config->rebuildInterval > 0) ? config->rebuildInterval : 30;
    cfg.maxRebuildsPerFrame = (config->maxRebuildsPerFrame > 0) ? config->maxRebuildsPerFrame : 2;
    bvh->setConfig(cfg);
}

void dbvh_get_config(const dbvh_tree_t* tree, dbvh_config_t* config) {
    if (!tree || !config) return;
    const dbvh::DBVH<int32_t>* bvh = reinterpret_cast<const dbvh::DBVH<int32_t>*>(tree);
    const dbvh::DBVHConfig& cfg = bvh->getConfig();
    config->enableRebuild = cfg.enableRebuild;
    config->enableFattening = cfg.enableFattening;
    config->enablePredictive = cfg.enablePredictive;
    config->enableRotations = cfg.enableRotations;
    config->enableAdaptiveRebuild = cfg.enableAdaptiveRebuild;
    config->degradationMetric = static_cast<dbvh_degradation_metric_t>(cfg.metric);
    config->rebuildThreshold = cfg.rebuildThreshold;
    config->areaRatioThreshold = cfg.areaRatioThreshold;
    config->subtreeSAHThreshold = cfg.subtreeSAHThreshold;
    config->rebuildInterval = cfg.rebuildInterval;
    config->maxRebuildsPerFrame = cfg.maxRebuildsPerFrame;
    config->maxSubtreeLeaves = cfg.maxSubtreeLeaves;
}

void dbvh_rebuild(dbvh_tree_t* tree) {
    if (!tree) return;
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    bvh->rebuild();
}

void dbvh_rebuild_degraded(dbvh_tree_t* tree, float threshold, dbvh_degradation_metric_t metric) {
    if (!tree) return;
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    bvh->rebuildDegraded(threshold, static_cast<dbvh::DegradationMetric>(metric), 2, 64);
}

int32_t dbvh_rebuild_degraded_ex(dbvh_tree_t* tree, float threshold, dbvh_degradation_metric_t metric, int32_t maxRebuilds) {
    if (!tree) return 0;
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    return static_cast<int32_t>(bvh->rebuildDegraded(threshold, static_cast<dbvh::DegradationMetric>(metric), maxRebuilds, 64));
}

int32_t dbvh_rebuild_degraded_adaptive(dbvh_tree_t* tree, float threshold, dbvh_degradation_metric_t metric, int32_t maxRebuilds, int32_t maxSubtreeLeaves) {
    if (!tree) return 0;
    dbvh::DBVH<int32_t>* bvh = reinterpret_cast<dbvh::DBVH<int32_t>*>(tree);
    return static_cast<int32_t>(bvh->rebuildDegraded(threshold, static_cast<dbvh::DegradationMetric>(metric), maxRebuilds, maxSubtreeLeaves));
}

int32_t dbvh_get_height(const dbvh_tree_t* tree) {
    if (!tree) return 0;
    const dbvh::DBVH<int32_t>* bvh = reinterpret_cast<const dbvh::DBVH<int32_t>*>(tree);
    return static_cast<int32_t>(bvh->getHeight());
}

float dbvh_get_degradation_alpha(const dbvh_tree_t* tree) {
    if (!tree) return 0.0f;
    const dbvh::DBVH<int32_t>* bvh = reinterpret_cast<const dbvh::DBVH<int32_t>*>(tree);
    return bvh->getDegradationAlpha();
}

float dbvh_get_total_tree_area(const dbvh_tree_t* tree) {
    if (!tree) return 0.0f;
    const dbvh::DBVH<int32_t>* bvh = reinterpret_cast<const dbvh::DBVH<int32_t>*>(tree);
    return bvh->getTotalTreeArea();
}

void dbvh_get_root_bounds(const dbvh_tree_t* tree, float aabb[6]) {
    if (!tree) {
        for (int i = 0; i < 6; ++i) aabb[i] = 0.0f;
        return;
    }
    const dbvh::DBVH<int32_t>* bvh = reinterpret_cast<const dbvh::DBVH<int32_t>*>(tree);
    bvh->getRootBounds().toArray(aabb);
}

void dbvh_get_quality_metrics(const dbvh_tree_t* tree, dbvh_tree_metrics_t* metrics, float traversalCost, float isectCost) {
    if (!tree || !metrics) return;
    const dbvh::DBVH<int32_t>* bvh = reinterpret_cast<const dbvh::DBVH<int32_t>*>(tree);
    auto qm = bvh->computeQualityMetrics(traversalCost, isectCost);
    metrics->sahCostStandard = qm.sahCostStandard;
    metrics->sahCostNormalized = qm.sahCostNormalized;
    metrics->rootArea = qm.rootArea;
    metrics->treeHeight = qm.treeHeight;
    metrics->leafCount = qm.leafCount;
    metrics->nodeCount = qm.nodeCount;
}

void dbvh_get_ideal_quality_metrics(const dbvh_tree_t* tree, dbvh_tree_metrics_t* idealMetrics, float traversalCost, float isectCost) {
    if (!tree || !idealMetrics) return;
    const dbvh::DBVH<int32_t>* bvh = reinterpret_cast<const dbvh::DBVH<int32_t>*>(tree);
    auto qm = bvh->computeIdealQualityMetrics(traversalCost, isectCost);
    idealMetrics->sahCostStandard = qm.sahCostStandard;
    idealMetrics->sahCostNormalized = qm.sahCostNormalized;
    idealMetrics->rootArea = qm.rootArea;
    idealMetrics->treeHeight = qm.treeHeight;
    idealMetrics->leafCount = qm.leafCount;
    idealMetrics->nodeCount = qm.nodeCount;
}

void dbvh_compute_ideal_from_aabbs(const float* aabbArray, int32_t leafCount, dbvh_tree_metrics_t* idealMetrics, float traversalCost, float isectCost) {
    if (!aabbArray || leafCount <= 0 || !idealMetrics) return;
    std::vector<dbvh::AABB> leafAABBs;
    leafAABBs.reserve(static_cast<size_t>(leafCount));
    for (int32_t i = 0; i < leafCount; ++i) {
        leafAABBs.push_back(dbvh::AABB::fromArray(aabbArray + i * 6));
    }
    auto qm = dbvh::DBVH<int32_t>::computeIdealFromAABBs(leafAABBs, traversalCost, isectCost);
    idealMetrics->sahCostStandard = qm.sahCostStandard;
    idealMetrics->sahCostNormalized = qm.sahCostNormalized;
    idealMetrics->rootArea = qm.rootArea;
    idealMetrics->treeHeight = qm.treeHeight;
    idealMetrics->leafCount = qm.leafCount;
    idealMetrics->nodeCount = qm.nodeCount;
}

}