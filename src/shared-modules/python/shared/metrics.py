"""
Custom CloudWatch metrics for monitoring video processing application.

Provides utilities to publish custom metrics for business and performance monitoring.
"""

import boto3
import time
from datetime import datetime
from typing import List, Dict, Optional, Union


# CloudWatch client
cloudwatch = boto3.client('cloudwatch')

# Namespace for all metrics
NAMESPACE = 'VideoProcessing'


def put_metric(
    metric_name: str,
    value: Union[int, float],
    unit: str = 'Count',
    dimensions: Optional[List[Dict[str, str]]] = None,
    timestamp: Optional[datetime] = None
) -> bool:
    """
    Publish a single custom metric to CloudWatch.

    Args:
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement (Count, Seconds, Milliseconds, Bytes, etc.)
        dimensions: List of dimension dicts [{'Name': 'key', 'Value': 'val'}]
        timestamp: Timestamp for metric (default: now)

    Returns:
        True if successful, False otherwise

    Usage:
        put_metric('VideoProcessingTime', 45000, unit='Milliseconds')
        put_metric('ClipsGenerated', 3, dimensions=[
            {'Name': 'TemplateId', 'Value': 'modern-minimal'}
        ])
    """
    try:
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Timestamp': timestamp or datetime.utcnow()
        }

        if dimensions:
            metric_data['Dimensions'] = dimensions

        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[metric_data]
        )

        print(f"Published metric: {metric_name}={value} {unit}")
        return True

    except Exception as e:
        print(f"Error publishing metric {metric_name}: {str(e)}")
        return False


def put_metrics_batch(metrics: List[Dict]) -> bool:
    """
    Publish multiple metrics in a single API call (more efficient).

    Args:
        metrics: List of metric dictionaries with keys:
                 - metric_name: str
                 - value: float
                 - unit: str (optional, default: 'Count')
                 - dimensions: list (optional)

    Returns:
        True if successful, False otherwise

    Usage:
        put_metrics_batch([
            {'metric_name': 'VideosProcessed', 'value': 10},
            {'metric_name': 'TotalClips', 'value': 30},
            {'metric_name': 'AvgProcessingTime', 'value': 180, 'unit': 'Seconds'}
        ])
    """
    try:
        metric_data = []

        for metric in metrics:
            data = {
                'MetricName': metric['metric_name'],
                'Value': metric['value'],
                'Unit': metric.get('unit', 'Count'),
                'Timestamp': metric.get('timestamp', datetime.utcnow())
            }

            if 'dimensions' in metric:
                data['Dimensions'] = metric['dimensions']

            metric_data.append(data)

        # CloudWatch allows max 20 metrics per call
        for i in range(0, len(metric_data), 20):
            batch = metric_data[i:i+20]
            cloudwatch.put_metric_data(
                Namespace=NAMESPACE,
                MetricData=batch
            )

        print(f"Published {len(metric_data)} metrics in batch")
        return True

    except Exception as e:
        print(f"Error publishing batch metrics: {str(e)}")
        return False


# Convenience functions for common metrics

def track_video_processing_time(session_id: str, duration_ms: int, template_id: str = None):
    """Track video processing duration."""
    dimensions = [{'Name': 'SessionId', 'Value': session_id}]
    if template_id:
        dimensions.append({'Name': 'TemplateId', 'Value': template_id})

    put_metric('VideoProcessingTime', duration_ms, unit='Milliseconds', dimensions=dimensions)


def track_clips_generated(count: int, template_id: str = None):
    """Track number of clips generated."""
    dimensions = []
    if template_id:
        dimensions.append({'Name': 'TemplateId', 'Value': template_id})

    put_metric('ClipsGenerated', count, dimensions=dimensions if dimensions else None)


def track_api_call(endpoint: str, status_code: int, latency_ms: int):
    """Track API endpoint performance."""
    dimensions = [
        {'Name': 'Endpoint', 'Value': endpoint},
        {'Name': 'StatusCode', 'Value': str(status_code)}
    ]

    # Track call count
    put_metric('APIRequests', 1, dimensions=dimensions)

    # Track latency
    put_metric('APILatency', latency_ms, unit='Milliseconds', dimensions=dimensions)

    # Track errors
    if status_code >= 400:
        put_metric('APIErrors', 1, dimensions=[{'Name': 'Endpoint', 'Value': endpoint}])


def track_transcription(method: str, duration_s: int, success: bool = True):
    """Track transcription performance."""
    dimensions = [
        {'Name': 'Method', 'Value': method},
        {'Name': 'Status', 'Value': 'success' if success else 'failure'}
    ]

    put_metric('TranscriptionRequests', 1, dimensions=dimensions)
    put_metric('TranscriptionDuration', duration_s, unit='Seconds', dimensions=dimensions)


def track_download(source: str, size_mb: float, duration_s: int, success: bool = True):
    """Track video download performance."""
    dimensions = [
        {'Name': 'Source', 'Value': source},
        {'Name': 'Status', 'Value': 'success' if success else 'failure'}
    ]

    put_metric('VideoDownloads', 1, dimensions=dimensions)
    put_metric('VideoSize', size_mb, unit='Megabytes', dimensions=dimensions)
    put_metric('DownloadDuration', duration_s, unit='Seconds', dimensions=dimensions)


def track_ffmpeg_processing(operation: str, duration_s: int, success: bool = True):
    """Track FFmpeg operations."""
    dimensions = [
        {'Name': 'Operation', 'Value': operation},
        {'Name': 'Status', 'Value': 'success' if success else 'failure'}
    ]

    put_metric('FFmpegOperations', 1, dimensions=dimensions)
    put_metric('FFmpegDuration', duration_s, unit='Seconds', dimensions=dimensions)


def track_cache_hit(cache_type: str, hit: bool = True):
    """Track cache performance."""
    dimensions = [
        {'Name': 'CacheType', 'Value': cache_type},
        {'Name': 'Result', 'Value': 'hit' if hit else 'miss'}
    ]

    if hit:
        put_metric('CacheHits', 1, dimensions=dimensions)
    else:
        put_metric('CacheMisses', 1, dimensions=dimensions)


def track_queue_depth(queue_name: str, depth: int):
    """Track SQS queue depth."""
    dimensions = [{'Name': 'QueueName', 'Value': queue_name}]
    put_metric('QueueDepth', depth, dimensions=dimensions)


def track_lambda_cold_start(function_name: str, cold_start: bool = True):
    """Track Lambda cold starts."""
    dimensions = [
        {'Name': 'FunctionName', 'Value': function_name},
        {'Name': 'ColdStart', 'Value': 'yes' if cold_start else 'no'}
    ]

    put_metric('LambdaInvocations', 1, dimensions=dimensions)


def track_user_plan_usage(user_plan: str, action: str):
    """Track usage by user plan."""
    dimensions = [
        {'Name': 'UserPlan', 'Value': user_plan},
        {'Name': 'Action', 'Value': action}
    ]

    put_metric('PlanUsage', 1, dimensions=dimensions)


def track_circuit_breaker(name: str, state: str, action: str):
    """Track circuit breaker state changes."""
    dimensions = [
        {'Name': 'BreakerName', 'Value': name},
        {'Name': 'State', 'Value': state},
        {'Name': 'Action', 'Value': action}
    ]

    put_metric('CircuitBreakerEvents', 1, dimensions=dimensions)


def track_clip_detection_time(session_id: str, duration_ms: int):
    """Track clip detection duration."""
    dimensions = [
        {'Name': 'SessionId', 'Value': session_id}
    ]
    put_metric('ClipDetectionTime', duration_ms, unit='Milliseconds', dimensions=dimensions)


def track_ai_api_call(session_id: str, api_name: str, status: str, duration_ms: int):
    """Track AI API call metrics."""
    dimensions = [
        {'Name': 'API', 'Value': api_name},
        {'Name': 'Status', 'Value': status}
    ]
    put_metric('AIAPICall', 1, dimensions=dimensions)
    put_metric('AIAPILatency', duration_ms, unit='Milliseconds', dimensions=dimensions)


def track_transcription_time(session_id: str, duration_ms: int):
    """Track transcription duration."""
    dimensions = [
        {'Name': 'SessionId', 'Value': session_id}
    ]
    put_metric('TranscriptionTime', duration_ms, unit='Milliseconds', dimensions=dimensions)


def track_video_processing_complete(session_id: str, clips_count: int):
    """Track video processing completion."""
    dimensions = [
        {'Name': 'SessionId', 'Value': session_id}
    ]
    put_metric('VideoProcessingComplete', 1, dimensions=dimensions)
    put_metric('ClipsGenerated', clips_count, dimensions=dimensions)


def track_clip_processing_time(session_id: str, clip_index: int, duration_ms: int):
    """Track individual clip processing time."""
    dimensions = [
        {'Name': 'SessionId', 'Value': session_id},
        {'Name': 'ClipIndex', 'Value': str(clip_index)}
    ]
    put_metric('ClipProcessingTime', duration_ms, unit='Milliseconds', dimensions=dimensions)


# Performance timer context manager
class MetricTimer:
    """
    Context manager for timing operations and publishing metrics.

    Usage:
        with MetricTimer('VideoProcessing', session_id=session_id):
            # ... process video ...

        # Automatically publishes VideoProcessing metric with duration
    """

    def __init__(self, metric_name: str, unit: str = 'Milliseconds', **dimensions):
        self.metric_name = metric_name
        self.unit = unit
        self.dimensions = [{'Name': k, 'Value': str(v)} for k, v in dimensions.items()]
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        if self.unit == 'Milliseconds':
            value = duration * 1000
        elif self.unit == 'Seconds':
            value = duration
        else:
            value = duration

        success = exc_type is None
        self.dimensions.append({'Name': 'Status', 'Value': 'success' if success else 'failure'})

        put_metric(self.metric_name, value, unit=self.unit, dimensions=self.dimensions)


# Export commonly used functions
__all__ = [
    'put_metric',
    'put_metrics_batch',
    'track_video_processing_time',
    'track_clips_generated',
    'track_api_call',
    'track_transcription',
    'track_download',
    'track_ffmpeg_processing',
    'track_cache_hit',
    'track_queue_depth',
    'track_lambda_cold_start',
    'track_user_plan_usage',
    'track_circuit_breaker',
    'MetricTimer'
]
