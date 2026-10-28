// SPDX-FileCopyrightText: 2025 Erin Catto
// SPDX-License-Identifier: MIT

#pragma once

#include "dynamic_tree.h"
#include "table.h"

#include "box3d/collision.h"
#include "box3d/types.h"

// SDBVH Integration: Include C API interface for SDBVH
#include "../sdbvh/sdbvh_c_api.h"

typedef struct b3Shape b3Shape;
typedef struct b3Stack b3Stack;
typedef struct b3World b3World;

// Store the proxy type in the lower 2 bits of the proxy key. This leaves 30 bits for the id.
#define B3_PROXY_TYPE( KEY ) ( (b3BodyType)( ( KEY ) & 3 ) )
#define B3_PROXY_ID( KEY ) ( ( KEY ) >> 2 )
#define B3_PROXY_KEY( ID, TYPE ) ( ( ( ID ) << 2 ) | ( TYPE ) )

/// The broad-phase is used for computing pairs and performing volume queries and ray casts.
/// This broad-phase does not persist pairs. Instead, this reports potentially new pairs.
/// It is up to the client to consume the new pairs and to track subsequent overlap.
typedef struct b3BroadPhase
{
	// One tree for each body type.
	b3DynamicTree trees[b3_bodyTypeCount];

	// The moved siblings gathered from the dynamic body tree.
	int* movedSiblings;

	// Tracks shape pairs that have a b3Contact
	// todo pairSet can grow quite large on the first time step and remain large
	b3HashSet pairSet;

	// SDBVH Integration: Pointer to SDBVH instance, active flag, dirty flag, and runtime configuration
	bool useSDBVH;
	bool dynamicMoved;
	void* sdbvhTree;
	sdbvh_config_t sdbvhConfig;
	int currentRebuildInterval;
	int currentMaxRebuilds;
	int adaptiveCooldownCounter;
} b3BroadPhase;

void b3CreateBroadPhase( b3BroadPhase* bp, const b3Capacity* capacity, bool useSDBVH );
void b3DestroyBroadPhase( b3BroadPhase* bp );
// SDBVH Integration: Set runtime configuration for SDBVH
void b3BroadPhase_SetConfig( b3BroadPhase* bp, const sdbvh_config_t* config );
void b3BroadPhase_Rebuild( b3BroadPhase* bp );

int b3BroadPhase_CreateProxy( b3BroadPhase* bp, b3BodyType proxyType, b3AABB aabb, uint64_t categoryBits, int shapeIndex,
							  bool forcePairCreation );
void b3BroadPhase_DestroyProxy( b3BroadPhase* bp, int proxyKey );

// SDBVH Integration: Pass linear velocity vector for predictive fattening
void b3BroadPhase_MoveProxy( b3BroadPhase* bp, int proxyKey, b3AABB aabb, b3Vec3 velocity );
void b3BroadPhase_EnlargeProxy( b3BroadPhase* bp, int proxyKey, b3AABB aabb );

int b3BroadPhase_GetShapeIndex( b3BroadPhase* bp, int proxyKey );

// SDBVH Integration: Unified broad-phase query and raycast routing through either b3DynamicTree or SDBVH
b3TreeStats b3BroadPhase_Query( const b3BroadPhase* bp, b3BodyType type, b3AABB aabb, uint64_t maskBits, bool requireAllBits,
								b3TreeQueryCallbackFcn* callback, void* context );

b3TreeStats b3BroadPhase_RayCast( const b3BroadPhase* bp, b3BodyType type, const b3RayCastInput* input, uint64_t maskBits,
								  bool requireAllBits, b3TreeRayCastCallbackFcn* callback, void* context );

void b3UpdateBroadPhasePairs( b3World* world );
bool b3BroadPhase_TestOverlap( const b3BroadPhase* bp, int proxyKeyA, int proxyKeyB );
b3AABB b3BroadPhase_GetProxyAABB( const b3BroadPhase* bp, int proxyKey );

void b3ValidateBroadPhase( const b3BroadPhase* bp );
void b3ValidateNoMoved( const b3BroadPhase* bp );

// SDBVH Integration: Compute broadphase quality metrics and ground truth ideal comparison
void b3BroadPhase_GetQualityMetrics( const b3BroadPhase* bp, b3BodyType bodyType, bool computeIdeal, float traversalCost,
									 float isectCost, b3BroadPhaseQualityMetrics* outMetrics );

static inline void b3BroadPhase_MarkProxyMovedSerial( b3BroadPhase* bp, int proxyKey )
{
	b3BodyType proxyType = B3_PROXY_TYPE( proxyKey );
	int proxyId = B3_PROXY_ID( proxyKey );
	if ( bp->useSDBVH && proxyType == b3_dynamicBody )
	{
		bp->dynamicMoved = true;
		return;
	}
	b3DynamicTree_MarkProxyMovedSerial( bp->trees + proxyType, proxyId );
}

static inline void b3BroadPhase_MarkProxyMoved( b3BroadPhase* bp, int proxyKey, b3AABB aabb )
{
	b3BodyType proxyType = B3_PROXY_TYPE( proxyKey );
	int proxyId = B3_PROXY_ID( proxyKey );
	if ( bp->useSDBVH && proxyType == b3_dynamicBody )
	{
		bp->dynamicMoved = true;
		sdbvh_enlarge_proxy( (sdbvh_tree_t*)bp->sdbvhTree, proxyId, (const float*)&aabb );
		return;
	}
	b3DynamicTree_MarkProxyMoved( bp->trees + proxyType, proxyId, aabb );
}
