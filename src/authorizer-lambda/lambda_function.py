"""
Lambda Authorizer for API Gateway
Verifies Supabase JWT tokens using JWKS (asymmetric signing keys).
"""

import json
import os
import time
import urllib.request
import urllib.error
import jwt
from jwt import PyJWKClient

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')

# JWKS client — caches keys automatically
_jwks_client = None


def get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        print(f'[Authorizer] Initialising JWKS client for {jwks_url}')
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def verify_supabase_token(token):
    """
    Verify Supabase JWT using JWKS public key (ES256/RS256).
    """
    try:
        token_parts = token.split('.')
        if len(token_parts) != 3:
            raise Exception('Invalid token format - must have 3 parts')

        if not SUPABASE_URL:
            raise Exception('SUPABASE_URL not configured')

        client = get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)

        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256', 'ES256'],
            audience='authenticated',
        )

        current_time = int(time.time())

        if 'nbf' in decoded and decoded['nbf'] > current_time:
            raise Exception('Token not yet valid (nbf claim)')

        if 'iat' in decoded and decoded['iat'] > current_time + 300:
            raise Exception('Token issued in future (iat claim invalid)')

        user_id = decoded.get('sub')
        if not user_id:
            raise Exception('Token missing user ID')

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
    if context:
        policy['context'] = context
    return policy


def lambda_handler(event, context):
    try:
        api_version = event.get('version', '1.0')

        if api_version == '2.0':
            print('[Authorizer] Using HTTP API v2 format')
            identity_source = event.get('identitySource', [])
            if identity_source and len(identity_source) > 0:
                auth_token = identity_source[0]
            else:
                headers = event.get('headers', {})
                auth_token = headers.get('authorization') or headers.get('Authorization', '')
        else:
            print('[Authorizer] Using REST API v1 format')
            auth_token = event.get('authorizationToken', '')

        if not auth_token:
            print('[Authorizer] No authorization token provided')
            if api_version == '2.0':
                return {'isAuthorized': False}
            else:
                raise Exception('Unauthorized')

        token = auth_token.replace('Bearer ', '').strip()

        if not token:
            print('[Authorizer] Empty token after Bearer removal')
            if api_version == '2.0':
                return {'isAuthorized': False}
            else:
                raise Exception('Unauthorized')

        decoded = verify_supabase_token(token)

        user_id = decoded.get('sub')
        email = decoded.get('email', '')
        email_verified = True
        provider = decoded.get('app_metadata', {}).get('provider', '')

        print(f'[Authorizer] Authorized user: {user_id}, email: {email}, provider: {provider}')

        if api_version == '2.0':
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
        if event.get('version') == '2.0':
            return {'isAuthorized': False}
        else:
            raise Exception('Unauthorized')


if __name__ == '__main__':
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
