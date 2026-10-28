#include "../sdbvh/sdbvh.hpp"
#include "box3d/collision.h"
#include <iostream>
#include <vector>
#include <chrono>
#include <cmath>
#include <random>
#include <iomanip>
#include <fstream>
#include <string>

// Estrutura para registro de resultados de benchmark de broadphase
struct PureMetrics {
    std::string engine;
    int actors;
    float threshold;
    int rebuilds;
    double move_ms;
    double query_ms;
    double rebuild_ms;
    double total_ms;
    size_t pair_count;
    int tree_height;
    float sah_norm;
    double memory_mb;
};

struct BoxData {
    float minX, minY, minZ;
    float maxX, maxY, maxZ;
    float vx, vy, vz;
};

std::vector<BoxData> generateBoxes(int count, float worldSize = 200.0f) {
    std::vector<BoxData> boxes(count);
    std::mt19937 rng(1337);
    std::uniform_real_distribution<float> posDist(-worldSize * 0.5f, worldSize * 0.5f);
    std::uniform_real_distribution<float> velDist(-0.5f, 0.5f);
    float boxExtent = 0.5f;

    for (int i = 0; i < count; ++i) {
        float cx = posDist(rng);
        float cy = posDist(rng);
        float cz = posDist(rng);

        boxes[i].minX = cx - boxExtent;
        boxes[i].minY = cy - boxExtent;
        boxes[i].minZ = cz - boxExtent;
        boxes[i].maxX = cx + boxExtent;
        boxes[i].maxY = cy + boxExtent;
        boxes[i].maxZ = cz + boxExtent;

        boxes[i].vx = velDist(rng);
        boxes[i].vy = velDist(rng);
        boxes[i].vz = velDist(rng);
    }
    return boxes;
}

// Benchmark da SDBVH
PureMetrics benchmarkSDBVH(int actorCount, int steps, float threshold, int rebuildBudget) {
    auto boxes = generateBoxes(actorCount);
    
    sdbvh::SDBVH<int32_t> bvh(actorCount * 2);
    sdbvh::SDBVHConfig cfg;
    cfg.enableRebuild = true;
    cfg.enableAdaptiveRebuild = true;
    cfg.maxSubtreeLeaves = 64;
    cfg.areaRatioThreshold = threshold;
    cfg.subtreeSAHThreshold = threshold;
    cfg.maxRebuildsPerFrame = rebuildBudget;
    cfg.rebuildInterval = 30;
    bvh.setConfig(cfg);

    std::vector<int32_t> proxyIds(actorCount);
    for (int i = 0; i < actorCount; ++i) {
        sdbvh::AABB aabb(sdbvh::Vec3(boxes[i].minX, boxes[i].minY, boxes[i].minZ),
                        sdbvh::Vec3(boxes[i].maxX, boxes[i].maxY, boxes[i].maxZ));
        proxyIds[i] = bvh.insert(aabb, i);
    }
    bvh.rebuild();

    double totalMoveUs = 0.0;
    double totalQueryUs = 0.0;
    double totalRebuildUs = 0.0;
    size_t lastPairCount = 0;

    int currentInterval = 30;

    for (int step = 0; step < steps; ++step) {
        // Proxies
        auto t0 = std::chrono::high_resolution_clock::now();
        for (int i = 0; i < actorCount; ++i) {
            boxes[i].minX += boxes[i].vx * 0.016f;
            boxes[i].maxX += boxes[i].vx * 0.016f;
            boxes[i].minY += boxes[i].vy * 0.016f;
            boxes[i].maxY += boxes[i].vy * 0.016f;
            boxes[i].minZ += boxes[i].vz * 0.016f;
            boxes[i].maxZ += boxes[i].vz * 0.016f;

            sdbvh::AABB aabb(sdbvh::Vec3(boxes[i].minX, boxes[i].minY, boxes[i].minZ),
                            sdbvh::Vec3(boxes[i].maxX, boxes[i].maxY, boxes[i].maxZ));
            sdbvh::Vec3 vel(boxes[i].vx, boxes[i].vy, boxes[i].vz);
            bvh.moveObject(proxyIds[i], aabb, vel);
        }
        auto t1 = std::chrono::high_resolution_clock::now();
        totalMoveUs += std::chrono::duration<double, std::micro>(t1 - t0).count();

        // Consulta de pares
        auto t2 = std::chrono::high_resolution_clock::now();
        size_t pairsFound = 0;
        bvh.queryPairs([&pairsFound](size_t, size_t) {
            pairsFound++;
        });
        auto t3 = std::chrono::high_resolution_clock::now();
        totalQueryUs += std::chrono::duration<double, std::micro>(t3 - t2).count();
        lastPairCount = pairsFound;

        // Rebuild adaptativo
        auto t4 = std::chrono::high_resolution_clock::now();
        if (step % currentInterval == 0) {
            int rebuilt = bvh.rebuildDegraded(threshold, sdbvh::DegradationMetric::AreaRatio, rebuildBudget, 64);
            if (rebuilt < 2) currentInterval = 60;
            else currentInterval = 30;
        }
        auto t5 = std::chrono::high_resolution_clock::now();
        totalRebuildUs += std::chrono::duration<double, std::micro>(t5 - t4).count();
    }

    auto qm = bvh.computeQualityMetrics(1.0f, 1.0f);
    double memMb = (double)(bvh.nodeCount() * sizeof(sdbvh::Node<int32_t>)) / (1024.0 * 1024.0);

    PureMetrics m;
    m.engine = "SSDBVH";
    m.actors = actorCount;
    m.threshold = threshold;
    m.rebuilds = rebuildBudget;
    m.move_ms = (totalMoveUs / (double)steps) / 1000.0;
    m.query_ms = (totalQueryUs / (double)steps) / 1000.0;
    m.rebuild_ms = (totalRebuildUs / (double)steps) / 1000.0;
    m.total_ms = m.move_ms + m.query_ms + m.rebuild_ms;
    m.pair_count = lastPairCount;
    m.tree_height = qm.treeHeight;
    m.sah_norm = qm.sahCostNormalized;
    m.memory_mb = memMb;
    return m;
}

// Benchmark do Box3D Nativo (b3DynamicTree)
PureMetrics benchmarkNative(int actorCount, int steps) {
    auto boxes = generateBoxes(actorCount);

    b3DynamicTree tree = b3DynamicTree_Create(actorCount + 64);
    std::vector<int> proxyIds(actorCount);

    for (int i = 0; i < actorCount; ++i) {
        b3AABB aabb;
        aabb.lowerBound = (b3Pos){ boxes[i].minX, boxes[i].minY, boxes[i].minZ };
        aabb.upperBound = (b3Pos){ boxes[i].maxX, boxes[i].maxY, boxes[i].maxZ };
        proxyIds[i] = b3DynamicTree_CreateProxy(&tree, aabb, 0xFFFFFFFFFFFFFFFFull, (uint64_t)i);
    }
    b3DynamicTree_Rebuild(&tree, true);

    double totalMoveUs = 0.0;
    double totalQueryUs = 0.0;
    double totalRebuildUs = 0.0;
    size_t lastPairCount = 0;

    for (int step = 0; step < steps; ++step) {
        // Movimentação
        auto t0 = std::chrono::high_resolution_clock::now();
        for (int i = 0; i < actorCount; ++i) {
            boxes[i].minX += boxes[i].vx * 0.016f;
            boxes[i].maxX += boxes[i].vx * 0.016f;
            boxes[i].minY += boxes[i].vy * 0.016f;
            boxes[i].maxY += boxes[i].vy * 0.016f;
            boxes[i].minZ += boxes[i].vz * 0.016f;
            boxes[i].maxZ += boxes[i].vz * 0.016f;

            b3AABB aabb;
            aabb.lowerBound = (b3Pos){ boxes[i].minX, boxes[i].minY, boxes[i].minZ };
            aabb.upperBound = (b3Pos){ boxes[i].maxX, boxes[i].maxY, boxes[i].maxZ };
            b3DynamicTree_MoveProxy(&tree, proxyIds[i], aabb);
        }
        auto t1 = std::chrono::high_resolution_clock::now();
        totalMoveUs += std::chrono::duration<double, std::micro>(t1 - t0).count();

        // Consulta de pares
        auto t2 = std::chrono::high_resolution_clock::now();
        size_t pairsFound = 0;
        for (int i = 0; i < actorCount; ++i) {
            b3AABB aabb = b3DynamicTree_GetAABB(&tree, proxyIds[i]);
            b3DynamicTree_Query(&tree, aabb, 0xFFFFFFFFFFFFFFFFull, false, [](int, uint64_t, void* ctx) -> bool {
                (*reinterpret_cast<size_t*>(ctx))++;
                return true;
            }, &pairsFound);
        }
        auto t3 = std::chrono::high_resolution_clock::now();
        totalQueryUs += std::chrono::duration<double, std::micro>(t3 - t2).count();
        lastPairCount = pairsFound / 2;

        // Rebuild incremental nativo
        auto t4 = std::chrono::high_resolution_clock::now();
        b3DynamicTree_Rebuild(&tree, false);
        auto t5 = std::chrono::high_resolution_clock::now();
        totalRebuildUs += std::chrono::duration<double, std::micro>(t5 - t4).count();
    }

    int height = b3DynamicTree_GetHeight(&tree);
    double memMb = (double)(tree.nodeCapacity * sizeof(b3TreeNode) + tree.proxyCapacity * sizeof(b3TreeProxy)) / (1024.0 * 1024.0);

    b3DynamicTree_Destroy(&tree);

    PureMetrics m;
    m.engine = "Box3D Nativo";
    m.actors = actorCount;
    m.threshold = 0.0f;
    m.rebuilds = 0;
    m.move_ms = (totalMoveUs / (double)steps) / 1000.0;
    m.query_ms = (totalQueryUs / (double)steps) / 1000.0;
    m.rebuild_ms = (totalRebuildUs / (double)steps) / 1000.0;
    m.total_ms = m.move_ms + m.query_ms + m.rebuild_ms;
    m.pair_count = lastPairCount;
    m.tree_height = height;
    m.sah_norm = 0.0f;
    m.memory_mb = memMb;
    return m;
}

int main(int argc, char** argv) {
    std::vector<int> scales = {10, 100, 500, 1000, 10000, 100000, 1000000};
    int steps = 50;
    std::string csvOut = "benchmark_results/pure_broadphase_summary.csv";

    if (argc > 1) {
        steps = std::max(5, std::atoi(argv[1]));
    }

    std::cout << "================================================================================" << std::endl;
    std::cout << " BENCHMARK DE BROAD-PHASE" << std::endl;
    std::cout << "================================================================================" << std::endl;
    std::cout << " Steps avaliados: " << steps << std::endl;
    std::cout << " Escalas: 10, 100, 500, 1.000, 10.000, 100.000, 1.000.000" << std::endl;
    std::cout << "================================================================================" << std::endl;

    std::ofstream out(csvOut);
    out << "engine,actors,threshold,rebuilds,move_ms,query_ms,rebuild_ms,total_ms,pairs,tree_height,sah_norm,memory_mb\n";

    for (int N : scales) {
        std::cout << "\n>>> INICIANDO ESCALA N = " << N << " corpos <<<" << std::endl;

        // Box3D Nativo(até 100k. 1M pesou demais)
        if (N <= 100000) {
            std::cout << "  [1/10] Box3D Nativo ... " << std::flush;
            auto m = benchmarkNative(N, steps);
            std::cout << "OK! Move: " << m.move_ms << "ms | Query: " << m.query_ms << "ms | Total: " 
                      << m.total_ms << "ms | H=" << m.tree_height << " | RAM=" << m.memory_mb << "MB" << std::endl;
            out << m.engine << "," << m.actors << "," << m.threshold << "," << m.rebuilds << ","
                << m.move_ms << "," << m.query_ms << "," << m.rebuild_ms << "," << m.total_ms << ","
                << m.pair_count << "," << m.tree_height << "," << m.sah_norm << "," << m.memory_mb << "\n";
            out.flush();
        }

        // SDBVH
        std::vector<float> thresholds = {1.3f, 1.5f, 1.8f};
        std::vector<int> rebuilds = {2, 4, 6};

        int count = (N <= 100000) ? 2 : 1;
        for (float th : thresholds) {
            for (int rb : rebuilds) {
                std::cout << "  [" << count++ << "/10] SDBVH (th=" << th << ", rb=" << rb << ") ... " << std::flush;
                auto m = benchmarkSDBVH(N, steps, th, rb);
                std::cout << "OK! Move: " << m.move_ms << "ms | Query: " << m.query_ms << "ms | Total: " 
                          << m.total_ms << "ms | H=" << m.tree_height << " | RAM=" << m.memory_mb << "MB" << std::endl;
                out << m.engine << "," << m.actors << "," << m.threshold << "," << m.rebuilds << ","
                    << m.move_ms << "," << m.query_ms << "," << m.rebuild_ms << "," << m.total_ms << ","
                    << m.pair_count << "," << m.tree_height << "," << m.sah_norm << "," << m.memory_mb << "\n";
                out.flush();
            }
        }
    }

    out.close();
    std::cout << "\n================================================================================" << std::endl;
    std::cout << " Bateria concluída! Resumo salvo em: " << csvOut << std::endl;
    std::cout << "================================================================================" << std::endl;
    return 0;
}