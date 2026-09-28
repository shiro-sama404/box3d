// SPDX-FileCopyrightText: 2025 Erin Catto
// SPDX-License-Identifier: MIT

#if defined( _MSC_VER ) && !defined( _CRT_SECURE_NO_WARNINGS )
#define _CRT_SECURE_NO_WARNINGS
#endif

#include "benchmarks.h"
#include "utils.h"

#include "box3d/box3d.h"
#include "box3d/constants.h"
#include "box3d/math_functions.h"

// DBVH Integration: Include DBVH C API
#include "../dbvh/dbvh_c_api.h"

#include <assert.h>
#include <ctype.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <direct.h>
#define CREATE_DIR( d ) _mkdir( d )
#else
#include <sys/stat.h>
#define CREATE_DIR( d ) mkdir( d, 0755 )
#endif

#ifdef TRACY_ENABLE
#include <tracy/TracyC.h>
#endif

#define ARRAY_COUNT( A ) (int)( sizeof( A ) / sizeof( A[0] ) )
#define MAYBE_UNUSED( x ) ( (void)( x ) )

typedef void CapacityFcn( b3Capacity* capacity );
typedef void CreateFcn( b3WorldId worldId );
typedef void DestroyFcn( void );
typedef void StepFcn( b3WorldId worldId, int stepCount );

typedef struct Benchmark
{
	const char* name;
	CapacityFcn* capacityFcn;
	CreateFcn* createFcn;
	DestroyFcn* destroyFcn;
	StepFcn* stepFcn;
	int totalStepCount;
} Benchmark;

// DBVH Integration: Per-frame metrics record structure
typedef struct StepRecord
{
	int frame;
	float stepTime;
	float pairsTime;
	float collideTime;
	float solveTime;
	int contactCount;
	int treeHeight;
	int leafCount;
	int nodeCount;
	float sahStandard;
	float sahNormalized;
	float idealSahStandard;
	float idealSahNormalized;
	int idealTreeHeight;
	float qualityRatioStandard;
	float qualityRatioNormalized;
} StepRecord;

static void MinProfile( b3Profile* p1, const b3Profile* p2 )
{
	p1->step = b3MinFloat( p1->step, p2->step );
	p1->pairs = b3MinFloat( p1->pairs, p2->pairs );
	p1->collide = b3MinFloat( p1->collide, p2->collide );
	p1->solve = b3MinFloat( p1->solve, p2->solve );
	p1->constraints = b3MinFloat( p1->constraints, p2->constraints );
	p1->transforms = b3MinFloat( p1->transforms, p2->transforms );
	p1->refit = b3MinFloat( p1->refit, p2->refit );
	p1->sleepIslands = b3MinFloat( p1->sleepIslands, p2->sleepIslands );
}

// Match a name=value option in either its short or long spelling. Returns the value or NULL.
static const char* MatchValue( const char* arg, const char* shortName, const char* longName )
{
	size_t n = strlen( shortName );
	if ( strncmp( arg, shortName, n ) == 0 )
	{
		return arg + n;
	}
	n = strlen( longName );
	if ( strncmp( arg, longName, n ) == 0 )
	{
		return arg + n;
	}
	return NULL;
}

// Distinguish a numeric benchmark index from a name. Empty string is not numeric.
static bool IsAllDigits( const char* s )
{
	if ( *s == 0 )
	{
		return false;
	}
	for ( ; *s != 0; ++s )
	{
		if ( isdigit( (unsigned char)*s ) == 0 )
		{
			return false;
		}
	}
	return true;
}

static bool EqualsIgnoreCase( const char* a, const char* b )
{
	while ( *a != 0 && *b != 0 )
	{
		if ( tolower( (unsigned char)*a ) != tolower( (unsigned char)*b ) )
		{
			return false;
		}
		++a;
		++b;
	}
	return *a == *b;
}

static int FindBenchmark( const Benchmark* benchmarks, int count, const char* name )
{
	for ( int i = 0; i < count; ++i )
	{
		if ( EqualsIgnoreCase( benchmarks[i].name, name ) )
		{
			return i;
		}
	}
	return -1;
}

static void PrintBenchmarks( const Benchmark* benchmarks, int count )
{
	printf( "Registered benchmarks:\n" );
	for ( int i = 0; i < count; ++i )
	{
		printf( "  %2d  %s\n", i, benchmarks[i].name );
	}
}

// Box3D benchmark application. On Windows it is important to use affinity avoid cross CCD
// usage or efficiency cores. Also on Windows create a power plan with Processor power management
// Min/Max of 99%. This prevents boosting and makes the benchmarks more repeatable.
// Affinity [0x01 0x02 0x04 0x08 0x10 0x20 0x40 0x80]

// Run all benchmarks with 1 to 8 threads.
// start /affinity 0x5555 .\build\bin\Release\benchmark.exe -t=8

// Run all benchmarks with 4 workers only.
// start /affinity 0x5555 .\build\bin\Release\benchmark.exe -t=4 -w=4

// List the registered benchmarks.
// .\build\bin\Release\benchmark.exe -l

// Run a single benchmark by name with 4 workers.
// start /affinity 0x5555 .\build\bin\Release\benchmark.exe -t=4 -w=4 --benchmark=many_pyramids -r=5

// Run benchmark 3 with 4 workers and repeat 20 times. Record the step times.
// start /affinity 0x5555 .\build\bin\Release\benchmark.exe -t=4 -w=4 -b=3 -r=20 -s

// Run benchmark 3 with 4 workers and run once. Disable continuous collision. Record the step times.
// start /affinity 0x5555 .\build\bin\Release\benchmark.exe -t=4 -w=4 -b=3 -r=1 -nc -s

int main( int argc, char** argv )
{
#ifdef TRACY_ENABLE
	___tracy_startup_profiler();
#endif

	Benchmark benchmarks[] = {
		{ "convex_pile", GetConvexPileCapacity, CreateConvexPile, NULL, NULL, 500 },
		{ "joint_grid", NULL, CreateJointGrid, NULL, NULL, 100 },
		{ "junkyard", GetJunkyardCapacity, CreateJunkyard, NULL, StepJunkyard, 500 },
		{ "large_pyramid", NULL, CreateLargePyramid, NULL, NULL, 200 },
		{ "large_world", GetLargeWorldCapacity, CreateLargeWorld, NULL, StepLargeWorld, 500 },
		{ "many_pyramids", NULL, CreateManyPyramids, NULL, NULL, 100 },
		{ "rain", GetRainCapacity, CreateRain, DestroyRain, StepRain, 400 },
		{ "sleep", GetSleepCapacity, CreateSleep, NULL, StepSleep, 300 },
		{ "spinner", GetSpinnerCapacity, CreateSpinner, DestroySpinner, NULL, 800 },
		{ "trees100", NULL, CreateTrees100, DestroyTrees, NULL, 500 },
		{ "trees50", NULL, CreateTrees50, DestroyTrees, NULL, 500 },
		{ "trees25", NULL, CreateTrees25, DestroyTrees, NULL, 500 },
		{ "washer", GetWasherCapacity, CreateWasher, NULL, NULL, 1000 },
		//{ "smash", CreateSmash, NULL, 300 },
		//{ "tumbler", CreateTumbler, NULL, 750 },
	};

	int benchmarkCount = ARRAY_COUNT( benchmarks );

	int maxSteps = benchmarks[0].totalStepCount;
	for ( int i = 1; i < benchmarkCount; ++i )
	{
		maxSteps = b3MaxInt( maxSteps, benchmarks[i].totalStepCount );
	}

	b3Profile maxProfile = {
		.step = FLT_MAX,
		.pairs = FLT_MAX,
		.collide = FLT_MAX,
		.solve = FLT_MAX,
		.solverSetup = FLT_MAX,
		.constraints = FLT_MAX,
		.prepareConstraints = FLT_MAX,
		.integrateVelocities = FLT_MAX,
		.warmStart = FLT_MAX,
		.solveImpulses = FLT_MAX,
		.integratePositions = FLT_MAX,
		.relaxImpulses = FLT_MAX,
		.storeImpulses = FLT_MAX,
		.splitIslands = FLT_MAX,
		.transforms = FLT_MAX,
		.hitEvents = FLT_MAX,
		.refit = FLT_MAX,
		.bullets = FLT_MAX,
		.sleepIslands = FLT_MAX,
	};

	int maxThreadCount = GetNumberOfCores();
	int runCount = 4;
	int singleBenchmark = -1;
	int singleWorkerCount = -1;
	int overrideStepCount = -1;
	int overrideActorCount = -1;
	bool enableContinuous = true;
	bool recordStepTimes = false;
	bool exportCsv = false;
	const char* customCsvFile = NULL;

	// DBVH Integration: CLI option variables
	bool useDBVH = false;
	bool dbvhEnableRebuild = true;
	bool dbvhEnableFattening = true;
	bool dbvhEnablePredictive = false;
	bool dbvhEnableRotations = false;
	int dbvhMetric = 0; // 0: AreaRatio, 1: SubtreeSAH
	float dbvhThreshold = 1.80f;
	int dbvhInterval = 30;
	int dbvhBudget = 2;
	bool dbvhEnableAdaptive = true;
	int dbvhMaxSubtreeLeaves = 64;
	bool customThresholdSet = false;
	bool groundTruthMode = false;

	assert( maxThreadCount <= B3_MAX_WORKERS );

	for ( int i = 1; i < argc; ++i )
	{
		const char* arg = argv[i];
		const char* value;
		if ( ( value = MatchValue( arg, "-t=", "--threads=" ) ) != NULL )
		{
			int threadCount = atoi( value );
			maxThreadCount = b3ClampInt( threadCount, 1, maxThreadCount );
		}
		else if ( ( strcmp( arg, "-t" ) == 0 || strcmp( arg, "--threads" ) == 0 ) && i + 1 < argc )
		{
			int threadCount = atoi( argv[++i] );
			maxThreadCount = b3ClampInt( threadCount, 1, maxThreadCount );
		}
		else if ( ( value = MatchValue( arg, "-b=", "--benchmark=" ) ) != NULL )
		{
			if ( IsAllDigits( value ) )
			{
				singleBenchmark = b3ClampInt( atoi( value ), 0, benchmarkCount - 1 );
			}
			else
			{
				singleBenchmark = FindBenchmark( benchmarks, benchmarkCount, value );
				if ( singleBenchmark == -1 )
				{
					printf( "No benchmark named \"%s\"\n", value );
					PrintBenchmarks( benchmarks, benchmarkCount );
					exit( 1 );
				}
			}
		}
		else if ( ( strcmp( arg, "-b" ) == 0 || strcmp( arg, "--benchmark" ) == 0 ) && i + 1 < argc )
		{
			const char* nextArg = argv[++i];
			if ( IsAllDigits( nextArg ) )
			{
				singleBenchmark = b3ClampInt( atoi( nextArg ), 0, benchmarkCount - 1 );
			}
			else
			{
				singleBenchmark = FindBenchmark( benchmarks, benchmarkCount, nextArg );
				if ( singleBenchmark == -1 )
				{
					printf( "No benchmark named \"%s\"\n", nextArg );
					PrintBenchmarks( benchmarks, benchmarkCount );
					exit( 1 );
				}
			}
		}
		else if ( ( value = MatchValue( arg, "-w=", "--workers=" ) ) != NULL )
		{
			singleWorkerCount = atoi( value );
		}
		else if ( ( strcmp( arg, "-w" ) == 0 || strcmp( arg, "--workers" ) == 0 ) && i + 1 < argc )
		{
			singleWorkerCount = atoi( argv[++i] );
		}
		else if ( ( value = MatchValue( arg, "-r=", "--repeats=" ) ) != NULL )
		{
			runCount = b3ClampInt( atoi( value ), 1, 1000 );
		}
		else if ( ( strcmp( arg, "-r" ) == 0 || strcmp( arg, "--repeats" ) == 0 ) && i + 1 < argc )
		{
			runCount = b3ClampInt( atoi( argv[++i] ), 1, 1000 );
		}
		else if ( ( value = MatchValue( arg, "--steps=", "--steps=" ) ) != NULL )
		{
			overrideStepCount = atoi( value );
			if ( overrideStepCount > maxSteps )
			{
				maxSteps = overrideStepCount;
			}
		}
		else if ( ( strcmp( arg, "--steps" ) == 0 || strcmp( arg, "-steps" ) == 0 ) && i + 1 < argc )
		{
			overrideStepCount = atoi( argv[++i] );
			if ( overrideStepCount > maxSteps )
			{
				maxSteps = overrideStepCount;
			}
		}
		else if ( ( value = MatchValue( arg, "-a=", "--actors=" ) ) != NULL )
		{
			overrideActorCount = atoi( value );
		}
		else if ( ( strcmp( arg, "-a" ) == 0 || strcmp( arg, "--actors" ) == 0 ) && i + 1 < argc )
		{
			overrideActorCount = atoi( argv[++i] );
		}
		else if ( ( value = MatchValue( arg, "-bp=", "--broadphase=" ) ) != NULL )
		{
			if ( EqualsIgnoreCase( value, "dbvh" ) )
			{
				useDBVH = true;
			}
			else
			{
				useDBVH = false;
			}
		}
		else if ( ( strcmp( arg, "-bp" ) == 0 || strcmp( arg, "--broadphase" ) == 0 ) && i + 1 < argc )
		{
			const char* nextArg = argv[++i];
			useDBVH = EqualsIgnoreCase( nextArg, "dbvh" );
		}
		else if ( ( value = MatchValue( arg, "-m=", "--metric=" ) ) != NULL )
		{
			if ( EqualsIgnoreCase( value, "subtree_sah" ) || EqualsIgnoreCase( value, "sah" ) || strcmp( value, "1" ) == 0 )
			{
				dbvhMetric = 1;
			}
			else
			{
				dbvhMetric = 0;
			}
		}
		else if ( ( strcmp( arg, "-m" ) == 0 || strcmp( arg, "--metric" ) == 0 ) && i + 1 < argc )
		{
			const char* nextArg = argv[++i];
			dbvhMetric = ( EqualsIgnoreCase( nextArg, "subtree_sah" ) || EqualsIgnoreCase( nextArg, "sah" ) || strcmp( nextArg, "1" ) == 0 ) ? 1 : 0;
		}
		else if ( ( value = MatchValue( arg, "-th=", "--threshold=" ) ) != NULL )
		{
			dbvhThreshold = (float)atof( value );
			customThresholdSet = true;
		}
		else if ( ( strcmp( arg, "-th" ) == 0 || strcmp( arg, "--threshold" ) == 0 ) && i + 1 < argc )
		{
			dbvhThreshold = (float)atof( argv[++i] );
			customThresholdSet = true;
		}
		else if ( ( value = MatchValue( arg, "-ri=", "--rebuild-interval=" ) ) != NULL )
		{
			dbvhInterval = b3ClampInt( atoi( value ), 1, 10000 );
		}
		else if ( ( strcmp( arg, "-ri" ) == 0 || strcmp( arg, "--rebuild-interval" ) == 0 ) && i + 1 < argc )
		{
			dbvhInterval = b3ClampInt( atoi( argv[++i] ), 1, 10000 );
		}
		else if ( ( value = MatchValue( arg, "-rb=", "--rebuild-budget=" ) ) != NULL )
		{
			dbvhBudget = b3ClampInt( atoi( value ), 1, 1000 );
		}
		else if ( ( strcmp( arg, "-rb" ) == 0 || strcmp( arg, "--rebuild-budget" ) == 0 ) && i + 1 < argc )
		{
			dbvhBudget = b3ClampInt( atoi( argv[++i] ), 1, 1000 );
		}
		else if ( ( value = MatchValue( arg, "--rebuild=", "--rebuild=" ) ) != NULL )
		{
			dbvhEnableRebuild = ( EqualsIgnoreCase( value, "on" ) || strcmp( value, "1" ) == 0 || EqualsIgnoreCase( value, "true" ) );
		}
		else if ( ( strcmp( arg, "--rebuild" ) == 0 || strcmp( arg, "-rebuild" ) == 0 ) && i + 1 < argc )
		{
			const char* nextArg = argv[++i];
			dbvhEnableRebuild = ( EqualsIgnoreCase( nextArg, "on" ) || strcmp( nextArg, "1" ) == 0 || EqualsIgnoreCase( nextArg, "true" ) );
		}
		else if ( ( value = MatchValue( arg, "--fattening=", "--fattening=" ) ) != NULL )
		{
			dbvhEnableFattening = ( EqualsIgnoreCase( value, "on" ) || strcmp( value, "1" ) == 0 || EqualsIgnoreCase( value, "true" ) );
		}
		else if ( ( strcmp( arg, "--fattening" ) == 0 || strcmp( arg, "-fattening" ) == 0 ) && i + 1 < argc )
		{
			const char* nextArg = argv[++i];
			dbvhEnableFattening = ( EqualsIgnoreCase( nextArg, "on" ) || strcmp( nextArg, "1" ) == 0 || EqualsIgnoreCase( nextArg, "true" ) );
		}
		else if ( ( value = MatchValue( arg, "--predictive=", "--predictive=" ) ) != NULL )
		{
			dbvhEnablePredictive = ( EqualsIgnoreCase( value, "on" ) || strcmp( value, "1" ) == 0 || EqualsIgnoreCase( value, "true" ) );
		}
		else if ( ( strcmp( arg, "--predictive" ) == 0 || strcmp( arg, "-predictive" ) == 0 ) && i + 1 < argc )
		{
			const char* nextArg = argv[++i];
			dbvhEnablePredictive = ( EqualsIgnoreCase( nextArg, "on" ) || strcmp( nextArg, "1" ) == 0 || EqualsIgnoreCase( nextArg, "true" ) );
		}
		else if ( ( value = MatchValue( arg, "--rotations=", "--rotations=" ) ) != NULL )
		{
			dbvhEnableRotations = ( EqualsIgnoreCase( value, "on" ) || strcmp( value, "1" ) == 0 || EqualsIgnoreCase( value, "true" ) );
		}
		else if ( ( strcmp( arg, "--rotations" ) == 0 || strcmp( arg, "-rotations" ) == 0 ) && i + 1 < argc )
		{
			const char* nextArg = argv[++i];
			dbvhEnableRotations = ( EqualsIgnoreCase( nextArg, "on" ) || strcmp( nextArg, "1" ) == 0 || EqualsIgnoreCase( nextArg, "true" ) );
		}
		else if ( ( value = MatchValue( arg, "--adaptive=", "--adaptive-rebuild=" ) ) != NULL )
		{
			dbvhEnableAdaptive = ( EqualsIgnoreCase( value, "on" ) || strcmp( value, "1" ) == 0 || EqualsIgnoreCase( value, "true" ) );
		}
		else if ( ( strcmp( arg, "--adaptive" ) == 0 || strcmp( arg, "-ar" ) == 0 ) && i + 1 < argc )
		{
			const char* nextArg = argv[++i];
			dbvhEnableAdaptive = ( EqualsIgnoreCase( nextArg, "on" ) || strcmp( nextArg, "1" ) == 0 || EqualsIgnoreCase( nextArg, "true" ) );
		}
		else if ( ( value = MatchValue( arg, "--max-subtree-leaves=", "-msl=" ) ) != NULL )
		{
			dbvhMaxSubtreeLeaves = b3ClampInt( atoi( value ), 1, 100000 );
		}
		else if ( ( strcmp( arg, "--max-subtree-leaves" ) == 0 || strcmp( arg, "-msl" ) == 0 ) && i + 1 < argc )
		{
			dbvhMaxSubtreeLeaves = b3ClampInt( atoi( argv[++i] ), 1, 100000 );
		}
		else if ( strcmp( arg, "-gt" ) == 0 || strcmp( arg, "--ground-truth" ) == 0 )
		{
			groundTruthMode = true;
			exportCsv = true;
		}
		else if ( ( value = MatchValue( arg, "-o=", "--output-csv=" ) ) != NULL )
		{
			customCsvFile = value;
			exportCsv = true;
		}
		else if ( ( strcmp( arg, "-o" ) == 0 || strcmp( arg, "--output-csv" ) == 0 ) && i + 1 < argc )
		{
			customCsvFile = argv[++i];
			exportCsv = true;
		}
		else if ( strcmp( arg, "-c" ) == 0 || strcmp( arg, "--csv" ) == 0 )
		{
			exportCsv = true;
		}
		else if ( strcmp( arg, "-nc" ) == 0 || strcmp( arg, "--no-continuous" ) == 0 )
		{
			enableContinuous = false;
			printf( "Continuous disabled\n" );
		}
		else if ( strcmp( arg, "-s" ) == 0 || strcmp( arg, "--record-steps" ) == 0 )
		{
			recordStepTimes = true;
		}
		else if ( strcmp( arg, "-l" ) == 0 || strcmp( arg, "--list" ) == 0 )
		{
			PrintBenchmarks( benchmarks, benchmarkCount );
			exit( 0 );
		}
		else if ( strcmp( arg, "-h" ) == 0 || strcmp( arg, "--help" ) == 0 )
		{
			printf( "Usage:\n"
					"  -t, --threads=<int>          Maximum threads to use\n"
					"  -b, --benchmark=<name|idx>   Run a specific benchmark\n"
					"  -w, --workers=<int>          Fixed worker count\n"
					"  -r, --repeats=<int>          Number of benchmark repeats (default: 4)\n"
					"  --steps=<int>                Override step count per benchmark\n"
					"  -bp, --broadphase=native|dbvh Select broadphase implementation\n"
					"  -m, --metric=area_ratio|subtree_sah Degradation metric for DBVH rebuild\n"
					"  -th, --threshold=<float>     Rebuild threshold value\n"
					"  --rebuild=on|off             Enable/disable incremental subtree rebuild\n"
					"  --fattening=on|off           Enable/disable AABB fattening\n"
					"  --predictive=on|off          Enable/disable predictive expansion\n"
					"  --rotations=on|off           Enable/disable tree rotations\n"
					"  -gt, --ground-truth          Enable per-frame Full Binned SAH ideal tree evaluation\n"
					"  -c, --csv                    Export per-frame metrics to CSV\n"
					"  -o, --output-csv=<file>      Custom output CSV filename\n"
					"  -nc, --no-continuous         Disable continuous collision\n"
					"  -s, --record-steps           Record per-step times in .dat file\n"
					"  -l, --list                   List all registered benchmarks\n"
					"  -h, --help                   Display this help message\n" );
			exit( 0 );
		}
		else
		{
			printf( "Unknown option \"%s\", use -h for help\n", arg );
		}
	}

	if ( !customThresholdSet )
	{
		dbvhThreshold = ( dbvhMetric == 0 ) ? 1.50f : 0.40f;
	}

	if ( singleWorkerCount != -1 )
	{
		singleWorkerCount = b3ClampInt( singleWorkerCount, 1, maxThreadCount );
	}

	b3Profile* profiles = malloc( maxSteps * sizeof( b3Profile ) );
	StepRecord* stepRecords = malloc( maxSteps * sizeof( StepRecord ) );

	for ( int i = 0; i < maxSteps; ++i )
	{
		profiles[i] = maxProfile;
	}

	printf( "Starting benchmarks\n" );
	printf( "Broadphase: %s\n", useDBVH ? "DBVH (Custom)" : "Native (b3DynamicTree)" );
	if ( useDBVH )
	{
		printf( "DBVH Config: rebuild=%s, adaptive=%s, max_leaves=%d, metric=%s, threshold=%.2f, interval=%d, budget=%d, fattening=%s, predictive=%s, rotations=%s\n",
				dbvhEnableRebuild ? "on" : "off",
				dbvhEnableAdaptive ? "on" : "off",
				dbvhMaxSubtreeLeaves,
				dbvhMetric == 0 ? "AreaRatio" : "SubtreeSAH",
				dbvhThreshold,
				dbvhInterval,
				dbvhBudget,
				dbvhEnableFattening ? "on" : "off",
				dbvhEnablePredictive ? "on" : "off",
				dbvhEnableRotations ? "on" : "off" );
	}
	if ( groundTruthMode )
	{
		printf( "Ground Truth Mode: ENABLED (Computing ideal Binned SAH tree each step)\n" );
	}
	printf( "======================================\n" );

	if ( overrideActorCount > 0 )
	{
		SetBenchmarkActorCount( overrideActorCount );
		printf( "Actor Count Override: %d bodies\n", overrideActorCount );
	}

	for ( int benchmarkIndex = 0; benchmarkIndex < benchmarkCount; ++benchmarkIndex )
	{
		if ( singleBenchmark != -1 && benchmarkIndex != singleBenchmark )
		{
			continue;
		}

#ifdef NDEBUG
		int stepCount = ( overrideStepCount > 0 ) ? overrideStepCount : benchmarks[benchmarkIndex].totalStepCount;
#else
		int stepCount = ( overrideStepCount > 0 ) ? overrideStepCount : 10;
#endif

		Benchmark* benchmark = benchmarks + benchmarkIndex;
		b3Counters counters = { 0 };
		bool countersAcquired = false;

		printf( "\nBenchmark: %s | Steps: %d\n", benchmark->name, stepCount );

		float minTime[B3_MAX_WORKERS] = { 0 };

		for ( int threadCount = 1; threadCount <= maxThreadCount; ++threadCount )
		{
			if ( singleWorkerCount != -1 && singleWorkerCount != threadCount )
			{
				continue;
			}

			printf( "  Threads: %d\n", threadCount );

			for ( int runIndex = 0; runIndex < runCount; ++runIndex )
			{
				b3WorldDef worldDef = b3DefaultWorldDef();
				worldDef.enableContinuous = enableContinuous;
				worldDef.workerCount = threadCount;
				// DBVH Integration: Pass useDBVH to world definition
				worldDef.useDBVH = useDBVH;

				if ( benchmark->capacityFcn != NULL )
				{
					benchmark->capacityFcn( &worldDef.capacity );
				}

				b3WorldId worldId = b3CreateWorld( &worldDef );

				// DBVH Integration: Configure runtime DBVH parameters
				if ( useDBVH )
				{
					dbvh_config_t dbvhCfg;
					dbvhCfg.enableRebuild = dbvhEnableRebuild;
					dbvhCfg.enableFattening = dbvhEnableFattening;
					dbvhCfg.enablePredictive = dbvhEnablePredictive;
					dbvhCfg.enableRotations = dbvhEnableRotations;
					dbvhCfg.degradationMetric = (dbvh_degradation_metric_t)dbvhMetric;
					dbvhCfg.rebuildThreshold = dbvhThreshold;
					dbvhCfg.areaRatioThreshold = (dbvhMetric == 0) ? dbvhThreshold : 1.80f;
					dbvhCfg.subtreeSAHThreshold = (dbvhMetric == 1) ? dbvhThreshold : 1.80f;
					dbvhCfg.rebuildInterval = dbvhInterval;
					dbvhCfg.maxRebuildsPerFrame = dbvhBudget;
					dbvhCfg.enableAdaptiveRebuild = dbvhEnableAdaptive;
					dbvhCfg.maxSubtreeLeaves = dbvhMaxSubtreeLeaves;
					b3World_SetDBVHConfig( worldId, &dbvhCfg );
				}

				benchmark->createFcn( worldId );

				// DBVH initial build via Binned SAH buckets before simulation loop
				if ( useDBVH )
				{
					b3World_RebuildBroadPhase( worldId );
				}

				float timeStep = 1.0f / 60.0f;
				int subStepCount = 4;

				// Initial step can be expensive and skew benchmark
				if ( benchmark->stepFcn != NULL )
				{
					benchmark->stepFcn( worldId, 0 );
				}

				assert( stepCount <= maxSteps );

				b3World_Step( worldId, timeStep, subStepCount );

				b3Profile profile = b3World_GetProfile( worldId );
				MinProfile( profiles + 0, &profile );

				b3Counters cnt0 = b3World_GetCounters( worldId );
				b3BroadPhaseQualityMetrics qm0 = b3World_GetBroadPhaseQualityMetrics( worldId, b3_dynamicBody, groundTruthMode, 1.0f, 1.0f );
				if ( runIndex == 0 )
				{
					stepRecords[0].frame = 0;
					stepRecords[0].stepTime = profile.step;
					stepRecords[0].pairsTime = profile.pairs;
					stepRecords[0].collideTime = profile.collide;
					stepRecords[0].solveTime = profile.solve;
					stepRecords[0].contactCount = cnt0.contactCount;
					stepRecords[0].treeHeight = qm0.current.treeHeight;
					stepRecords[0].leafCount = qm0.current.leafCount;
					stepRecords[0].nodeCount = qm0.current.nodeCount;
					stepRecords[0].sahStandard = qm0.current.sahCostStandard;
					stepRecords[0].sahNormalized = qm0.current.sahCostNormalized;
					stepRecords[0].idealSahStandard = qm0.ideal.sahCostStandard;
					stepRecords[0].idealSahNormalized = qm0.ideal.sahCostNormalized;
					stepRecords[0].idealTreeHeight = qm0.ideal.treeHeight;
					stepRecords[0].qualityRatioStandard = qm0.qualityRatioStandard;
					stepRecords[0].qualityRatioNormalized = qm0.qualityRatioNormalized;
				}

				uint64_t ticks = b3GetTicks();

				for ( int stepIndex = 1; stepIndex < stepCount; ++stepIndex )
				{
					if ( benchmark->stepFcn != NULL )
					{
						benchmark->stepFcn( worldId, stepIndex );
					}

					b3World_Step( worldId, timeStep, subStepCount );

					profile = b3World_GetProfile( worldId );
					MinProfile( profiles + stepIndex, &profile );

					if ( runIndex == 0 )
					{
						b3Counters cnt = b3World_GetCounters( worldId );
						b3BroadPhaseQualityMetrics qm = b3World_GetBroadPhaseQualityMetrics( worldId, b3_dynamicBody, groundTruthMode, 1.0f, 1.0f );
						stepRecords[stepIndex].frame = stepIndex;
						stepRecords[stepIndex].stepTime = profile.step;
						stepRecords[stepIndex].pairsTime = profile.pairs;
						stepRecords[stepIndex].collideTime = profile.collide;
						stepRecords[stepIndex].solveTime = profile.solve;
						stepRecords[stepIndex].contactCount = cnt.contactCount;
						stepRecords[stepIndex].treeHeight = qm.current.treeHeight;
						stepRecords[stepIndex].leafCount = qm.current.leafCount;
						stepRecords[stepIndex].nodeCount = qm.current.nodeCount;
						stepRecords[stepIndex].sahStandard = qm.current.sahCostStandard;
						stepRecords[stepIndex].sahNormalized = qm.current.sahCostNormalized;
						stepRecords[stepIndex].idealSahStandard = qm.ideal.sahCostStandard;
						stepRecords[stepIndex].idealSahNormalized = qm.ideal.sahCostNormalized;
						stepRecords[stepIndex].idealTreeHeight = qm.ideal.treeHeight;
						stepRecords[stepIndex].qualityRatioStandard = qm.qualityRatioStandard;
						stepRecords[stepIndex].qualityRatioNormalized = qm.qualityRatioNormalized;
					}
				}

				float ms = b3GetMilliseconds( ticks );
				printf( "    run %d : %6.2f ms\n", runIndex, ms );

				if ( runIndex == 0 )
				{
					minTime[threadCount - 1] = ms;
				}
				else
				{
					minTime[threadCount - 1] = b3MinFloat( minTime[threadCount - 1], ms );
				}

				if ( countersAcquired == false )
				{
					counters = b3World_GetCounters( worldId );
					countersAcquired = true;
				}

				if ( benchmark->destroyFcn != NULL )
				{
					benchmark->destroyFcn();
				}

				b3DestroyWorld( worldId );
			}

			// Export per-frame CSV
			if ( exportCsv )
			{
				CREATE_DIR( "benchmark_results" );
				char csvFileName[512] = { 0 };
				if ( customCsvFile != NULL )
				{
					if ( strchr( customCsvFile, '/' ) != NULL || strchr( customCsvFile, '\\' ) != NULL )
					{
						snprintf( csvFileName, sizeof( csvFileName ), "%s", customCsvFile );
					}
					else
					{
						snprintf( csvFileName, sizeof( csvFileName ), "benchmark_results/%s", customCsvFile );
					}
				}
				else
				{
					const char* bpName = useDBVH ? "dbvh" : "native";
					snprintf( csvFileName, sizeof( csvFileName ), "benchmark_results/benchmark_%s_%s_t%d.csv", benchmark->name, bpName, threadCount );
				}

				FILE* csvFile = fopen( csvFileName, "w" );
				if ( csvFile != NULL )
				{
					fprintf( csvFile, "frame,step_ms,pairs_ms,collide_ms,solve_ms,contact_count,tree_height,leaf_count,node_count,sah_standard,sah_normalized,ideal_sah_standard,ideal_sah_normalized,ideal_tree_height,quality_ratio_standard,quality_ratio_normalized\n" );
					for ( int s = 0; s < stepCount; ++s )
					{
						StepRecord* r = stepRecords + s;
						fprintf( csvFile, "%d,%.4f,%.4f,%.4f,%.4f,%d,%d,%d,%d,%.4f,%.4f,%.4f,%.4f,%d,%.4f,%.4f\n",
								 r->frame, r->stepTime, r->pairsTime, r->collideTime, r->solveTime,
								 r->contactCount,
								 r->treeHeight, r->leafCount, r->nodeCount,
								 r->sahStandard, r->sahNormalized,
								 r->idealSahStandard, r->idealSahNormalized,
								 r->idealTreeHeight,
								 r->qualityRatioStandard, r->qualityRatioNormalized );
					}
					fclose( csvFile );
					printf( "    -> Exported CSV metrics to: %s\n", csvFileName );
				}
			}

			if ( recordStepTimes )
			{
				char fileName[64] = { 0 };
				snprintf( fileName, 64, "%s_t%d.dat", benchmarks[benchmarkIndex].name, threadCount );
				FILE* file = fopen( fileName, "w" );
				if ( file != NULL )
				{
					for ( int stepIndex = 0; stepIndex < stepCount; ++stepIndex )
					{
						b3Profile p = profiles[stepIndex];
						fprintf( file, "%g %g %g %g %g %g %g\n", p.step, p.pairs, p.collide, p.constraints, p.transforms,
								 p.refit, p.sleepIslands );
					}
					fclose( file );
				}
			}
		}

		printf( "  Objects: body=%d, shape=%d, contact=%d, joint=%d, tree_height=%d\n",
				counters.bodyCount, counters.shapeCount, counters.contactCount, counters.jointCount, counters.treeHeight );
	}

	printf( "\n======================================\n" );
	printf( "All benchmarks complete!\n" );

	free( profiles );
	free( stepRecords );

#ifdef TRACY_ENABLE
	___tracy_shutdown_profiler();
#endif

	return 0;
}
