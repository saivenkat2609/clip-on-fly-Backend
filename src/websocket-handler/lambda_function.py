"""
WebSocket Handler Lambda Function

Handles WebSocket connections, disconnections, and subscriptions.
"""

import boto3
import json
import os
import sys
import time

# Add shared directory to path
sys.path.append('/opt/python')  # Lambda layer path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

try:
    from dynamodb_client import (
        save_websocket_connection,
        delete_websocket_connection
    )
    DYNAMODB_CLIENT_AVAILABLE = True
except ImportError:
    # Fallback if shared module not available
    print("Warning: Could not import dynamodb_client, using inline functions")
    DYNAMODB_CLIENT_AVAILABLE = False

    # Inline DynamoDB functions as fallback
    dynamodb = boto3.resource('dynamodb')
    WEBSOCKET_CONNECTIONS_TABLE = os.environ.get('DYNAMODB_WEBSOCKET_CONNECTIONS_TABLE', 'prod-websocket-connections')
    websocket_connections_table = dynamodb.Table(WEBSOCKET_CONNECTIONS_TABLE)

    def save_websocket_connection(connection_id: str, session_id: str, user_id: str) -> bool:
        """Save WebSocket connection to DynamoDB."""
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

    def delete_websocket_connection(connection_id: str) -> bool:
        """Delete WebSocket connection from DynamoDB."""
        try:
            websocket_connections_table.delete_item(
                Key={'connection_id': connection_id}
            )
            print(f"Deleted WebSocket connection: {connection_id}")
            return True
        except Exception as e:
            print(f"Error deleting WebSocket connection: {str(e)}")
            return False


def lambda_handler(event, context):
    """
    Handle WebSocket events.

    Routes:
    - $connect: New WebSocket connection
    - $disconnect: WebSocket disconnection
    - subscribe: Subscribe to session updates
    - ping: Heartbeat
    """
    route_key = event['requestContext']['routeKey']
    connection_id = event['requestContext']['connectionId']

    print(f"WebSocket event: {route_key} for connection {connection_id}")

    if route_key == '$connect':
        return handle_connect(event, context)
    elif route_key == '$disconnect':
        return handle_disconnect(event, context)
    elif route_key == 'subscribe':
        return handle_subscribe(event, context)
    elif route_key == 'ping':
        return handle_ping(event, context)

    return {
        'statusCode': 400,
        'body': json.dumps({'error': 'Unknown route'})
    }


def handle_connect(event, context):
    """
    Handle new WebSocket connection.

    Query parameters can include authentication token.
    """
    connection_id = event['requestContext']['connectionId']

    # Extract query parameters
    query_params = event.get('queryStringParameters', {}) or {}

    print(f"New WebSocket connection: {connection_id}")

    # TODO: Validate authentication token from query params
    # auth_token = query_params.get('token')

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Connected', 'connection_id': connection_id})
    }


def handle_disconnect(event, context):
    """
    Handle WebSocket disconnection.

    Clean up connection from DynamoDB.
    """
    connection_id = event['requestContext']['connectionId']

    print(f"WebSocket disconnection: {connection_id}")

    # Delete connection from DynamoDB
    try:
        delete_websocket_connection(connection_id)
    except Exception as e:
        print(f"Error deleting connection: {str(e)}")

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Disconnected'})
    }


def handle_subscribe(event, context):
    """
    Handle subscription to session updates.

    Message format:
    {
        "action": "subscribe",
        "session_id": "session_id_here",
        "user_id": "user_id_here"
    }
    """
    connection_id = event['requestContext']['connectionId']
    domain_name = event['requestContext']['domainName']
    stage = event['requestContext']['stage']

    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        session_id = body.get('session_id')
        user_id = body.get('user_id', 'anonymous')  # Make user_id optional

        if not session_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'session_id required'})
            }

        # Save connection with session subscription
        save_websocket_connection(connection_id, session_id, user_id)

        print(f"✅ Subscribed connection {connection_id} to session {session_id} for user {user_id}")

        # Send confirmation message back to client
        try:
            # Create API Gateway Management API client
            api_client = boto3.client(
                'apigatewaymanagementapi',
                endpoint_url=f"https://{domain_name}/{stage}"
            )

            # Send subscription confirmation
            confirmation = {
                'event': 'subscribed',
                'session_id': session_id,
                'message': 'Successfully subscribed to session updates',
                'timestamp': int(time.time())
            }

            api_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(confirmation).encode('utf-8')
            )

            print(f"✅ Sent subscription confirmation to {connection_id}")

        except Exception as send_error:
            print(f"⚠️ Could not send confirmation (non-fatal): {str(send_error)}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Subscribed',
                'session_id': session_id
            })
        }

    except Exception as e:
        print(f"❌ Error in subscribe: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def handle_ping(event, context):
    """
    Handle heartbeat ping.

    Responds with pong to keep connection alive.
    """
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'pong'})
    }
