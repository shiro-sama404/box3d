#include "sdbvh_c_api.h"

#include "aabb.h"
#include "sdbvh.hpp"
#include "vec3.h"

#include <cstring>

extern "C"
{

sdbvh_tree_t* sdbvh_create( size_t initialCapacity )
{
	return reinterpret_cast<sdbvh_tree_t*>( new sdbvh::SDBVH<int32_t>( initialCapacity ) );
}

void sdbvh_destroy( sdbvh_tree_t* tree )
{
	delete reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
}

int32_t sdbvh_insert_with_category( sdbvh_tree_t* tree, const float aabb[6], int32_t userData, uint64_t categoryBits )
{
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	return static_cast<int32_t>( bvh->insert( sdbvh::AABB::fromArray( aabb ), userData, categoryBits ) );
}

void sdbvh_remove( sdbvh_tree_t* tree, int32_t leafIndex )
{
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	bvh->remove( static_cast<size_t>( leafIndex ) );
}

int32_t sdbvh_move( sdbvh_tree_t* tree, int32_t leafIndex, const float aabb[6], const float velocity[3], float epsilon )
{
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	sdbvh::Vec3 vel( velocity[0], velocity[1], velocity[2] );
	return static_cast<int32_t>(
		bvh->moveObject( static_cast<size_t>( leafIndex ), *reinterpret_cast<const sdbvh::AABB*>( aabb ), vel, epsilon ) );
}

void sdbvh_enlarge_proxy( sdbvh_tree_t* tree, int32_t proxyId, const float aabb[6] )
{
	if ( !tree )
		return;
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	bvh->enlargeProxy( static_cast<size_t>( proxyId ), *reinterpret_cast<const sdbvh::AABB*>( aabb ) );
}

int32_t sdbvh_get_user_data( sdbvh_tree_t* tree, int32_t leafIndex )
{
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	return bvh->getNode( static_cast<size_t>( leafIndex ) ).userData;
}

void sdbvh_get_aabb( sdbvh_tree_t* tree, int32_t leafIndex, float aabb[6] )
{
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	bvh->getNode( static_cast<size_t>( leafIndex ) ).aabb.toArray( aabb );
}

void sdbvh_query_pairs( sdbvh_tree_t* tree, sdbvh_pairs_callback_t callback, void* context )
{
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	bvh->queryPairs( [callback, context, bvh]( size_t leafA, size_t leafB ) {
		int32_t shapeIdA = bvh->getNode( leafA ).userData;
		int32_t shapeIdB = bvh->getNode( leafB ).userData;
		callback( shapeIdA, shapeIdB, context );
	} );
}

void sdbvh_query_pairs_batched( sdbvh_tree_t* tree, sdbvh_pairs_batch_callback_t callback, void* context )
{
	if ( !tree )
		return;
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );

	constexpr int BATCH_CAPACITY = 32;
	sdbvh_pair_t buffer[BATCH_CAPACITY];
	int count = 0;

	bvh->queryPairs( [&]( size_t leafA, size_t leafB ) {
		int32_t idA = bvh->getNode( leafA ).userData;
		int32_t idB = bvh->getNode( leafB ).userData;
		if ( idA == idB )
			return;

		if ( idA > idB )
			std::swap( idA, idB );

		buffer[count].shapeIdA = idA;
		buffer[count].shapeIdB = idB;
		count++;

		if ( count == BATCH_CAPACITY )
		{
			callback( buffer, count, context );
			count = 0;
		}
	} );

	if ( count > 0 )
	{
		callback( buffer, count, context );
	}
}

int32_t sdbvh_gather_seeds( sdbvh_tree_t* tree, sdbvh_seed_t* seeds, int32_t maxSeeds )
{
	if ( !tree || !seeds || maxSeeds <= 0 )
		return 0;
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );

	std::vector<sdbvh::NodeIndex> outA( maxSeeds );
	std::vector<sdbvh::NodeIndex> outB( maxSeeds );
	int seedCount = bvh->gatherSubtreePairs( outA.data(), outB.data(), maxSeeds );

	for ( int i = 0; i < seedCount; ++i )
	{
		seeds[i].a = static_cast<int32_t>( outA[i] );
		seeds[i].b = static_cast<int32_t>( outB[i] );
	}
	return seedCount;
}

void sdbvh_query_seed_batched( sdbvh_tree_t* tree, const sdbvh_seed_t* seed, sdbvh_pairs_batch_callback_t callback,
							   void* context )
{
	if ( !tree || !seed )
		return;
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );

	constexpr int BATCH_CAPACITY = 32;
	sdbvh_pair_t buffer[BATCH_CAPACITY];
	int count = 0;

	bvh->queryPairs( static_cast<sdbvh::NodeIndex>( seed->a ), static_cast<sdbvh::NodeIndex>( seed->b ),
					 [&]( size_t leafA, size_t leafB ) {
						 int32_t idA = bvh->getNode( leafA ).userData;
						 int32_t idB = bvh->getNode( leafB ).userData;
						 if ( idA == idB )
							 return;

						 if ( idA > idB )
							 std::swap( idA, idB );

						 buffer[count].shapeIdA = idA;
						 buffer[count].shapeIdB = idB;
						 count++;

						 if ( count == BATCH_CAPACITY )
						 {
							 callback( buffer, count, context );
							 count = 0;
						 }
					 } );

	if ( count > 0 )
	{
		callback( buffer, count, context );
	}
}

void sdbvh_query_aabb( sdbvh_tree_t* tree, const float aabb[6], sdbvh_query_aabb_callback_t callback, void* context )
{
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	sdbvh::AABB box = sdbvh::AABB::fromArray( aabb );
	bvh->query( box, [callback, context]( size_t leafIndex, int32_t userData ) -> bool {
		return callback( static_cast<int32_t>( leafIndex ), userData, context );
	} );
}

void sdbvh_query_aabb_mask( sdbvh_tree_t* tree, const float aabb[6], uint64_t maskBits, sdbvh_query_aabb_callback_t callback,
							void* context )
{
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	sdbvh::AABB box = sdbvh::AABB::fromArray( aabb );
	bvh->query(
		box,
		[callback, context]( size_t leafIndex, int32_t userData ) -> bool {
			return callback( static_cast<int32_t>( leafIndex ), userData, context );
		},
		maskBits );
}

void sdbvh_query_aabb_mask_moved( sdbvh_tree_t* tree, const float aabb[6], uint64_t maskBits,
								  sdbvh_query_aabb_callback_t callback, void* context )
{
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	sdbvh::AABB box = sdbvh::AABB::fromArray( aabb );
	bvh->queryMaskMoved(
		box,
		[callback, context]( size_t leafIndex, int32_t userData ) -> bool {
			return callback( static_cast<int32_t>( leafIndex ), userData, context );
		},
		maskBits );
}

void sdbvh_clear_moved( sdbvh_tree_t* tree )
{
	if ( !tree )
		return;
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	bvh->clearMoved();
}

void sdbvh_mark_moved( sdbvh_tree_t* tree, int32_t proxyId )
{
	if ( !tree )
		return;
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	bvh->markProxyMoved( static_cast<size_t>( proxyId ) );
}

void sdbvh_ray_cast( sdbvh_tree_t* tree, const float translation[3], const float p1[3], float maxFraction,
					 sdbvh_ray_cast_callback_t callback, void* context )
{
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	sdbvh::Vec3 trans = { translation[0], translation[1], translation[2] };
	sdbvh::Vec3 p1_vec = { p1[0], p1[1], p1[2] };
	bvh->rayCast( trans, p1_vec, maxFraction, [callback, context]( size_t leafIndex, int32_t userData ) -> float {
		return callback( static_cast<int32_t>( leafIndex ), userData, context );
	} );
}

void sdbvh_set_config( sdbvh_tree_t* tree, const sdbvh_config_t* config )
{
	if ( !tree || !config )
		return;
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	sdbvh::SDBVHConfig cfg;
	cfg.enableRebuild = config->enableRebuild;
	cfg.enableFattening = config->enableFattening;
	cfg.enablePredictive = config->enablePredictive;
	cfg.enableRotations = config->enableRotations;
	cfg.enableAdaptiveRebuild = config->enableAdaptiveRebuild;
	cfg.maxSubtreeLeaves = ( config->maxSubtreeLeaves > 0 ) ? config->maxSubtreeLeaves : 64;
	cfg.metric = static_cast<sdbvh::DegradationMetric>( config->degradationMetric );
	cfg.partitionAlgorithm = static_cast<sdbvh::PartitionAlgorithm>( config->partitionAlgorithm );
	cfg.areaRatioThreshold = ( config->areaRatioThreshold > 0.0f ) ? config->areaRatioThreshold : 1.8f;
	cfg.subtreeSAHThreshold = ( config->subtreeSAHThreshold > 0.0f ) ? config->subtreeSAHThreshold : 1.8f;
	cfg.rebuildInterval = ( config->rebuildInterval > 0 ) ? config->rebuildInterval : 30;
	cfg.maxRebuildsPerFrame = ( config->maxRebuildsPerFrame > 0 ) ? config->maxRebuildsPerFrame : 2;
	bvh->setConfig( cfg );
}

void sdbvh_rebuild( sdbvh_tree_t* tree )
{
	if ( !tree )
		return;
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	bvh->rebuild();
}

int32_t sdbvh_rebuild_degraded_adaptive( sdbvh_tree_t* tree, float threshold, sdbvh_degradation_metric_t metric,
										 int32_t maxRebuilds, int32_t maxSubtreeLeaves )
{
	if ( !tree )
		return 0;
	sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<sdbvh::SDBVH<int32_t>*>( tree );
	return static_cast<int32_t>(
		bvh->rebuildDegraded( threshold, static_cast<sdbvh::DegradationMetric>( metric ), maxRebuilds, maxSubtreeLeaves ) );
}

int32_t sdbvh_get_height( const sdbvh_tree_t* tree )
{
	if ( !tree )
		return 0;
	const sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<const sdbvh::SDBVH<int32_t>*>( tree );
	return static_cast<int32_t>( bvh->getHeight() );
}

float sdbvh_get_degradation_alpha( const sdbvh_tree_t* tree )
{
	if ( !tree )
		return 0.0f;
	const sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<const sdbvh::SDBVH<int32_t>*>( tree );
	return bvh->getDegradationAlpha();
}

float sdbvh_get_total_tree_area( const sdbvh_tree_t* tree )
{
	if ( !tree )
		return 0.0f;
	const sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<const sdbvh::SDBVH<int32_t>*>( tree );
	return bvh->getTotalTreeArea();
}

void sdbvh_get_root_bounds( const sdbvh_tree_t* tree, float aabb[6] )
{
	if ( !tree )
	{
		for ( int i = 0; i < 6; ++i )
			aabb[i] = 0.0f;
		return;
	}
	const sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<const sdbvh::SDBVH<int32_t>*>( tree );
	bvh->getRootBounds().toArray( aabb );
}

void sdbvh_get_quality_metrics( const sdbvh_tree_t* tree, sdbvh_tree_metrics_t* metrics, float traversalCost, float isectCost )
{
	if ( !tree || !metrics )
		return;
	const sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<const sdbvh::SDBVH<int32_t>*>( tree );
	auto qm = bvh->computeQualityMetrics( traversalCost, isectCost );
	metrics->sahCostStandard = qm.sahCostStandard;
	metrics->sahCostNormalized = qm.sahCostNormalized;
	metrics->rootArea = qm.rootArea;
	metrics->treeHeight = qm.treeHeight;
	metrics->leafCount = qm.leafCount;
	metrics->nodeCount = qm.nodeCount;
}

void sdbvh_get_ideal_quality_metrics( const sdbvh_tree_t* tree, sdbvh_tree_metrics_t* idealMetrics, float traversalCost,
									  float isectCost )
{
	if ( !tree || !idealMetrics )
		return;
	const sdbvh::SDBVH<int32_t>* bvh = reinterpret_cast<const sdbvh::SDBVH<int32_t>*>( tree );
	auto qm = bvh->computeIdealQualityMetrics( traversalCost, isectCost );
	idealMetrics->sahCostStandard = qm.sahCostStandard;
	idealMetrics->sahCostNormalized = qm.sahCostNormalized;
	idealMetrics->rootArea = qm.rootArea;
	idealMetrics->treeHeight = qm.treeHeight;
	idealMetrics->leafCount = qm.leafCount;
	idealMetrics->nodeCount = qm.nodeCount;
}

void sdbvh_compute_ideal_from_aabbs( const float* aabbArray, int32_t leafCount, sdbvh_tree_metrics_t* idealMetrics,
									 float traversalCost, float isectCost )
{
	if ( !aabbArray || leafCount <= 0 || !idealMetrics )
		return;
	std::vector<sdbvh::AABB> leafAABBs;
	leafAABBs.reserve( static_cast<size_t>( leafCount ) );
	for ( int32_t i = 0; i < leafCount; ++i )
	{
		leafAABBs.push_back( sdbvh::AABB::fromArray( aabbArray + i * 6 ) );
	}
	auto qm = sdbvh::SDBVH<int32_t>::computeIdealFromAABBs( leafAABBs, traversalCost, isectCost );
	idealMetrics->sahCostStandard = qm.sahCostStandard;
	idealMetrics->sahCostNormalized = qm.sahCostNormalized;
	idealMetrics->rootArea = qm.rootArea;
	idealMetrics->treeHeight = qm.treeHeight;
	idealMetrics->leafCount = qm.leafCount;
	idealMetrics->nodeCount = qm.nodeCount;
}
}
