"""
Celery tasks for analytics (R service integration).
"""
import httpx
import time
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from apps.accounts.models import UsageEvent
import structlog

logger = structlog.get_logger()


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def run_analytics(self, query_id, analysis_type, retrieved_chunks):
    """Run statistical analysis via R service."""
    from apps.analytics.models import AnalyticsJob
    from apps.queries.models import Query

    try:
        query = Query.objects.get(id=query_id)
    except Query.DoesNotExist:
        logger.error("Query not found for analytics", query_id=query_id)
        return

    # Create or get analytics job
    job, created = AnalyticsJob.objects.get_or_create(
        query=query,
        analysis_type=analysis_type,
        defaults={
            'company': query.company,
            'parameters': {'retrieved_chunks': retrieved_chunks[:5]},  # Limit context
            'status': AnalyticsJob.Status.PENDING,
        }
    )

    if not created and job.status == AnalyticsJob.Status.COMPLETED:
        return

    job.status = AnalyticsJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save()

    try:
        # Prepare data for R service
        # Extract numeric data from retrieved chunks
        data = extract_numeric_data(retrieved_chunks)

        if not data:
            job.status = AnalyticsJob.Status.FAILED
            job.error_message = "No numeric data found for analysis"
            job.save()
            return

        # Call R service
        result = call_r_service(analysis_type, data, job.parameters)

        job.status = AnalyticsJob.Status.COMPLETED
        job.result_data = result.get('result', {})
        job.chart_spec = result.get('chart_spec', {})
        job.chart_data = result.get('chart_data', {})
        job.completed_at = timezone.now()
        job.save()

        # Update query result with analytics
        if hasattr(query, 'result'):
            query.result.chart_spec = job.chart_spec
            query.result.chart_data = job.chart_data
            query.result.answer_structured['analytics'] = job.result_data
            query.result.save(update_fields=['chart_spec', 'chart_data', 'answer_structured'])

        # Record usage
        UsageEvent.objects.create(
            company=query.company,
            user=query.user,
            event_type=UsageEvent.EventType.ANALYTICS,
            quantity=1,
            metadata={'analysis_type': analysis_type, 'query_id': str(query.id)}
        )

        logger.info("Analytics completed", query_id=query_id, analysis_type=analysis_type)

    except Exception as e:
        job.status = AnalyticsJob.Status.FAILED
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save()

        logger.error("Analytics failed", query_id=query_id, analysis_type=analysis_type, error=str(e))
        raise self.retry(exc=e)


def extract_numeric_data(retrieved_chunks):
    """Extract numeric data from retrieved chunks for analysis."""
    # This is a simplified extraction - in production, would be more sophisticated
    numeric_columns = {}

    for chunk in retrieved_chunks:
        content = chunk.get('content', '')
        # Simple parsing - look for tabular data
        lines = content.split('\n')
        for line in lines:
            if '|' in line and not line.startswith('|---'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 2:
                    # Try to parse as key-value pairs
                    pass

    return numeric_columns


def call_r_service(analysis_type: str, data: dict, parameters: dict) -> dict:
    """Call R Plumber service for statistical analysis."""
    url = f"{settings.R_SERVICE_URL}/{analysis_type}"

    payload = {
        'data': data,
        'parameters': parameters,
    }

    try:
        with httpx.Client(timeout=settings.R_SERVICE_TIMEOUT) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise Exception("R service timeout")
    except httpx.HTTPStatusError as e:
        raise Exception(f"R service error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        raise Exception(f"R service call failed: {str(e)}")