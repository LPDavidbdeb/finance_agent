import pandas as pd
import logging
from decimal import Decimal
from django.utils import timezone
from django.db import connection
from django.db.models import Sum
from django.core.cache import cache
from celery import shared_task

from accounting.models import Account, AnalysisRun, CategoryMonthlyStat, InsightFact
from accounting.analysis.classification import ProcessClassifier
from accounting.analysis.trend import TrendAnalyzer
from accounting.analysis.volatility import VolatilityAnalyzer, VolatilityResult
from accounting.analysis.insights import InsightEngine, CategoryProfile

logger = logging.getLogger(__name__)
INSIGHTS_SYNC_CACHE_KEY = "insights_is_syncing"


@shared_task(bind=True)
def rebuild_financial_insights(self, family_id=None):
    """
    LAYER 2: Analytical ETL Pipeline Orchestrator

    4-Step Process:
    1. REFRESH: Update the Materialized View with latest ledger data
    2. EXTRACT: Query CategoryMonthlyStat and transform to DataFrames
    3. TRANSFORM: Run data through EPIC 1-4 mathematical pipeline
    4. LOAD: Persist CategoryProfile results to InsightFact (append-only)

    This task is designed to be:
    - Idempotent (safe to run multiple times)
    - Append-only (never deletes historical insights)
    - Auditable (every computation stored with timestamp)

    Args:
        family_id (int, optional): If provided, only compute insights for this family.
                                  If None, compute for all families.

    Returns:
        dict: Summary of insights computed {'families_processed': n, 'insights_created': n}
    """
    cache.set(INSIGHTS_SYNC_CACHE_KEY, True, timeout=3600)

    try:
        logger.info("Starting rebuild_financial_insights pipeline")

        # Step 1: REFRESH
        logger.info("Step 1: Refreshing Materialized View")
        _refresh_materialized_view()

        source_refreshed_at = timezone.now()

        # Step 2-4: Process all families (or specific family)
        families = _get_families_to_process(family_id)
        total_insights_created = 0
        runs_created = 0

        for family in families:
            logger.info(f"Processing family: {family.name}")
            analysis_run = AnalysisRun.objects.create(
                family=family,
                status=AnalysisRun.Status.RUNNING,
                source_refreshed_at=source_refreshed_at,
            )
            runs_created += 1

            try:
                # Step 2: EXTRACT
                logger.info(f"Step 2: Extracting data for family {family.id}")
                category_dataframes = _extract_category_data(family)

                if not category_dataframes:
                    logger.warning(f"No data extracted for family {family.id}")
                    analysis_run.status = AnalysisRun.Status.SUCCEEDED
                    analysis_run.insights_created = 0
                    analysis_run.completed_at = timezone.now()
                    analysis_run.save(update_fields=['status', 'insights_created', 'completed_at'])
                    continue

                # Step 3: TRANSFORM
                logger.info(f"Step 3: Transforming data through analytics pipeline")
                category_profiles = _transform_through_pipeline(family, category_dataframes)

                # Step 4: LOAD
                logger.info(f"Step 4: Loading insights to InsightFact")
                insights_created = _load_insights(category_profiles, analysis_run=analysis_run)
                total_insights_created += insights_created

                analysis_run.status = AnalysisRun.Status.SUCCEEDED
                analysis_run.insights_created = insights_created
                analysis_run.completed_at = timezone.now()
                analysis_run.save(update_fields=['status', 'insights_created', 'completed_at'])

                logger.info(f"Created {insights_created} insights for family {family.id}")
            except Exception as family_exc:
                analysis_run.status = AnalysisRun.Status.FAILED
                analysis_run.error_message = str(family_exc)
                analysis_run.completed_at = timezone.now()
                analysis_run.save(update_fields=['status', 'error_message', 'completed_at'])
                raise

        result = {
            'families_processed': len(families),
            'insights_created': total_insights_created,
            'analysis_runs_created': runs_created,
        }
        logger.info(f"Pipeline completed successfully: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in rebuild_financial_insights: {str(e)}", exc_info=True)
        raise
    finally:
        cache.set(INSIGHTS_SYNC_CACHE_KEY, False, timeout=3600)
        logger.info("Insights sync state reset to idle")


def _refresh_materialized_view():
    """
    Step 1: Refresh the PostgreSQL Materialized View with latest data.

    Uses REFRESH MATERIALIZED VIEW CONCURRENTLY if a unique index exists,
    otherwise falls back to standard REFRESH.
    """
    with connection.cursor() as cursor:
        try:
            # Try concurrent refresh first (requires unique index)
            cursor.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY accounting_categorymonthlystat"
            )
            logger.info("Materialized View refreshed CONCURRENTLY")
        except Exception as e:
            logger.warning(f"Concurrent refresh failed, trying standard refresh: {str(e)}")
            try:
                cursor.execute(
                    "REFRESH MATERIALIZED VIEW accounting_categorymonthlystat"
                )
                logger.info("Materialized View refreshed (standard)")
            except Exception as e2:
                logger.error(f"Failed to refresh materialized view: {str(e2)}")
                raise


def _get_families_to_process(family_id=None):
    """
    Get list of families to process.

    Args:
        family_id: If provided, return single family. Else all families.

    Returns:
        QuerySet of Family objects
    """
    from users.models import Family

    if family_id:
        return Family.objects.filter(id=family_id)
    else:
        return Family.objects.all()


def _extract_category_data(family):
    """
    Step 2: Extract aggregated monthly data from Materialized View.

    Transforms Django QuerySet into a dict of Pandas Series/DataFrames
    organized by category, ready for analysis.

    Args:
        family: Family object

    Returns:
        dict: {category_id: pd.Series} where Series is monthly spend values
    """
    # Query the materialized view
    stats = CategoryMonthlyStat.objects.filter(
        category_id__in=Account.objects.filter(family=family).values_list('id', flat=True)
    ).order_by('category_id', 'month')

    # Group by category
    category_dataframes = {}

    for stat in stats:
        if stat.category_id not in category_dataframes:
            category_dataframes[stat.category_id] = {
                'dates': [],
                'amounts': [],
                'transaction_counts': [],
                'avg_tickets': []
            }

        # Append month-level data
        category_dataframes[stat.category_id]['dates'].append(stat.month)
        category_dataframes[stat.category_id]['amounts'].append(float(stat.total_amount))
        category_dataframes[stat.category_id]['transaction_counts'].append(stat.transaction_count)
        category_dataframes[stat.category_id]['avg_tickets'].append(float(stat.avg_ticket))

    # Convert to Pandas Series (monthly spend time series)
    pandas_dataframes = {}
    for category_id, data in category_dataframes.items():
        if len(data['dates']) > 0:
            pandas_dataframes[category_id] = pd.Series(
                data['amounts'],
                index=pd.DatetimeIndex(data['dates']),
                name=f'Category_{category_id}'
            )

    return pandas_dataframes


def _transform_through_pipeline(family, category_dataframes):
    """
    Step 3: Transform data through the EPIC 1-4 mathematical pipeline.

    For each category, runs through:
    - EPIC 1: Signal filtering & Process classification
    - EPIC 2: Trend & Volatility analysis
    - EPIC 3: Causal decomposition (optional, data dependent)
    - EPIC 4: Projection & Insight ranking

    Args:
        family: Family object
        category_dataframes: dict of {category_id: pd.Series}

    Returns:
        list: CategoryProfile objects ready to persist
    """
    from accounting.analysis.projection import ProjectionEngine

    category_profiles = []

    # Initialize analyzers
    classifier = ProcessClassifier()
    trend_analyzer = TrendAnalyzer()
    volatility_analyzer = VolatilityAnalyzer()
    projection_engine = ProjectionEngine()

    # Get materiality (total spend by category)
    total_family_spend = CategoryMonthlyStat.objects.filter(
        category_id__in=Account.objects.filter(family=family).values_list('id', flat=True)
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('1')

    # Process each category
    for category_id, series in category_dataframes.items():
        try:
            # Get Account object
            account = Account.objects.get(id=category_id)

            # Skip if insufficient data
            if len(series) < 2:
                logger.debug(f"Skipping {account.name}: insufficient data ({len(series)} points)")
                continue

            # EPIC 1: Classify process type
            process_type = classifier.classify(series)

            # EPIC 2: Analyze trend
            trend_result = trend_analyzer.analyze(series)
            
            # EPIC 2: Analyze volatility
            volatility_result = volatility_analyzer.detect_structural_break(series)
            volatility_result_obj = VolatilityResult(
                ser=volatility_result.get('ser', 0.0),
                has_structural_break=volatility_result.get('has_structural_break', False),
                z_scores=volatility_result.get('z_scores', {})
            )

            # EPIC 3: Causal analysis (if sufficient data)
            causal_result = None
            if len(series) >= 12:
                # Would need raw transaction data for CausalAnalyzer
                # For now, skip causal analysis in ETL
                pass

            # EPIC 4.1: Project future values
            projection_result = projection_engine.project(
                historical_series=series,
                process_type=process_type,
                trend_result=trend_result,
                volatility_result=volatility_result_obj,
                reference_date=pd.Timestamp.now()
            )

            # Calculate materiality percentage
            category_spend = float(CategoryMonthlyStat.objects.filter(
                category_id=category_id
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0)
            materiality_pct = (category_spend / float(total_family_spend) * 100) if total_family_spend > 0 else 0

            # EPIC 4.2: Create CategoryProfile for ranking
            profile = CategoryProfile(
                category_name=account.name,
                materiality_pct=materiality_pct,
                process_type=process_type,
                trend_result=trend_result,
                volatility_result=volatility_result_obj,
                causal_result=causal_result,
                projected_value=float(projection_result.projected_series.iloc[0]) if len(projection_result.projected_series) > 0 else None,
                projected_upper=float(projection_result.upper_bound.iloc[0]) if len(projection_result.upper_bound) > 0 else None,
                projected_lower=float(projection_result.lower_bound.iloc[0]) if len(projection_result.lower_bound) > 0 else None,
            )

            # Generate expert summary
            insight_engine = InsightEngine()
            expert_summary = insight_engine.generate_expert_summary(profile)

            # Store with summary for loading
            profile._expert_summary = expert_summary
            profile._account_id = category_id

            category_profiles.append(profile)
            logger.debug(f"Analyzed {account.name}: {process_type.value}, score={profile.insight_score:.0f}")

        except Account.DoesNotExist:
            logger.warning(f"Account with id {category_id} not found")
            continue
        except Exception as e:
            logger.error(f"Error analyzing category {category_id}: {str(e)}", exc_info=True)
            continue

    return category_profiles


def _load_insights(category_profiles, analysis_run=None):
    """
    Step 4: Load CategoryProfile results into InsightFact (append-only).

    Converts CategoryProfile objects into InsightFact model instances
    and uses bulk_create for efficient insertion.

    Args:
        category_profiles: list of CategoryProfile objects

    Returns:
        int: Number of insights created
    """
    insight_facts = []

    for profile in category_profiles:
        insight_fact = InsightFact(
            category_id=profile._account_id,
            analysis_run=analysis_run,
            insight_score=profile.insight_score,
            materiality_pct=profile.materiality_pct,
            process_type=profile.process_type.value,
            slope=profile.trend_result.slope if profile.trend_result else None,
            has_structural_break=profile.volatility_result.has_structural_break if profile.volatility_result else False,
            causal_volume_pct=profile.causal_result.volume_effect_pct if profile.causal_result else None,
            causal_price_pct=profile.causal_result.price_effect_pct if profile.causal_result else None,
            projected_value=profile.projected_value,
            expert_summary=profile._expert_summary if hasattr(profile, '_expert_summary') else ""
        )
        insight_facts.append(insight_fact)

    # Bulk create (append-only, no deletes)
    if insight_facts:
        created = InsightFact.objects.bulk_create(insight_facts)
        logger.info(f"Bulk created {len(created)} InsightFact records")
        return len(created)
    else:
        logger.warning("No insights to load")
        return 0


