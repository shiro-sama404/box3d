#pragma once

namespace sdbvh
{

struct Vec3
{
    float x{0.0f}, y{0.0f}, z{0.0f};

    constexpr Vec3() = default;
    constexpr Vec3(float x_, float y_, float z_) noexcept : x(x_), y(y_), z(z_) {}

    constexpr Vec3 operator -() const noexcept { return Vec3(-x, -y, -z); }
    constexpr Vec3& operator +=(const Vec3& v) noexcept
    {
        x += v.x; y += v.y; z += v.z;
        return *this;
    }
    constexpr Vec3& operator -=(const Vec3& v) noexcept
    {
        x -= v.x; y -= v.y; z -= v.z;
        return *this;
    }
    constexpr Vec3& operator *=(float s) noexcept
    {
        x *= s; y *= s; z *= s;
        return *this;
    }

    friend constexpr Vec3 operator +(Vec3 a, const Vec3& b) noexcept { a += b; return a; }
    friend constexpr Vec3 operator -(Vec3 a, const Vec3& b) noexcept { a -= b; return a; }
    friend constexpr Vec3 operator *(Vec3 a, float s) noexcept { a *= s; return a; }
    friend constexpr Vec3 operator *(float s, Vec3 a) noexcept { a *= s; return a; }
};

} // namespace sdbvh