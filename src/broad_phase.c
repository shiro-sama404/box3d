// SPDX-FileCopyrightText: 2025 Erin Catto
// SPDX-License-Identifier: MIT

#include "broad_phase.h"

#include "aabb.h"
#include "arena_allocator.h"
#include "body.h"
#include "compound.h"
#include "contact.h"
#include "core.h"
#include "dynamic_tree.h"
#include "parallel_for.h"
#include "physics_world.h"
#include "platform.h"
#include "qsort.h"
#include "shape.h"
#include "simd.h"
#include "../dbvh/dbvh_c_api.h"

#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

void b3CreateBroadPhase( b3BroadPhase* bp, const b3Capacity* capacity, bool useDBVH )
{
	_Static_assert( b3_bodyTypeCount == 3, "must be three body types" );

	bp->pairSet = b3CreateSet( b3MaxInt( 32, 2 * capacity->contactCount ) );

	int staticCapacity = b3MaxInt( 16, capacity->staticShapeCount );
	bp->trees[b3_staticBody] = b3DynamicTree_Create( staticCapacity );

	int kinematicCapacity = 16;
	bp->trees[b3_kinematicBody] = b3DynamicTree_Create( kinematicCapacity );

	int dynamicCapacity = b3MaxInt( 16, capacity->dynamicShapeCount );
	bp->movedSiblings = NULL;

	// DBVH Integration: Setup DBVH lifecycle and default configuration if enabled
	bp->useDBVH = useDBVH;
	bp->dbvhConfig.enableRebuild = true;
	bp->dbvhConfig.enableFattening = true;
	bp->dbvhConfig.enablePredictive = true;
	bp->dbvhConfig.enableRotations = true;
	bp->dbvhConfig.enableAdaptiveRebuild = true;
	bp->dbvhConfig.degradationMetric = DBVH_METRIC_AREA_RATIO;
	bp->dbvhConfig.rebuildThreshold = 1.80f;
	bp->dbvhConfig.areaRatioThreshold = 1.80f;
	bp->dbvhConfig.subtreeSAHThreshold = 1.80f;
	bp->dbvhConfig.rebuildInterval = 30;
	bp->dbvhConfig.maxRebuildsPerFrame = 2;
	bp->dbvhConfig.maxSubtreeLeaves = 64;

	bp->currentRebuildInterval = bp->dbvhConfig.rebuildInterval;
	bp->currentMaxRebuilds = bp->dbvhConfig.maxRebuildsPerFrame;
	bp->adaptiveCooldownCounter = 0;

	if ( useDBVH )
	{
		bp->trees[b3_dynamicBody] = (b3DynamicTree){ 0 };
		bp->dbvhTree = dbvh_create( dynamicCapacity );
		dbvh_set_config( bp->dbvhTree, &bp->dbvhConfig );
	}
	else
	{
		bp->trees[b3_dynamicBody] = b3DynamicTree_Create( dynamicCapacity );
		bp->dbvhTree = NULL;
	}

}

// DBVH Integration: Update DBVH runtime parameters
void b3BroadPhase_SetConfig( b3BroadPhase* bp, const dbvh_config_t* config )
{
	if ( config != NULL )
	{
		bp->dbvhConfig = *config;
		bp->currentRebuildInterval = config->rebuildInterval;
		bp->currentMaxRebuilds = config->maxRebuildsPerFrame;
		bp->adaptiveCooldownCounter = 0;
		if ( bp->useDBVH && bp->dbvhTree != NULL )
		{
			dbvh_set_config( bp->dbvhTree, config );
		}
	}
}

void b3BroadPhase_Rebuild( b3BroadPhase* bp )
{
	if ( bp->useDBVH && bp->dbvhTree != NULL )
	{
		dbvh_rebuild( bp->dbvhTree );
	}
}

void b3DestroyBroadPhase( b3BroadPhase* bp )
{
	for ( int i = 0; i < b3_bodyTypeCount; ++i )
	{
		b3DynamicTree_Destroy( bp->trees + i );
	}

	b3DestroySet( &bp->pairSet );
	// DBVH Integration: Cleanup DBVH C++ instance
	if ( bp->useDBVH )
	{
		dbvh_destroy( bp->dbvhTree );
	}


	memset( bp, 0, sizeof( b3BroadPhase ) );
}

int b3BroadPhase_CreateProxy( b3BroadPhase* bp, b3BodyType proxyType, b3AABB aabb, uint64_t categoryBits, int shapeIndex,
							  bool forcePairCreation )
{
	B3_ASSERT( 0 <= proxyType && proxyType < b3_bodyTypeCount );
	int proxyId;
	if ( bp->useDBVH && proxyType == b3_dynamicBody )
	{
		float aabbArray[6] = { aabb.lowerBound.x, aabb.lowerBound.y, aabb.lowerBound.z, aabb.upperBound.x, aabb.upperBound.y, aabb.upperBound.z };
		proxyId = dbvh_insert_with_category( bp->dbvhTree, aabbArray, shapeIndex, categoryBits );
	}
	else
	{
		bool mark = ( proxyType != b3_staticBody || forcePairCreation );
		proxyId = b3CreateTreeProxyInternal( bp->trees + proxyType, aabb, categoryBits, shapeIndex, mark );
	}
	int proxyKey = B3_PROXY_KEY( proxyId, proxyType );
	return proxyKey;
}

void b3BroadPhase_DestroyProxy( b3BroadPhase* bp, int proxyKey )
{
	b3BodyType proxyType = B3_PROXY_TYPE( proxyKey );
	int proxyId = B3_PROXY_ID( proxyKey );

	B3_ASSERT( 0 <= proxyType && proxyType < b3_bodyTypeCount );
	// DBVH Integration: Remove proxy from DBVH
	if ( bp->useDBVH && proxyType == b3_dynamicBody )
	{
		dbvh_remove( bp->dbvhTree, proxyId );
	}
	else
	{
		b3DynamicTree_DestroyProxy( bp->trees + proxyType, proxyId );
	}
}

void b3BroadPhase_MoveProxy( b3BroadPhase* bp, int proxyKey, b3AABB aabb, b3Vec3 velocity )
{
	b3BodyType proxyType = B3_PROXY_TYPE( proxyKey );
	int proxyId = B3_PROXY_ID( proxyKey );

	if ( bp->useDBVH && proxyType == b3_dynamicBody )
	{
		int newId = dbvh_move( bp->dbvhTree, proxyId, (const float*)&aabb, (const float*)&velocity, 0.01f );
		B3_ASSERT( newId == proxyId );
	}
	else
	{
		bool mark = true;
		b3DynamicTree_MoveProxyInternal( bp->trees + proxyType, proxyId, aabb, mark );
	}
}

// DBVH Integration: Enlarge/update proxy in DBVH or DynamicTree
void b3BroadPhase_EnlargeProxy( b3BroadPhase* bp, int proxyKey, b3AABB aabb )
{
	b3BodyType typeIndex = B3_PROXY_TYPE( proxyKey );
	int proxyId = B3_PROXY_ID( proxyKey );

	if ( bp->useDBVH && typeIndex == b3_dynamicBody )
	{
		dbvh_enlarge_proxy( bp->dbvhTree, proxyId, (const float*)&aabb );
	}
	else
	{
		b3DynamicTree* dynamicTree = bp->trees + typeIndex;
		b3AABB treeAABB = b3DynamicTree_GetAABB( dynamicTree, proxyId );
		if ( b3AABB_Contains( treeAABB, aabb ) == false )
		{
			b3DynamicTree_EnlargeProxy( dynamicTree, proxyId, aabb );
		}
	}
}

// DBVH Integration: Trampoline callbacks adapting C++ DBVH query/raycast signatures to Box3D C callbacks
typedef struct b3DBVHTrampolineContext {
	b3TreeQueryCallbackFcn* queryCallback;
	b3TreeRayCastCallbackFcn* rayCastCallback;
	const b3RayCastInput* rayInput;
	void* userContext;
} b3DBVHTrampolineContext;

static bool b3DBVHQueryTrampoline(int32_t leafIndex, int32_t userData, void* context) {
	b3DBVHTrampolineContext* ctx = (b3DBVHTrampolineContext*)context;
	return ctx->queryCallback((int)leafIndex, (uint64_t)userData, ctx->userContext);
}

static float b3DBVHRayCastTrampoline(int32_t leafIndex, int32_t userData, void* context) {
	b3DBVHTrampolineContext* ctx = (b3DBVHTrampolineContext*)context;
	return ctx->rayCastCallback(ctx->rayInput, (int)leafIndex, (uint64_t)userData, ctx->userContext);
}

// DBVH Integration: Route AABB queries to DBVH when targeting dynamic body tree
b3TreeStats b3BroadPhase_Query( const b3BroadPhase* bp, b3BodyType type, b3AABB aabb, uint64_t maskBits, bool requireAllBits, b3TreeQueryCallbackFcn* callback, void* context )
{
	if ( bp->useDBVH && type == b3_dynamicBody )
	{
		b3DBVHTrampolineContext trampCtx = { callback, NULL, NULL, context };
		float aabbArray[6] = { aabb.lowerBound.x, aabb.lowerBound.y, aabb.lowerBound.z, aabb.upperBound.x, aabb.upperBound.y, aabb.upperBound.z };
		dbvh_query_aabb( bp->dbvhTree, aabbArray, b3DBVHQueryTrampoline, &trampCtx );
		b3TreeStats stats = {0};
		return stats;
	}
	else
	{
		return b3DynamicTree_Query( bp->trees + type, aabb, maskBits, requireAllBits, callback, context );
	}
}

// DBVH Integration: Route raycasts to DBVH when targeting dynamic body tree
b3TreeStats b3BroadPhase_RayCast( const b3BroadPhase* bp, b3BodyType type, const b3RayCastInput* input, uint64_t maskBits, bool requireAllBits, b3TreeRayCastCallbackFcn* callback, void* context )
{
	if ( bp->useDBVH && type == b3_dynamicBody )
	{
		b3DBVHTrampolineContext trampCtx = { NULL, callback, input, context };
		float originArray[3] = { input->origin.x, input->origin.y, input->origin.z };
		float translationArray[3] = { input->translation.x, input->translation.y, input->translation.z };
		dbvh_ray_cast( bp->dbvhTree, originArray, translationArray, input->maxFraction, b3DBVHRayCastTrampoline, &trampCtx );
		b3TreeStats stats = {0};
		return stats;
	}
	else
	{
		return b3DynamicTree_RayCast( bp->trees + type, input, maskBits, requireAllBits, callback, context );
	}
}

// Gather the sibling pairs with a moved node. This is done serially, it is cache friendly.
static int b3GatherMovedSiblings( const b3DynamicTree* tree, int* pairIndices )
{
	const b3TreeNode* nodes = tree->nodes;
	int nodeEnd = tree->nodeEnd;

	int count = 0;

	// Skip the root.
	for ( int pair = 2; pair < nodeEnd; pair += 2 )
	{
		// Push when either sibling moved.
		if ( ( nodes[pair].flagIndex | nodes[pair + 1].flagIndex ) & B3_MOVED_NODE )
		{
			pairIndices[count++] = pair;
		}
	}

	return count;
}

#define B3_CANDIDATE_BATCH 32

typedef struct b3CandidatePair
{
	int shapeIdA;
	int shapeIdB;
} b3CandidatePair;

typedef struct b3PairContext
{
	b3World* world;
	b3Array( uint64_t ) * pairKeys;
	b3CandidatePair batch[B3_CANDIDATE_BATCH];
	int batchCount;

	// Compound shapes are static only, so only the static cross pass can meet one. Elsewhere
	// this stays false and the batch never reads a shape type.
	bool checkCompounds;
} b3PairContext;

typedef struct b3NodePair
{
	b3TreeNode a;
	b3TreeNode b;
} b3NodePair;

typedef struct b3IndexPair
{
	int a, b;
} b3IndexPair;

static inline void b3PrefetchHash( b3HashSet* set, uint32_t hash )
{
	uint32_t capacity = set->capacity;
	uint32_t index = hash & ( capacity - 1 );
	b3Prefetch( set->items + index );
}

// The shape pair gauntlet. Everything here is a property of the pair, not of a compound child,
// so a compound runs it once for the whole pair.
static bool b3ShouldCreatePair( b3World* world, int shapeIdA, int shapeIdB )
{
	b3Shape* shapeA = b3Array_Get( world->shapes, shapeIdA );
	b3Shape* shapeB = b3Array_Get( world->shapes, shapeIdB );

	int bodyIdA = shapeA->bodyId;
	int bodyIdB = shapeB->bodyId;

	// Are the shapes on the same body?
	if ( bodyIdA == bodyIdB )
	{
		return false;
	}

	// Sensors are handled elsewhere
	if ( shapeA->sensorIndex != B3_NULL_INDEX || shapeB->sensorIndex != B3_NULL_INDEX )
	{
		return false;
	}

	if ( b3ShouldShapesCollide( shapeA->filter, shapeB->filter ) == false )
	{
		return false;
	}

	// Does a joint override collision?
	b3Body* bodyA = b3Array_Get( world->bodies, bodyIdA );
	b3Body* bodyB = b3Array_Get( world->bodies, bodyIdB );
	if ( b3ShouldBodiesCollide( world, bodyA, bodyB ) == false )
	{
		return false;
	}

	// Custom user filter
	if ( ( shapeA->flags & b3_enableCustomFiltering ) || ( shapeB->flags & b3_enableCustomFiltering ) )
	{
		b3CustomFilterFcn* customFilterFcn = world->customFilterFcn;
		if ( customFilterFcn != NULL )
		{
			b3ShapeId idA = { shapeIdA + 1, world->worldId, shapeA->generation };
			b3ShapeId idB = { shapeIdB + 1, world->worldId, shapeB->generation };
			if ( customFilterFcn( idA, idB, world->customFilterContext ) == false )
			{
				return false;
			}
		}
	}

	return true;
}

typedef struct b3CompoundPairContext
{
	b3PairContext* pairContext;
	b3HashSet* pairSet;
	int compoundShapeId;
	int otherShapeId;
} b3CompoundPairContext;

static bool b3CompoundChildCallback( int proxyId, uint64_t userData, void* context )
{
	B3_UNUSED( proxyId );

	b3CompoundPairContext* compoundContext = context;
	int childIndex = (int)userData;

	uint64_t key = b3ShapePairKey( compoundContext->compoundShapeId, compoundContext->otherShapeId, childIndex );
	if ( b3ContainsKey( compoundContext->pairSet, key ) == false )
	{
		b3Array_Push( *compoundContext->pairContext->pairKeys, key );
	}

	return true;
}

// One of the two shapes is a compound, so the pair becomes one pair per overlapping child. The
// child boxes live in the compound frame, so the other shape's box has to be demoted and pulled
// into that frame first.
static void b3EmitCompoundPairs( b3PairContext* context, int compoundShapeId, int otherShapeId )
{
	b3World* world = context->world;

	b3Shape* compoundShape = b3Array_Get( world->shapes, compoundShapeId );
	b3Shape* otherShape = b3Array_Get( world->shapes, otherShapeId );

	int otherProxyKey = otherShape->proxyKey;
	B3_ASSERT( otherProxyKey != B3_NULL_INDEX );
	b3AABB otherAABB =
		b3DynamicTree_GetAABB( world->broadPhase.trees + B3_PROXY_TYPE( otherProxyKey ), B3_PROXY_ID( otherProxyKey ) );

	// Query bounds are float world space, so the demoted transform is the matching float frame
	b3Transform compoundTransform = b3ToRelativeTransform( b3GetBodyTransform( world, compoundShape->bodyId ), b3Pos_zero );
	b3AABB localAABB = b3AABB_Transform( b3InvertTransform( compoundTransform ), otherAABB );

	b3CompoundPairContext compoundContext = {
		.pairContext = context,
		.pairSet = &world->broadPhase.pairSet,
		.compoundShapeId = compoundShapeId,
		.otherShapeId = otherShapeId,
	};

	int startCount = context->pairKeys->count;

	b3DynamicTree_Query( &compoundShape->compound->tree, localAABB, B3_DEFAULT_MASK_BITS, false, b3CompoundChildCallback,
						 &compoundContext );

	if ( context->pairKeys->count > startCount && b3ShouldCreatePair( world, compoundShapeId, otherShapeId ) == false )
	{
		b3Array_Resize( *context->pairKeys, startCount );
	}
}

static void b3FlushCandidatePairs( b3PairContext* context )
{
	b3World* world = context->world;
	b3BroadPhase* bp = &world->broadPhase;

	int count1 = context->batchCount;
	context->batchCount = 0;

	b3CandidatePair plain[B3_CANDIDATE_BATCH];
	int plainCount = 0;

	if ( context->checkCompounds )
	{
		// A compound expands into one pair per child, so its key is not known yet and it cannot
		// ride the batched cull below.
		const b3Shape* shapes = world->shapes.data;
		for ( int i = 0; i < count1; ++i )
		{
			b3CandidatePair candidate = context->batch[i];
			bool compoundA = shapes[candidate.shapeIdA].type == b3_compoundShape;
			bool compoundB = shapes[candidate.shapeIdB].type == b3_compoundShape;

			if ( compoundA )
			{
				// Compound versus compound is not supported
				B3_ASSERT( compoundB == false );
				b3EmitCompoundPairs( context, candidate.shapeIdA, candidate.shapeIdB );
			}
			else if ( compoundB )
			{
				b3EmitCompoundPairs( context, candidate.shapeIdB, candidate.shapeIdA );
			}
			else
			{
				plain[plainCount] = candidate;
				plainCount += 1;
			}
		}
	}
	else
	{
		memcpy( plain, context->batch, count1 * sizeof( b3CandidatePair ) );
		plainCount = count1;
	}

	// Prefetch hash set entries. Less than 1% gain in Box2D but the 3D shape is fatter.
	uint64_t keys[B3_CANDIDATE_BATCH];
	uint32_t hashes[B3_CANDIDATE_BATCH];
	for ( int i = 0; i < plainCount; ++i )
	{
		keys[i] = b3ShapePairKey( plain[i].shapeIdA, plain[i].shapeIdB, 0 );
		hashes[i] = b3KeyHash( keys[i] );
		b3PrefetchHash( &bp->pairSet, hashes[i] );
	}

	// Cull existing pairs.
	b3CandidatePair candidates[B3_CANDIDATE_BATCH];
	int count2 = 0;
	for ( int i = 0; i < plainCount; ++i )
	{
		if ( b3ContainsHashedKey( &bp->pairSet, keys[i], hashes[i] ) == false )
		{
			candidates[count2] = plain[i];
			keys[count2] = keys[i];
			count2 += 1;
		}
	}

	// Prefetch shapes.
	const b3Shape* shapes = world->shapes.data;
	for ( int i = 0; i < count2; ++i )
	{
		b3Prefetch( shapes + candidates[i].shapeIdA );
		b3Prefetch( shapes + candidates[i].shapeIdB );
	}

	// Filter candidates.
	for ( int i = 0; i < count2; ++i )
	{
		if ( b3ShouldCreatePair( world, candidates[i].shapeIdA, candidates[i].shapeIdB ) )
		{
			// The pair passed the gauntlet. A new contact will be created.
			b3Array_Push( *context->pairKeys, keys[i] );
		}
	}
}

B3_FORCE_INLINE void b3AddCandidatePair( int shapeIdA, int shapeIdB, b3PairContext* context )
{
	// Follow shape index order.
	b3CandidatePair* candidate = context->batch + context->batchCount;
	candidate->shapeIdA = b3MinInt( shapeIdA, shapeIdB );
	candidate->shapeIdB = b3MaxInt( shapeIdA, shapeIdB );
	context->batchCount += 1;
	if ( context->batchCount == B3_CANDIDATE_BATCH )
	{
		b3FlushCandidatePairs( context );
	}
}

// Did either move and if so do they overlap?
B3_FORCE_INLINE bool b3TestPair( const b3TreeNode* a, const b3TreeNode* b )
{
	if ( ( ( a->flagIndex | b->flagIndex ) & B3_MOVED_NODE ) == 0 )
	{
		return false;
	}

	return b3OverlapV( &a->aabb, &b->aabb );
}

static void b3CollideProxyAndSubtree( const b3TreeNode* proxy, const b3TreeNode* nodes, int pair, b3PairContext* context )
{
	uint32_t proxyMark = proxy->flagIndex & B3_MOVED_NODE;
	b3AABBV boxv = b3LoadAABBV( &proxy->aabb );
	int shapeId = proxy->shapeIndex;

	int stack[B3_TREE_STACK_SIZE];
	int stackCount = 0;
	stack[stackCount++] = pair;

	while ( stackCount > 0 )
	{
		pair = stack[--stackCount];
		for ( int i = 0; i < 2; ++i )
		{
			const b3TreeNode* node = nodes + pair + i;
			if ( ( ( node->flagIndex | proxyMark ) & B3_MOVED_NODE ) == 0 )
			{
				continue;
			}

			if ( b3OverlapNode( boxv, node ) == false )
			{
				continue;
			}

			if ( b3IsLeaf( node ) )
			{
				b3AddCandidatePair( shapeId, node->shapeIndex, context );
			}
			else
			{
				if ( stackCount < B3_TREE_STACK_SIZE )
				{
					stack[stackCount++] = b3GetLeftChild( node );
				}
				else
				{
					B3_ASSERT( stackCount < B3_TREE_STACK_SIZE );
				}
			}
		}
	}
}

// Helper for b3CollideCrossPairs to avoid code duplication.
B3_FORCE_INLINE void b3VisitPair( const b3TreeNode* arrayA, const b3TreeNode* arrayB, const b3TreeNode* nodeA,
								  const b3TreeNode* nodeB, b3IndexPair* stack, int* stackCount, b3PairContext* context )
{
	if ( b3TestPair( nodeA, nodeB ) == false )
	{
		return;
	}

	bool leafA = b3IsLeaf( nodeA );
	bool leafB = b3IsLeaf( nodeB );
	if ( leafA && leafB )
	{
		b3AddCandidatePair( nodeA->shapeIndex, nodeB->shapeIndex, context );
	}
	else if ( leafA )
	{
		b3CollideProxyAndSubtree( nodeA, arrayB, b3GetLeftChild( nodeB ), context );
	}
	else if ( leafB )
	{
		b3CollideProxyAndSubtree( nodeB, arrayA, b3GetLeftChild( nodeA ), context );
	}
	else
	{
		if ( *stackCount < B3_TREE_STACK_SIZE )
		{
			stack[*stackCount] = B3_LITERAL( b3IndexPair ){ .a = b3GetLeftChild( nodeA ), .b = b3GetLeftChild( nodeB ) };
			*stackCount += 1;
		}
		else
		{
			B3_ASSERT( *stackCount < B3_TREE_STACK_SIZE );
		}
	}
}

// This collides two sub-trees against each other. They can live in the same dynamic tree.
// This can only generate pairs cross sub-tree, but not within a sub-tree. This fact means
// this does not generate duplicate pairs.
// For example consider the full binary tree A (B (D  E) C (F G))
// Colliding children of A (B and C) can give pairs (D,F) (D,G) (E,F) and (E,G).
// Then colliding children of B can give the pair (D,E) and for C (F,G).
// So no duplicates even when used for self-collision.
// Whenever a proxy is moved, the flag is propagated up the hierarchy to the root. So
// self collision gathers all those moved internal nodes and collides their subtrees together.
// See Real-time collision detection section 6.3.2. This is faster than querying every moved
// proxy against the whole tree. Scaling is linear instead of linear * log.
// Many other physics engines do this (Bepu, Rapier, etc). So nothing new here.
static void b3CollideCrossPairs( const b3TreeNode* arrayA, const b3TreeNode* arrayB, const b3TreeNode* subtreeA,
								 const b3TreeNode* subtreeB, b3PairContext* context )
{
	b3IndexPair stack[B3_TREE_STACK_SIZE];
	int stackCount = 0;

	// Seed the stack.
	b3VisitPair( arrayA, arrayB, subtreeA, subtreeB, stack, &stackCount, context );

	while ( stackCount > 0 )
	{
		b3IndexPair pair = stack[--stackCount];
		for ( int i = 0; i < 2; ++i )
		{
			for ( int j = 0; j < 2; ++j )
			{
				b3VisitPair( arrayA, arrayB, arrayA + pair.a + i, arrayB + pair.b + j, stack, &stackCount, context );
			}
		}
	}
}

// This takes moved internal nodes and collides their sub-trees against each other.
static void b3SelfPairsTask( int startIndex, int endIndex, int workerIndex, void* context )
{
	b3TracyCZoneNC( self_pairs, "Self", b3_colorCoral, true );

	b3World* world = context;
	b3BroadPhase* bp = &world->broadPhase;
	const b3DynamicTree* tree = bp->trees + b3_dynamicBody;
	const b3TreeNode* nodes = tree->nodes;
	const int* siblingIndices = bp->movedSiblings;

	b3PairContext pairContext = {
		.world = world,
		.pairKeys = &world->taskContexts.data[workerIndex].pairKeys,
	};

	for ( int i = startIndex; i < endIndex; ++i )
	{
		int nodeIndex = siblingIndices[i];
		b3CollideCrossPairs( nodes, nodes, nodes + nodeIndex, nodes + nodeIndex + 1, &pairContext );
	}

	b3FlushCandidatePairs( &pairContext );

	b3TracyCZoneEnd( self_pairs );
}

#define B3_CROSS_SEED_COUNT 64
_Static_assert( ( B3_CROSS_SEED_COUNT & ( B3_CROSS_SEED_COUNT - 1 ) ) == 0, "must be power of 2" );

// This does a serial cross-tree breadth first search until the queue is full. Then it returns
// the queue pairs as seeds for a parallel search.
static int b3GatherCrossSeeds( const b3DynamicTree* treeA, const b3DynamicTree* treeB, b3NodePair* seeds )
{
	const b3TreeNode* nodesA = treeA->nodes;
	const b3TreeNode* nodesB = treeB->nodes;

	// Breadth-first search from the two roots as one pair. An empty tree has a sentinel root that
	// survives nothing.
	b3NodePair queue[2 * B3_CROSS_SEED_COUNT];
	int mask = 2 * B3_CROSS_SEED_COUNT - 1;
	int head = 0;
	int tail = 0;

	const b3TreeNode* rootA = nodesA + B3_ROOT_NODE;
	const b3TreeNode* rootB = nodesB + B3_ROOT_NODE;
	if ( b3TestPair( rootA, rootB ) )
	{
		queue[tail & mask] = B3_LITERAL( b3NodePair ){ .a = *rootA, .b = *rootB };
		tail += 1;
	}

	int seedCount = 0;
	while ( head < tail && seedCount + ( tail - head ) + 3 < B3_CROSS_SEED_COUNT )
	{
		b3NodePair pair = queue[head & mask];
		head += 1;

		if ( b3IsLeaf( &pair.a ) || b3IsLeaf( &pair.b ) )
		{
			seeds[seedCount++] = pair;
			continue;
		}

		const b3TreeNode* a = nodesA + b3GetLeftChild( &pair.a );
		const b3TreeNode* b = nodesB + b3GetLeftChild( &pair.b );

		// Nodes have two children each, so four combinations.
		for ( int i = 0; i < 2; ++i )
		{
			for ( int j = 0; j < 2; ++j )
			{
				if ( b3TestPair( a + i, b + j ) )
				{
					queue[tail & mask] = B3_LITERAL( b3NodePair ){ a[i], b[j] };
					tail += 1;
				}
			}
		}
	}

	while ( head < tail )
	{
		seeds[seedCount] = queue[head & mask];
		seedCount += 1;
		head += 1;
	}

	return seedCount;
}

typedef struct b3CrossContext
{
	b3World* world;
	const b3NodePair* seeds;
	int staticSeedCount;
	bool checkCompounds;
} b3CrossContext;

static void b3CrossPairsTask( int startIndex, int endIndex, int workerIndex, void* context )
{
	b3TracyCZoneNC( cross_pairs, "Cross", b3_colorCoral, true );

	b3CrossContext* crossContext = context;
	b3World* world = crossContext->world;
	b3BroadPhase* bp = &world->broadPhase;
	const b3TreeNode* staticNodes = bp->trees[b3_staticBody].nodes;
	const b3TreeNode* kinematicNodes = bp->trees[b3_kinematicBody].nodes;
	const b3TreeNode* dynamicNodes = bp->trees[b3_dynamicBody].nodes;

	b3PairContext pairContext = {
		.world = world,
		.pairKeys = &world->taskContexts.data[workerIndex].pairKeys,
	};

	// Static seeds come first, so the two passes are contiguous sub-ranges. The batch is drained
	// between them because only the static pass can meet a compound.
	int staticEnd = b3MinInt( endIndex, crossContext->staticSeedCount );

	pairContext.checkCompounds = crossContext->checkCompounds;
	for ( int i = startIndex; i < staticEnd; ++i )
	{
		b3NodePair seed = crossContext->seeds[i];
		b3CollideCrossPairs( dynamicNodes, staticNodes, &seed.a, &seed.b, &pairContext );
	}
	b3FlushCandidatePairs( &pairContext );

	pairContext.checkCompounds = false;
	for ( int i = b3MaxInt( startIndex, crossContext->staticSeedCount ); i < endIndex; ++i )
	{
		b3NodePair seed = crossContext->seeds[i];
		b3CollideCrossPairs( dynamicNodes, kinematicNodes, &seed.a, &seed.b, &pairContext );
	}
	b3FlushCandidatePairs( &pairContext );

	b3TracyCZoneEnd( cross_pairs );
}

static void b3UpdateTreesTask( void* context )
{
	b3TracyCZoneNC( tree_task, "Rebuild Trees", b3_colorFireBrick, true );

	b3World* world = (b3World*)context;
	// DBVH Integration: Trigger periodic degradation-based rebuild every N frames with amortized budget
	if ( world->broadPhase.useDBVH )
	{
		b3BroadPhase* bp = &world->broadPhase;
		if ( bp->dbvhConfig.enableRebuild )
		{
			int interval = bp->dbvhConfig.enableAdaptiveRebuild ? bp->currentRebuildInterval : bp->dbvhConfig.rebuildInterval;
			if ( interval <= 1 || ( world->stepIndex % (uint64_t)interval ) == 0 )
			{
				int maxRebuilds = 2;
				int maxLeaves = bp->dbvhConfig.maxSubtreeLeaves > 0 ? bp->dbvhConfig.maxSubtreeLeaves : 64;
				int rebuiltCount = dbvh_rebuild_degraded_adaptive( bp->dbvhTree,
				                                                   bp->dbvhConfig.rebuildThreshold,
				                                                   bp->dbvhConfig.degradationMetric,
				                                                   maxRebuilds,
				                                                   maxLeaves );

				if ( bp->dbvhConfig.enableAdaptiveRebuild )
				{
					bp->currentMaxRebuilds = 2;
					if ( rebuiltCount < 2 )
					{
						// Caso menos de 2 ramos sejam reconstruídos, aumenta o intervalo para 60
						bp->currentRebuildInterval = 60;
					}
					else
					{
						bp->currentRebuildInterval = ( bp->dbvhConfig.rebuildInterval > 0 ) ? bp->dbvhConfig.rebuildInterval : 30;
					}
				}
			}
		}
	}
	else
	{
		b3DynamicTree_Rebuild( world->broadPhase.trees + b3_dynamicBody, false );
	}
	b3DynamicTree_Rebuild( world->broadPhase.trees + b3_kinematicBody, false );

	b3TracyCZoneEnd( tree_task );
}

// Task that can be done in parallel with the narrow-phase
// - rebuild the collision tree for dynamic and kinematic bodies to keep their query performance good
static void b3EnqueueTreeUpdate( b3World* world )
{
	if ( world->taskCount < B3_MAX_TASKS )
	{
		world->userTreeTask = world->enqueueTaskFcn( &b3UpdateTreesTask, world, world->userTaskContext, "rebuild tree" );
		world->taskCount += 1;
		world->activeTaskCount += world->userTreeTask == NULL ? 0 : 1;
	}
	else
	{
		world->userTreeTask = NULL;
		b3UpdateTreesTask( world );
	}
}

void b3UpdateBroadPhasePairs( b3World* world )
{
	b3BroadPhase* bp = &world->broadPhase;

	bool needUpdate = b3HasTreeMoved( bp->trees + b3_staticBody );
	needUpdate = needUpdate || b3NeedsRebuild( bp->trees + b3_kinematicBody );
	needUpdate = needUpdate || b3NeedsRebuild( bp->trees + b3_dynamicBody );

	if ( needUpdate == false )
	{
		return;
	}

	b3TracyCZoneNC( update_pairs, "Find Pairs", b3_colorMediumSlateBlue, true );

	b3Stack* alloc = &world->stack;

	for ( int i = 0; i < world->workerCount; ++i )
	{
		b3Array_Clear( world->taskContexts.data[i].pairKeys );
	}

	// Generate pairs by querying the dynamic body tree against itself and against
	// the kinematic and static trees.
	{
		// Get the sibling pairs of the dynamic body tree that have moved.
		const b3DynamicTree* dynamicTree = bp->trees + b3_dynamicBody;
		int pairCapacity = b3MaxInt( dynamicTree->nodeEnd / 2, 1 );
		bp->movedSiblings = b3StackAlloc( alloc, pairCapacity * sizeof( int ), "moved pairs" );
		int dynamicMoveCount = b3GatherMovedSiblings( dynamicTree, bp->movedSiblings );

		// Get seeds for colliding against the static and kinematic trees.
		b3NodePair crossSeeds[2 * B3_CROSS_SEED_COUNT];
		int staticSeedCount = b3GatherCrossSeeds( dynamicTree, bp->trees + b3_staticBody, crossSeeds );
		B3_ASSERT( staticSeedCount <= B3_CROSS_SEED_COUNT );
		int kinematicSeedCount = b3GatherCrossSeeds( dynamicTree, bp->trees + b3_kinematicBody, crossSeeds + staticSeedCount );
		B3_ASSERT( kinematicSeedCount <= B3_CROSS_SEED_COUNT );
		int crossMoveCount = staticSeedCount + kinematicSeedCount;

		// Collide the dynamic body tree against the static and kinematic trees.
		b3CrossContext crossContext = {
			.world = world,
			.seeds = crossSeeds,
			.staticSeedCount = staticSeedCount,
			.checkCompounds = world->compoundShapeCount > 0,
		};
		b3ParallelFor( world, &b3CrossPairsTask, crossMoveCount, 1, &crossContext, "cross pairs" );

		// Collide the dynamic body tree against itself.
		b3ParallelFor( world, &b3SelfPairsTask, dynamicMoveCount, 64, world, "self pairs" );
	}

	b3DynamicTree_ClearMoved( bp->trees + b3_staticBody );

	b3TracyCZoneEnd( update_pairs );

	b3TracyCZoneNC( create_contacts, "Create Contacts", b3_colorCoral, true );

	// Update stale trees.
	b3EnqueueTreeUpdate( world );

	// Pairs arrive in deterministic order but scrambled relative to body and shape order.
	// Sorting them here improves solver performance and makes contact order independent of
	// tree structure.
	int pairCount = 0;
	for ( int i = 0; i < world->workerCount; ++i )
	{
		pairCount += world->taskContexts.data[i].pairKeys.count;
	}

	uint64_t* pairKeys = b3StackAlloc( alloc, b3MaxInt( pairCount, 1 ) * sizeof( uint64_t ), "pair keys" );
	int keyCount = 0;
	for ( int i = 0; i < world->workerCount; ++i )
	{
		const b3Array( uint64_t )* workerKeys = &world->taskContexts.data[i].pairKeys;
		if ( workerKeys->count > 0 )
		{
			memcpy( pairKeys + keyCount, workerKeys->data, workerKeys->count * sizeof( uint64_t ) );
			keyCount += workerKeys->count;
		}
	}

	B3_ASSERT( keyCount == pairCount );

	{
#define LESS( i, j ) ( pairKeys[(int)( i )] < pairKeys[(int)( j )] )
#define SWAP( i, j )                                                                                                             \
	do                                                                                                                           \
	{                                                                                                                            \
		uint64_t tmp_ = pairKeys[(int)( i )];                                                                                    \
		pairKeys[(int)( i )] = pairKeys[(int)( j )];                                                                             \
		pairKeys[(int)( j )] = tmp_;                                                                                             \
	}                                                                                                                            \
	while ( 0 )

		QSORT( pairCount, LESS, SWAP );

#undef LESS
#undef SWAP
	}

	for ( int i = 0; i < keyCount; ++i )
	{
		uint64_t key = pairKeys[i];

		// The traversal is cross subtree and the seeds are disjoint, so a duplicate key means a
		// real bug. Trap it in a validation build, and skip rather than double add to the pair
		// set, which a later destroy would then remove once.
		bool duplicate = i > 0 && key == pairKeys[i - 1];
		B3_VALIDATE( duplicate == false );
		if ( duplicate )
		{
			continue;
		}

		int shapeIdA = (int)( ( key >> ( 64 - B3_SHAPE_POWER ) ) & B3_SHAPE_MASK );
		int shapeIdB = (int)( ( key >> ( 64 - 2 * B3_SHAPE_POWER ) ) & B3_SHAPE_MASK );
		int childIndex = (int)( key & B3_CHILD_MASK );

		b3Shape* shapeA = b3Array_Get( world->shapes, shapeIdA );
		b3Shape* shapeB = b3Array_Get( world->shapes, shapeIdB );

		b3CreateContact( world, shapeA, shapeB, childIndex );
	}

	b3StackFree( alloc, pairKeys );

	b3StackFree( alloc, bp->movedSiblings );
	bp->movedSiblings = NULL;

	b3ValidateSolverSets( world );

	b3TracyCZoneEnd( create_contacts );
}

bool b3BroadPhase_TestOverlap( const b3BroadPhase* bp, int proxyKeyA, int proxyKeyB )
{
	int typeIndexA = B3_PROXY_TYPE( proxyKeyA );
	int proxyIdA = B3_PROXY_ID( proxyKeyA );
	int typeIndexB = B3_PROXY_TYPE( proxyKeyB );
	int proxyIdB = B3_PROXY_ID( proxyKeyB );

	b3AABB aabbA;
	// DBVH Integration: Get proxy AABB from DBVH for dynamic body
	if ( bp->useDBVH && typeIndexA == b3_dynamicBody )
	{
		float arr[6];
		dbvh_get_aabb( bp->dbvhTree, proxyIdA, arr );
		aabbA.lowerBound = (b3Pos){ arr[0], arr[1], arr[2] };
		aabbA.upperBound = (b3Pos){ arr[3], arr[4], arr[5] };
	}
	else
	{
		aabbA = b3DynamicTree_GetAABB( bp->trees + typeIndexA, proxyIdA );
	}

	b3AABB aabbB;
	// DBVH Integration: Get proxy AABB from DBVH for dynamic body
	if ( bp->useDBVH && typeIndexB == b3_dynamicBody )
	{
		float arr[6];
		dbvh_get_aabb( bp->dbvhTree, proxyIdB, arr );
		aabbB.lowerBound = (b3Pos){ arr[0], arr[1], arr[2] };
		aabbB.upperBound = (b3Pos){ arr[3], arr[4], arr[5] };
	}
	else
	{
		aabbB = b3DynamicTree_GetAABB( bp->trees + typeIndexB, proxyIdB );
	}

	return b3AABB_Overlaps( aabbA, aabbB );
}

int b3BroadPhase_GetShapeIndex( b3BroadPhase* bp, int proxyKey )
{
	int typeIndex = B3_PROXY_TYPE( proxyKey );
	int proxyId = B3_PROXY_ID( proxyKey );

	// DBVH Integration: Get user data (shapeIndex) from DBVH for dynamic body
	if ( bp->useDBVH && typeIndex == b3_dynamicBody )
	{
		return (int)dbvh_get_user_data( bp->dbvhTree, proxyId );
	}
	else
	{
		return (int)b3DynamicTree_GetUserData( bp->trees + typeIndex, proxyId );
	}
}

void b3ValidateBroadPhase( const b3BroadPhase* bp )
{
	// DBVH Integration: Validate native dynamic tree only when not using DBVH
	if ( !bp->useDBVH )
	{
		b3DynamicTree_Validate( bp->trees + b3_dynamicBody );
	}
	b3DynamicTree_Validate( bp->trees + b3_kinematicBody );

	// todo validate every shape AABB is contained in tree AABB
}

void b3ValidateNoMoved( const b3BroadPhase* bp )
{
#if B3_ENABLE_VALIDATION == 1
	for ( int j = 0; j < b3_bodyTypeCount; ++j )
	{
		// DBVH Integration: Skip native dynamic tree validation when using DBVH
		if ( bp->useDBVH && j == b3_dynamicBody )
		{
			continue;
		}
		const b3DynamicTree* tree = bp->trees + j;
		b3DynamicTree_ValidateNoMoved( tree );
	}
#else
	B3_UNUSED( bp );
#endif
}

// DBVH Integration: Compute broadphase quality metrics and ground truth ideal comparison
void b3BroadPhase_GetQualityMetrics( const b3BroadPhase* bp, b3BodyType bodyType, bool computeIdeal, float traversalCost, float isectCost, b3BroadPhaseQualityMetrics* outMetrics )
{
	if ( bp == NULL || outMetrics == NULL )
	{
		return;
	}

	memset( outMetrics, 0, sizeof( *outMetrics ) );

	if ( bp->useDBVH && bodyType == b3_dynamicBody )
	{
		dbvh_tree_metrics_t curMetrics;
		dbvh_get_quality_metrics( bp->dbvhTree, &curMetrics, traversalCost, isectCost );
		outMetrics->current.sahCostStandard = curMetrics.sahCostStandard;
		outMetrics->current.sahCostNormalized = curMetrics.sahCostNormalized;
		outMetrics->current.rootArea = curMetrics.rootArea;
		outMetrics->current.treeHeight = curMetrics.treeHeight;
		outMetrics->current.leafCount = curMetrics.leafCount;
		outMetrics->current.nodeCount = curMetrics.nodeCount;

		if ( computeIdeal )
		{
			dbvh_tree_metrics_t idealMetrics;
			dbvh_get_ideal_quality_metrics( bp->dbvhTree, &idealMetrics, traversalCost, isectCost );
			outMetrics->ideal.sahCostStandard = idealMetrics.sahCostStandard;
			outMetrics->ideal.sahCostNormalized = idealMetrics.sahCostNormalized;
			outMetrics->ideal.rootArea = idealMetrics.rootArea;
			outMetrics->ideal.treeHeight = idealMetrics.treeHeight;
			outMetrics->ideal.leafCount = idealMetrics.leafCount;
			outMetrics->ideal.nodeCount = idealMetrics.nodeCount;

			if ( idealMetrics.sahCostStandard > 0.0f )
			{
				outMetrics->qualityRatioStandard = curMetrics.sahCostStandard / idealMetrics.sahCostStandard;
			}
			if ( idealMetrics.sahCostNormalized > 0.0f )
			{
				outMetrics->qualityRatioNormalized = curMetrics.sahCostNormalized / idealMetrics.sahCostNormalized;
			}
		}
	}
	else
	{
		const b3DynamicTree* tree = bp->trees + bodyType;
		outMetrics->current = b3DynamicTree_ComputeQualityMetrics( tree, traversalCost, isectCost );

		if ( computeIdeal && outMetrics->current.leafCount > 0 )
		{
			int leafCount = outMetrics->current.leafCount;
			float* aabbArray = (float*)malloc( leafCount * 6 * sizeof( float ) );
			if ( aabbArray != NULL )
			{
				b3DynamicTree_GetLeafAABBs( tree, aabbArray, leafCount );
				dbvh_tree_metrics_t idealMetrics;
				dbvh_compute_ideal_from_aabbs( aabbArray, leafCount, &idealMetrics, traversalCost, isectCost );
				free( aabbArray );

				outMetrics->ideal.sahCostStandard = idealMetrics.sahCostStandard;
				outMetrics->ideal.sahCostNormalized = idealMetrics.sahCostNormalized;
				outMetrics->ideal.rootArea = idealMetrics.rootArea;
				outMetrics->ideal.treeHeight = idealMetrics.treeHeight;
				outMetrics->ideal.leafCount = idealMetrics.leafCount;
				outMetrics->ideal.nodeCount = idealMetrics.nodeCount;

				if ( idealMetrics.sahCostStandard > 0.0f )
				{
					outMetrics->qualityRatioStandard = outMetrics->current.sahCostStandard / idealMetrics.sahCostStandard;
				}
				if ( idealMetrics.sahCostNormalized > 0.0f )
				{
					outMetrics->qualityRatioNormalized = outMetrics->current.sahCostNormalized / idealMetrics.sahCostNormalized;
				}
			}
		}
	}
}
