"""
WebSocket notification utility.

Sends real-time updates to connected WebSocket clients.
"""

import boto3
import json
import os
from typing import Dict, Any, List

try:
    from .dynamodb_client import get_websocket_connections
except (ImportError, ValueError):
    # ValueError for attempted relative import in non-package, ImportError for missing module
    try:
        from dynamodb_client import get_websocket_connections
    except ImportError:
        get_websocket_connections = None


# API Gateway Management API client
def get_api_gateway_client(endpoint_url: str):
    """
    Get API Gateway Management API client.

    Args:
        endpoint_url: WebSocket API endpoint URL

    Returns:
        boto3 client for API Gateway Management API
    """
    return boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=endpoint_url
    )


def send_to_connection(
    connection_id: str,
    data: Dict[str, Any],
    endpoint_url: str
) -> bool:
    """
    Send message to a WebSocket connection.

    Args:
        connection_id: WebSocket connection ID
        data: Data to send (will be JSON serialized)
        endpoint_url: WebSocket API endpoint URL

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_api_gateway_client(endpoint_url)

        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode('utf-8')
        )

        print(f"Sent message to connection {connection_id}")
        return True

    except client.exceptions.GoneException:
        print(f"Connection {connection_id} is gone (client disconnected)")
        return False

    except Exception as e:
        print(f"Error sending to connection {connection_id}: {str(e)}")
        return False


def notify_session_update(
    session_id: str,
    event_type: str,
    data: Dict[str, Any],
    endpoint_url: str = None
) -> int:
    """
    Notify all clients subscribed to a session.

    Args:
        session_id: Session identifier
        event_type: Type of event (processing_complete, processing_progress, etc.)
        data: Event data
        endpoint_url: WebSocket API endpoint URL (from environment if not provided)

    Returns:
        Number of clients notified successfully
    """
    if not endpoint_url:
        endpoint_url = os.environ.get('WEBSOCKET_API_ENDPOINT')

    if not endpoint_url:
        print("Error: WEBSOCKET_API_ENDPOINT not configured")
        return 0

    if not get_websocket_connections:
        # Silently skip if dynamodb_client not available
        return 0

    # Get all connections for this session
    connections = get_websocket_connections(session_id)

    if not connections:
        print(f"No WebSocket connections found for session {session_id}")
        return 0

    # Prepare message
    message = {
        'event': event_type,
        'session_id': session_id,
        'timestamp': int(time.time()),
        'data': data
    }

    # Extract status to root level if present (for frontend compatibility)
    if 'status' in data:
        message['status'] = data['status']

    # Send to all connections
    success_count = 0
    failed_connections = []

    for conn in connections:
        connection_id = conn['connection_id']

        if send_to_connection(connection_id, message, endpoint_url):
            success_count += 1
        else:
            failed_connections.append(connection_id)

    # Clean up failed connections from DynamoDB
    if failed_connections:
        from dynamodb_client import delete_websocket_connection
        for connection_id in failed_connections:
            try:
                delete_websocket_connection(connection_id)
            except Exception as e:
                print(f"Error deleting connection {connection_id}: {str(e)}")

    print(f"Notified {success_count}/{len(connections)} clients for session {session_id}")
    return success_count


def notify_processing_complete(
    session_id: str,
    result: Dict[str, Any],
    endpoint_url: str = None
) -> int:
    """
    Notify clients that video processing is complete.

    Args:
        session_id: Session identifier
        result: Processing result data
        endpoint_url: WebSocket API endpoint URL

    Returns:
        Number of clients notified
    """
    return notify_session_update(
        session_id=session_id,
        event_type='processing_complete',
        data={
            'status': 'completed',
            'clips_count': result.get('total_clips', 0),
            'video_info': result.get('video_info', {})
        },
        endpoint_url=endpoint_url
    )


def notify_processing_progress(
    session_id: str,
    status: str,
    progress: int = 0,
    message: str = None,
    endpoint_url: str = None
) -> int:
    """
    Notify clients of processing progress.

    Args:
        session_id: Session identifier
        status: Current processing status (downloading, transcribing, detecting, processing_clips)
        progress: Progress percentage (0-100)
        message: Optional progress message
        endpoint_url: WebSocket API endpoint URL

    Returns:
        Number of clients notified
    """
    data = {
        'status': status,  # ✅ Send status field for frontend
        'progress': progress
    }

    if message:
        data['message'] = message

    return notify_session_update(
        session_id=session_id,
        event_type='processing_progress',
        data=data,
        endpoint_url=endpoint_url
    )


def notify_processing_error(
    session_id: str,
    error: str,
    endpoint_url: str = None
) -> int:
    """
    Notify clients of processing error.

    Args:
        session_id: Session identifier
        error: Error message
        endpoint_url: WebSocket API endpoint URL

    Returns:
        Number of clients notified
    """
    return notify_session_update(
        session_id=session_id,
        event_type='processing_error',
        data={
            'status': 'failed',
            'error': error
        },
        endpoint_url=endpoint_url
    )


# Import time for timestamps
import time


# Export commonly used functions
__all__ = [
    'send_to_connection',
    'notify_session_update',
    'notify_processing_complete',
    'notify_processing_progress',
    'notify_processing_error'
]
