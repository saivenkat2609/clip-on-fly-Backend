"""
DynamoDB client for video session management.

Provides utilities for managing video sessions in DynamoDB with pagination support.
"""

import boto3
import os
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal


# DynamoDB client
dynamodb = boto3.resource('dynamodb')

# Table names from environment
VIDEO_SESSIONS_TABLE = os.environ.get('DYNAMODB_VIDEO_SESSIONS_TABLE', 'prod-video-sessions')
WEBSOCKET_CONNECTIONS_TABLE = os.environ.get('DYNAMODB_WEBSOCKET_CONNECTIONS_TABLE', 'prod-websocket-connections')

# Table references
video_sessions_table = dynamodb.Table(VIDEO_SESSIONS_TABLE)
websocket_connections_table = dynamodb.Table(WEBSOCKET_CONNECTIONS_TABLE)


class DecimalEncoder:
    """Helper to convert Decimal to int/float for JSON serialization."""

    @staticmethod
    def convert(obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        elif isinstance(obj, dict):
            return {k: DecimalEncoder.convert(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DecimalEncoder.convert(item) for item in obj]
        return obj


def create_video_session(user_id: str, session_id: str, **kwargs) -> bool:
    """
    Create a new video session in DynamoDB.

    Args:
        user_id: User identifier
        session_id: Session identifier
        **kwargs: Additional session attributes

    Returns:
        True if successful, False otherwise
    """
    try:
        item = {
            'user_id': user_id,
            'session_id': session_id,
            'status': kwargs.get('status', 'queued'),
            'created_at': int(time.time()),
            'expires_at': int(time.time()) + (3 * 24 * 3600),  # 3 days TTL
            **kwargs
        }

        video_sessions_table.put_item(Item=item)
        print(f"Created video session: {session_id}")
        return True

    except Exception as e:
        print(f"Error creating video session: {str(e)}")
        return False


def update_video_session(user_id: str, session_id: str, **kwargs) -> bool:
    """
    Update video session attributes.

    Args:
        user_id: User identifier
        session_id: Session identifier
        **kwargs: Attributes to update (e.g., status, execution_arn, error_message, etc.)
                  Note: execution_arn is stored internally for debugging but not exposed to clients

    Returns:
        True if successful, False otherwise
    """
    try:
        # Build update expression
        update_expressions = []
        expression_values = {}
        expression_names = {}

        for key, value in kwargs.items():
            safe_key = key.replace('-', '_')
            update_expressions.append(f"#{safe_key} = :{safe_key}")
            expression_values[f":{safe_key}"] = value
            expression_names[f"#{safe_key}"] = key

        update_expression = "SET " + ", ".join(update_expressions)

        video_sessions_table.update_item(
            Key={
                'user_id': user_id,
                'session_id': session_id
            },
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names
        )

        print(f"Updated video session: {session_id}")
        return True

    except Exception as e:
        print(f"Error updating video session: {str(e)}")
        return False


def get_video_session(user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get video session by ID.

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        Session data or None if not found
    """
    try:
        response = video_sessions_table.get_item(
            Key={
                'user_id': user_id,
                'session_id': session_id
            }
        )

        if 'Item' in response:
            return DecimalEncoder.convert(response['Item'])

        return None

    except Exception as e:
        print(f"Error getting video session: {str(e)}")
        return None


def query_user_videos(
    user_id: str,
    limit: int = 20,
    last_evaluated_key: Optional[Dict] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    Query videos for a user with pagination.

    Args:
        user_id: User identifier
        limit: Number of items per page
        last_evaluated_key: Pagination cursor from previous query
        status: Filter by status (optional)

    Returns:
        Dictionary with videos and pagination info
    """
    try:
        query_kwargs = {
            'KeyConditionExpression': 'user_id = :uid',
            'ExpressionAttributeValues': {':uid': user_id},
            'Limit': limit,
            'ScanIndexForward': False  # Sort by created_at DESC
        }

        # Add pagination cursor
        if last_evaluated_key:
            query_kwargs['ExclusiveStartKey'] = last_evaluated_key

        # Add status filter
        if status:
            query_kwargs['FilterExpression'] = '#status = :status'
            query_kwargs['ExpressionAttributeValues'][':status'] = status
            query_kwargs['ExpressionAttributeNames'] = {'#status': 'status'}

        response = video_sessions_table.query(**query_kwargs)

        videos = [DecimalEncoder.convert(item) for item in response.get('Items', [])]

        result = {
            'videos': videos,
            'count': len(videos),
            'has_more': 'LastEvaluatedKey' in response
        }

        if 'LastEvaluatedKey' in response:
            result['last_evaluated_key'] = response['LastEvaluatedKey']

        return result

    except Exception as e:
        print(f"Error querying user videos: {str(e)}")
        return {'videos': [], 'count': 0, 'has_more': False}


def query_videos_by_status(
    status: str,
    limit: int = 100,
    last_evaluated_key: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Query videos by status (for admin dashboard).

    Args:
        status: Status to filter by
        limit: Number of items per page
        last_evaluated_key: Pagination cursor

    Returns:
        Dictionary with videos and pagination info
    """
    try:
        query_kwargs = {
            'IndexName': 'status-created_at-index',
            'KeyConditionExpression': '#status = :status',
            'ExpressionAttributeNames': {'#status': 'status'},
            'ExpressionAttributeValues': {':status': status},
            'Limit': limit,
            'ScanIndexForward': False
        }

        if last_evaluated_key:
            query_kwargs['ExclusiveStartKey'] = last_evaluated_key

        response = video_sessions_table.query(**query_kwargs)

        videos = [DecimalEncoder.convert(item) for item in response.get('Items', [])]

        result = {
            'videos': videos,
            'count': len(videos),
            'has_more': 'LastEvaluatedKey' in response
        }

        if 'LastEvaluatedKey' in response:
            result['last_evaluated_key'] = response['LastEvaluatedKey']

        return result

    except Exception as e:
        print(f"Error querying videos by status: {str(e)}")
        return {'videos': [], 'count': 0, 'has_more': False}


def delete_video_session(user_id: str, session_id: str) -> bool:
    """
    Delete video session.

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        True if successful, False otherwise
    """
    try:
        video_sessions_table.delete_item(
            Key={
                'user_id': user_id,
                'session_id': session_id
            }
        )

        print(f"Deleted video session: {session_id}")
        return True

    except Exception as e:
        print(f"Error deleting video session: {str(e)}")
        return False


# WebSocket connection management

def save_websocket_connection(connection_id: str, session_id: str, user_id: str) -> bool:
    """
    Save WebSocket connection to DynamoDB.

    Args:
        connection_id: WebSocket connection ID
        session_id: Video session ID to subscribe to
        user_id: User identifier

    Returns:
        True if successful, False otherwise
    """
    try:
        websocket_connections_table.put_item(
            Item={
                'connection_id': connection_id,
                'session_id': session_id,
                'user_id': user_id,
                'connected_at': int(time.time()),
                'expires_at': int(time.time()) + (24 * 3600)  # 24 hours TTL
            }
        )

        print(f"Saved WebSocket connection: {connection_id}")
        return True

    except Exception as e:
        print(f"Error saving WebSocket connection: {str(e)}")
        return False


def get_websocket_connections(session_id: str) -> List[Dict[str, Any]]:
    """
    Get all WebSocket connections for a session.

    Args:
        session_id: Session identifier

    Returns:
        List of connection items
    """
    try:
        response = websocket_connections_table.query(
            IndexName='session_id-index',
            KeyConditionExpression='session_id = :sid',
            ExpressionAttributeValues={':sid': session_id}
        )

        return [DecimalEncoder.convert(item) for item in response.get('Items', [])]

    except Exception as e:
        print(f"Error getting WebSocket connections: {str(e)}")
        return []


def delete_websocket_connection(connection_id: str) -> bool:
    """
    Delete WebSocket connection.

    Args:
        connection_id: Connection identifier

    Returns:
        True if successful, False otherwise
    """
    try:
        websocket_connections_table.delete_item(
            Key={'connection_id': connection_id}
        )

        print(f"Deleted WebSocket connection: {connection_id}")
        return True

    except Exception as e:
        print(f"Error deleting WebSocket connection: {str(e)}")
        return False


# Export commonly used functions
__all__ = [
    'create_video_session',
    'update_video_session',
    'get_video_session',
    'query_user_videos',
    'query_videos_by_status',
    'delete_video_session',
    'save_websocket_connection',
    'get_websocket_connections',
    'delete_websocket_connection'
]
