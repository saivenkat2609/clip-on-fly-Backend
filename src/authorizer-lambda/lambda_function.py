"""
Lambda Authorizer for API Gateway
Verifies Firebase ID tokens and returns IAM policy with verified user context

This authorizer runs before every API request and ensures that:
1. The request has a valid Firebase JWT token
2. The token is properly signed by Firebase
3. The token hasn't expired
4. The user context is passed to downstream Lambda functions

Security: Caches Firebase public keys for 1 hour to improve performance
"""

import json
import os
import jwt
import requests
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.hazmat.backends import default_backend

# Firebase configuration
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'reframe-1e182')
FIREBASE_KEYS_URL = 'https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com'

# Cache for Firebase public keys (improves performance)
_keys_cache = {'keys': None, 'expires': None}


def get_firebase_public_keys():
    """
    Fetch Firebase public keys for JWT verification
    Caches keys for 1 hour to reduce API calls

    Returns:
        dict: Firebase public keys mapped by key ID
    """
    now = datetime.utcnow()

    # Return cached keys if still valid
    if _keys_cache['keys'] and _keys_cache['expires'] and now < _keys_cache['expires']:
        print('[Authorizer] Using cached Firebase public keys')
        return _keys_cache['keys']

    try:
        print('[Authorizer] Fetching fresh Firebase public keys')
        response = requests.get(FIREBASE_KEYS_URL, timeout=5)
        response.raise_for_status()
        keys = response.json()

        # Cache keys for 1 hour
        _keys_cache['keys'] = keys
        _keys_cache['expires'] = now + timedelta(hours=1)

        return keys
    except Exception as e:
        print(f'[Authorizer] Error fetching public keys: {str(e)}')
        # If cache exists, use it even if expired (fail open for availability)
        if _keys_cache['keys']:
            print('[Authorizer] Using expired cache due to fetch error')
            return _keys_cache['keys']
        raise


def verify_firebase_token(token):
    """
    Verify Firebase ID token signature and claims

    Args:
        token (str): Firebase ID token from Authorization header

    Returns:
        dict: Decoded token with user information

    Raises:
        Exception: If token is invalid, expired, or verification fails
    """
    try:
        # Decode header to get key ID (kid)
        header = jwt.get_unverified_header(token)
        kid = header.get('kid')

        if not kid:
            raise Exception('Token missing key ID')

        # Get Firebase public keys
        public_keys = get_firebase_public_keys()

        if kid not in public_keys:
            raise Exception(f'Invalid key ID: {kid}')

        # Load the X.509 certificate and extract public key
        cert_str = public_keys[kid]
        cert = x509.load_pem_x509_certificate(cert_str.encode('utf-8'), default_backend())
        public_key = cert.public_key()

        # Verify token signature and claims
        decoded = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience=FIREBASE_PROJECT_ID,
            issuer=f'https://securetoken.google.com/{FIREBASE_PROJECT_ID}'
        )

        # Validate required claims
        # Firebase tokens use 'sub' (standard JWT) as the user ID
        user_id = decoded.get('sub') or decoded.get('uid')
        if not user_id:
            raise Exception('Token missing user ID')

        # Add 'uid' alias for compatibility
        decoded['uid'] = user_id

        print(f'[Authorizer] Token verified for user: {user_id}')
        return decoded

    except jwt.ExpiredSignatureError:
        print('[Authorizer] Token expired')
        raise Exception('Token expired')
    except jwt.InvalidTokenError as e:
        print(f'[Authorizer] Invalid token: {str(e)}')
        raise Exception('Invalid token')
    except Exception as e:
        print(f'[Authorizer] Token verification failed: {str(e)}')
        raise


def generate_policy(principal_id, effect, resource, context=None):
    """
    Generate IAM policy for API Gateway

    Args:
        principal_id (str): User ID
        effect (str): 'Allow' or 'Deny'
        resource (str): API Gateway ARN
        context (dict): Additional context to pass to Lambda function

    Returns:
        dict: IAM policy document
    """
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource
            }]
        }
    }

    # Add context if provided (accessible in Lambda as event['requestContext']['authorizer'])
    if context:
        policy['context'] = context

    return policy


def lambda_handler(event, context):
    """
    Lambda Authorizer handler
    Supports both REST API (v1) and HTTP API (v2) formats

    Args:
        event (dict): API Gateway authorizer event
        context (object): Lambda context

    Returns:
        dict: IAM policy (REST API) or Simple response (HTTP API)

    Raises:
        Exception: Returns 401 Unauthorized if token verification fails
    """
    try:
        # Detect API Gateway type and extract token
        api_version = event.get('version', '1.0')

        if api_version == '2.0':
            # HTTP API v2 format
            print('[Authorizer] Using HTTP API v2 format')

            # Token comes from identitySource or headers
            identity_source = event.get('identitySource', [])
            if identity_source and len(identity_source) > 0:
                auth_token = identity_source[0]
            else:
                # Fallback to headers
                headers = event.get('headers', {})
                auth_token = headers.get('authorization') or headers.get('Authorization', '')
        else:
            # REST API v1 format (TOKEN authorizer)
            print('[Authorizer] Using REST API v1 format')
            auth_token = event.get('authorizationToken', '')

        if not auth_token:
            print('[Authorizer] No authorization token provided')
            print(f'[Authorizer] Event keys: {list(event.keys())}')
            if api_version == '2.0':
                # HTTP API v2 Simple response
                return {
                    'isAuthorized': False
                }
            else:
                raise Exception('Unauthorized')

        # Remove 'Bearer ' prefix if present
        token = auth_token.replace('Bearer ', '').strip()

        if not token:
            print('[Authorizer] Empty token after Bearer removal')
            if api_version == '2.0':
                return {
                    'isAuthorized': False
                }
            else:
                raise Exception('Unauthorized')

        # Verify Firebase token
        decoded = verify_firebase_token(token)

        # Extract user information
        user_id = decoded['uid']
        email = decoded.get('email', '')
        email_verified = decoded.get('email_verified', False)
        provider = decoded.get('firebase', {}).get('sign_in_provider', '')

        print(f'[Authorizer] Authorized user: {user_id}, email: {email}, verified: {email_verified}')

        # Return appropriate response format
        if api_version == '2.0':
            # HTTP API v2 Simple response
            return {
                'isAuthorized': True,
                'context': {
                    'userId': user_id,
                    'email': email,
                    'emailVerified': str(email_verified),
                    'provider': provider
                }
            }
        else:
            # REST API v1 IAM policy response
            return generate_policy(
                user_id,
                'Allow',
                event['methodArn'],
                context={
                    'userId': user_id,
                    'email': email,
                    'emailVerified': str(email_verified),
                    'provider': provider
                }
            )

    except Exception as e:
        print(f'[Authorizer] Authorization failed: {str(e)}')
        # Return appropriate error format
        if event.get('version') == '2.0':
            return {
                'isAuthorized': False
            }
        else:
            raise Exception('Unauthorized')


# For local testing
if __name__ == '__main__':
    # Test event
    test_event = {
        'type': 'TOKEN',
        'authorizationToken': 'Bearer test-token',
        'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef123/prod/POST/process'
    }

    try:
        result = lambda_handler(test_event, None)
        print('Success:', json.dumps(result, indent=2))
    except Exception as e:
        print('Error:', str(e))
