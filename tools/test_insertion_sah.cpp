#include "../sdbvh/sdbvh.hpp"
#include <iostream>
#include <vector>

int main()
{
    // Replicate convex pile initial boxes (8x8x10 = 640 boxes)
    int countX = 8, countZ = 8, layers = 10;
    float amplitude = 2.0f;
    float scatter = 2.0f * amplitude;

    std::vector<sdbvh::AABB> boxes;
    for (int layer = 0; layer < layers; ++layer)
    {
        for (int z = 0; z < countZ; ++z)
        {
            for (int x = 0; x < countX; ++x)
            {
                float posX = ((float)x - 0.5f * (float)countX) * scatter;
                float posZ = ((float)z - 0.5f * (float)countZ) * scatter;
                float posY = amplitude + 2.0f * amplitude * (float)layer;
                
                sdbvh::Vec3 min(posX - amplitude, posY - amplitude, posZ - amplitude);
                sdbvh::Vec3 max(posX + amplitude, posY + amplitude, posZ + amplitude);
                boxes.push_back(sdbvh::AABB(min, max));
            }
        }
    }

    std::cout << "Total boxes: " << boxes.size() << std::endl;

    // Test 1: Current Greedy SDBVH
    {
        sdbvh::SDBVH<int> bvh(boxes.size() * 2);
        for (size_t i = 0; i < boxes.size(); ++i)
            bvh.insert(boxes[i], (int)i);

        auto qm = bvh.computeQualityMetrics(1.0f, 1.0f);
        auto ideal = bvh.computeIdealQualityMetrics(1.0f, 1.0f);
        std::cout << "1. Greedy SDBVH: SAH_norm=" << qm.sahCostNormalized 
                  << ", Ideal=" << ideal.sahCostNormalized 
                  << ", Q_norm=" << (qm.sahCostNormalized / ideal.sahCostNormalized)
                  << ", Height=" << qm.treeHeight << std::endl;
    }

    // Test 2: Greedy SDBVH + rebuild() at the end
    {
        sdbvh::SDBVH<int> bvh(boxes.size() * 2);
        for (size_t i = 0; i < boxes.size(); ++i)
            bvh.insert(boxes[i], (int)i);
        bvh.rebuild();

        auto qm = bvh.computeQualityMetrics(1.0f, 1.0f);
        auto ideal = bvh.computeIdealQualityMetrics(1.0f, 1.0f);
        std::cout << "2. Greedy SDBVH + rebuild(): SAH_norm=" << qm.sahCostNormalized 
                  << ", Ideal=" << ideal.sahCostNormalized 
                  << ", Q_norm=" << (qm.sahCostNormalized / ideal.sahCostNormalized)
                  << ", Height=" << qm.treeHeight << std::endl;
    }

    // Test 3: Branch-and-Bound insertion
    {
        class TestBnB_BVH : public sdbvh::SDBVH<int>
        {
        public:
            TestBnB_BVH(size_t cap) : sdbvh::SDBVH<int>(cap) {}

            sdbvh::NodeIndex findBestSiblingBnB(const sdbvh::AABB& leafAABB) const
            {
                if (getRoot() == sdbvh::NULL_NODE) return sdbvh::NULL_NODE;

                float leafArea = leafAABB.surfaceArea();
                float bestCost = std::numeric_limits<float>::max();
                sdbvh::NodeIndex bestNode = getRoot();

                struct StackEntry { sdbvh::NodeIndex node; float inheritedCost; };
                std::vector<StackEntry> stack;
                stack.push_back({getRoot(), 0.0f});

                while (!stack.empty())
                {
                    auto [idx, inherited] = stack.back();
                    stack.pop_back();

                    const auto& node = getNode(idx);
                    float directCost = sdbvh::AABB::unite(leafAABB, node.aabb).surfaceArea();
                    float totalCost = directCost + inherited;

                    if (totalCost < bestCost)
                    {
                        bestCost = totalCost;
                        bestNode = idx;
                    }

                    float newInherited = inherited + (directCost - node.aabb.surfaceArea());
                    float lowerBound = leafArea + newInherited;
                    if (lowerBound >= bestCost) continue;

                    if (!node.isLeaf())
                    {
                        stack.push_back({node.child[0], newInherited});
                        stack.push_back({node.child[1], newInherited});
                    }
                }
                return bestNode;
            }
        };
    }

    return 0;
}