#pragma once

#include "vec3.h"
#include <algorithm>

#if !defined(BOX3D_DISABLE_SIMD) && (defined(__SSE2__) || defined(_M_X64) || (defined(_M_IX86_FP) && _M_IX86_FP >= 2))
#define SDBVH_SIMD_SSE2 1
#include <emmintrin.h>
#endif

namespace sdbvh
{

struct AABB
{
    Vec3 min;
    Vec3 max;

    constexpr AABB() = default;
    constexpr AABB(const Vec3& min_, const Vec3& max_) noexcept : min(min_), max(max_) {}

    /// @brief Área de superfície da caixa (usada na SAH).
    [[nodiscard]] constexpr float surfaceArea() const noexcept
    {
        Vec3 d{max - min};
        return 2.0f * (d.x * d.y + d.y * d.z + d.z * d.x);
    }

    /// @brief Centróide da caixa.
    [[nodiscard]] constexpr Vec3 centroid() const noexcept
    {
        return Vec3(
            (min.x + max.x) * 0.5f,
            (min.y + max.y) * 0.5f,
            (min.z + max.z) * 0.5f
        );
    }

    [[nodiscard]] inline bool overlaps(const AABB& other) const noexcept
    {
#if defined(SDBVH_SIMD_SSE2)
        const float* a_base = &min.x;
        const float* b_base = &other.min.x;

        __m128 a_v1 = _mm_loadu_ps(a_base + 2);
        __m128 a_lower = _mm_loadu_ps(a_base);
        __m128 a_upper = _mm_shuffle_ps(a_v1, a_v1, _MM_SHUFFLE(3, 3, 2, 1));

        __m128 b_v1 = _mm_loadu_ps(b_base + 2);
        __m128 b_lower = _mm_loadu_ps(b_base);
        __m128 b_upper = _mm_shuffle_ps(b_v1, b_v1, _MM_SHUFFLE(3, 3, 2, 1));

        __m128 test = _mm_and_ps(_mm_cmple_ps(a_lower, b_upper), _mm_cmple_ps(b_lower, a_upper));
        return (_mm_movemask_ps(test) & 0x7) == 0x7;
#else
        return (min.x <= other.max.x && max.x >= other.min.x) &&
               (min.y <= other.max.y && max.y >= other.min.y) &&
               (min.z <= other.max.z && max.z >= other.min.z);
#endif
    }

    [[nodiscard]] inline bool contains(const AABB& other) const noexcept
    {
#if defined(SDBVH_SIMD_SSE2)
        const float* a_base = &min.x;
        const float* b_base = &other.min.x;

        __m128 a_v1 = _mm_loadu_ps(a_base + 2);
        __m128 a_lower = _mm_loadu_ps(a_base);
        __m128 a_upper = _mm_shuffle_ps(a_v1, a_v1, _MM_SHUFFLE(3, 3, 2, 1));

        __m128 b_v1 = _mm_loadu_ps(b_base + 2);
        __m128 b_lower = _mm_loadu_ps(b_base);
        __m128 b_upper = _mm_shuffle_ps(b_v1, b_v1, _MM_SHUFFLE(3, 3, 2, 1));

        __m128 test = _mm_and_ps(_mm_cmple_ps(a_lower, b_lower), _mm_cmple_ps(b_upper, a_upper));
        return (_mm_movemask_ps(test) & 0x7) == 0x7;
#else
        return (min.x <= other.min.x && max.x >= other.max.x) &&
               (min.y <= other.min.y && max.y >= other.max.y) &&
               (min.z <= other.min.z && max.z >= other.max.z);
#endif
    }

    /// @brief Expande a caixa uniformemente por uma margem epsilon.
    constexpr void expand(float epsilon) noexcept
    {
        min.x -= epsilon; min.y -= epsilon; min.z -= epsilon;
        max.x += epsilon; max.y += epsilon; max.z += epsilon;
    }

    /// @brief Expande a caixa de forma preditiva na direção do vetor de deslocamento.
    void expandPredictive(const Vec3& velocity, float dt = (1.0f / 60.0f)) noexcept
    {
        Vec3 disp = velocity * dt;
        if (disp.x > 0.0f) max.x += disp.x;
        else               min.x += disp.x;
        if (disp.y > 0.0f) max.y += disp.y;
        else               min.y += disp.y;
        if (disp.z > 0.0f) max.z += disp.z;
        else               min.z += disp.z;
    }

    [[nodiscard]] static constexpr AABB unite(const AABB& a, const AABB& b) noexcept
    {
        return AABB(
            Vec3(std::min(a.min.x, b.min.x), std::min(a.min.y, b.min.y), std::min(a.min.z, b.min.z)),
            Vec3(std::max(a.max.x, b.max.x), std::max(a.max.y, b.max.y), std::max(a.max.z, b.max.z))
        );
    }

    /// @brief Testa interseção de um raio com este AABB.
    /// @param origin Origem do raio.
    /// @param invDir Inverso da direção do raio (1.0 / dir) para evitar divisões.
    /// @param maxFraction Limite superior do t no raio.
    /// @return true se o raio cruza o AABB com um t em [0, maxFraction].
    [[nodiscard]] constexpr bool rayIntersects(const Vec3& origin, const Vec3& invDir, float maxFraction) const noexcept
    {
        float tx1 = (min.x - origin.x) * invDir.x;
        float tx2 = (max.x - origin.x) * invDir.x;
        float tmin = std::min(tx1, tx2);
        float tmax = std::max(tx1, tx2);

        float ty1 = (min.y - origin.y) * invDir.y;
        float ty2 = (max.y - origin.y) * invDir.y;
        tmin = std::max(tmin, std::min(ty1, ty2));
        tmax = std::min(tmax, std::max(ty1, ty2));

        float tz1 = (min.z - origin.z) * invDir.z;
        float tz2 = (max.z - origin.z) * invDir.z;
        tmin = std::max(tmin, std::min(tz1, tz2));
        tmax = std::min(tmax, std::max(tz1, tz2));

        return tmax >= std::max(tmin, 0.0f) && tmin <= maxFraction;
    }

    /// @brief Cria um AABB a partir de um array de 6 floats (C API).
    [[nodiscard]] static constexpr AABB fromArray(const float arr[6]) noexcept
    {
        return AABB(Vec3(arr[0], arr[1], arr[2]), Vec3(arr[3], arr[4], arr[5]));
    }

    /// @brief Preenche um array de 6 floats com os dados do AABB (C API).
    constexpr void toArray(float arr[6]) const noexcept
    {
        arr[0] = min.x; arr[1] = min.y; arr[2] = min.z;
        arr[3] = max.x; arr[4] = max.y; arr[5] = max.z;
    }
};

} // namespace sdbvh