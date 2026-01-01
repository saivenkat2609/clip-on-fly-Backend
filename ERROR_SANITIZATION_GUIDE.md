# HIGH PRIORITY FIX #24: Error Sanitization Guide

## Overview

This guide explains how to use the error sanitization utilities to prevent exposure of internal system details in error responses.

**Security Issues Prevented:**
- ✅ S3 bucket names exposure
- ✅ File paths and directory structure leaks
- ✅ AWS account IDs in errors
- ✅ API endpoints and service names
- ✅ Stack traces in production
- ✅ Debug information leakage

## Quick Start

### Import the utilities

```python
from shared.error_sanitizer import (
    sanitize_error_for_client,
    log_detailed_error,
    create_error_response,
    ErrorResponses
)
```

### Basic Usage

**Before (Insecure):**
```python
def lambda_handler(event, context):
    try:
        result = process_video('s3://my-secret-bucket/videos/secret.mp4')
        return {'statusCode': 200, 'body': json.dumps(result)}
    except Exception as e:
        # ❌ SECURITY ISSUE: Exposes internal details
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

**After (Secure):**
```python
def lambda_handler(event, context):
    try:
        result = process_video('s3://my-secret-bucket/videos/secret.mp4')
        return {'statusCode': 200, 'body': json.dumps(result)}
    except Exception as e:
        # ✅ SECURE: Logs full details to CloudWatch, returns sanitized message
        return create_error_response(
            e,
            context={'session_id': event.get('session_id')}
        )
```

## Usage Examples

### Example 1: Simple Error Handling

```python
def lambda_handler(event, context):
    session_id = event.get('session_id')

    try:
        # Your processing logic
        result = download_video(youtube_url)

        return {
            'statusCode': 200,
            'body': json.dumps({'result': result})
        }

    except Exception as e:
        # Automatically logs full error and returns sanitized version
        return create_error_response(
            e,
            status_code=500,
            context={'session_id': session_id, 'youtube_url': youtube_url}
        )
```

### Example 2: Specific Error Types

```python
def handle_video_download(session_id, youtube_url):
    try:
        video_path = download_from_youtube(youtube_url)
        return {'success': True, 'path': video_path}

    except VideoUnavailableError as e:
        return create_error_response(
            e,
            status_code=404,
            error_type='Video unavailable',  # Maps to friendly message
            context={'session_id': session_id}
        )

    except NetworkError as e:
        return create_error_response(
            e,
            status_code=503,
            error_type='ConnectionError',
            context={'session_id': session_id}
        )

    except Exception as e:
        return create_error_response(
            e,
            status_code=500,
            context={'session_id': session_id}
        )
```

### Example 3: Manual Sanitization

If you need more control:

```python
def lambda_handler(event, context):
    try:
        result = process_data()
        return {'statusCode': 200, 'body': json.dumps(result)}

    except Exception as e:
        # Log full error to CloudWatch
        log_detailed_error(
            e,
            context={'user_id': event.get('user_id')},
            prefix='[VIDEO-PROCESSOR]'
        )

        # Return sanitized error to client
        sanitized_message = sanitize_error_for_client(e)

        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': sanitized_message})
        }
```

### Example 4: Pre-defined Responses

For common scenarios, use pre-defined responses:

```python
from shared.error_sanitizer import ErrorResponses

def handle_request(event, context):
    user_id = event.get('user_id')
    session_id = event.get('session_id')

    # Check authorization
    if not user_id:
        return ErrorResponses.unauthorized()

    # Check ownership
    if not owns_session(user_id, session_id):
        return ErrorResponses.forbidden()

    # Check rate limit
    if is_rate_limited(user_id):
        return ErrorResponses.rate_limit_exceeded()

    # Validate input
    if not is_valid_url(event.get('youtube_url')):
        return ErrorResponses.invalid_input('YouTube URL')

    try:
        result = process_video(session_id)
        return {'statusCode': 200, 'body': json.dumps(result)}

    except ResourceNotFound:
        return ErrorResponses.video_not_found()

    except ServiceUnavailable:
        return ErrorResponses.service_unavailable()

    except Exception as e:
        return create_error_response(e, context={'session_id': session_id})
```

## Integration with Existing Lambda Functions

### Step 1: Add error_sanitizer.py to Lambda layer

The error sanitizer is in `shared/` directory, so it needs to be included in your Lambda layer or deployment package.

**Option A: Lambda Layer (Recommended)**
```bash
# Add to existing shared layer
cd opus-clip-cloud/src
zip -r shared-layer.zip shared/
aws lambda publish-layer-version \
    --layer-name shared-utilities \
    --zip-file fileb://shared-layer.zip \
    --compatible-runtimes python3.11
```

**Option B: Include in deployment package**
```bash
# Copy shared module to each Lambda function
cp -r shared/ api-gateway/
cp -r shared/ download/
cp -r shared/ process-clip/
# etc.
```

### Step 2: Update Lambda functions

Update each Lambda function's error handling:

**api-gateway/lambda_function.py:**
```python
from shared.error_sanitizer import create_error_response, ErrorResponses

def lambda_handler(event, context):
    try:
        # Existing logic...
        pass

    except Exception as e:
        return create_error_response(
            e,
            context={'path': event.get('path'), 'method': event.get('httpMethod')}
        )
```

**download/lambda_function.py:**
```python
from shared.error_sanitizer import create_error_response

def lambda_handler(event, context):
    session_id = event['session_id']
    youtube_url = event['youtube_url']

    try:
        # Existing download logic...
        pass

    except Exception as e:
        return create_error_response(
            e,
            context={'session_id': session_id, 'youtube_url': youtube_url}
        )
```

## What Gets Sanitized

### Sensitive Information Removed

| Pattern | Example | Sanitized |
|---------|---------|-----------|
| S3 Buckets | `s3://my-bucket/path` | `s3://[REDACTED]` |
| File Paths | `/tmp/session_123/video.mp4` | `/tmp/[REDACTED]` |
| Account IDs | `123456789012` | `[AWS_ACCOUNT_ID]` |
| IP Addresses | `192.168.1.1` | `[IP_ADDRESS]` |
| URLs | `https://api.example.com/v1/process` | `https://[ENDPOINT]/[PATH]` |
| ARNs | `arn:aws:lambda:us-east-1:123:function:fn` | `arn:aws:[REDACTED]` |
| API Keys | `api_key=abc123xyz` | `[API_KEY_REDACTED]` |

### Error Message Mapping

| Technical Error | User-Friendly Message |
|----------------|----------------------|
| `NoSuchKey` | "The requested file was not found" |
| `AccessDenied` | "Permission denied to access the resource" |
| `Video unavailable` | "The video is unavailable or private" |
| `ConnectionError` | "Unable to connect to the service" |
| `TimeoutError` | "The request timed out" |

## CloudWatch Logging

Error sanitization logs **full details** to CloudWatch for debugging:

```
[ERROR] Exception occurred: FileNotFoundError
[ERROR] Message: [Errno 2] No such file or directory: '/tmp/abc123/video.mp4'
[ERROR] Context: {'session_id': 'abc-123-def', 'user_id': 'user_456'}
[ERROR] Full traceback:
Traceback (most recent call last):
  File "/var/task/lambda_function.py", line 125, in process_video
    with open('/tmp/abc123/video.mp4', 'rb') as f:
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/abc123/video.mp4'
```

**Client receives:** `"An error occurred while processing your request. Please try again."`

## Testing

### Test 1: Verify Sanitization

```python
# Test script
from shared.error_sanitizer import sanitize_error_for_client

# Test S3 bucket sanitization
error = Exception("Failed to upload to s3://my-secret-bucket/videos/private.mp4")
result = sanitize_error_for_client(error)
assert "my-secret-bucket" not in result
print(f"✓ S3 bucket sanitized: {result}")

# Test file path sanitization
error = Exception("File not found: /tmp/user_123/session_456/video.mp4")
result = sanitize_error_for_client(error)
assert "user_123" not in result
print(f"✓ File path sanitized: {result}")

# Test account ID sanitization
error = Exception("ARN: arn:aws:lambda:us-east-1:123456789012:function:my-func")
result = sanitize_error_for_client(error)
assert "123456789012" not in result
print(f"✓ Account ID sanitized: {result}")
```

### Test 2: Verify CloudWatch Logging

```python
# Test full error logging
from shared.error_sanitizer import log_detailed_error

try:
    raise Exception("Test error with sensitive data: s3://bucket/key")
except Exception as e:
    log_detailed_error(e, context={'test': True})

# Check CloudWatch Logs - full error should be there
# Client response should be sanitized
```

## Migration Checklist

- [ ] Add `error_sanitizer.py` to shared Lambda layer
- [ ] Update `api-gateway` Lambda error handling
- [ ] Update `download` Lambda error handling
- [ ] Update `transcribe` Lambda error handling
- [ ] Update `detect-clips` Lambda error handling
- [ ] Update `process-clip` Lambda error handling
- [ ] Update `finalize` Lambda error handling
- [ ] Update `upload-api-gateway` Lambda error handling
- [ ] Test all error scenarios
- [ ] Verify sensitive data not in client responses
- [ ] Verify full details in CloudWatch Logs
- [ ] Update monitoring/alerting queries

## Best Practices

1. **Always use create_error_response()** for consistency
2. **Include context** in error logs for debugging
3. **Use specific error types** when possible for better UX
4. **Test error paths** to ensure sanitization works
5. **Monitor CloudWatch** for full error details
6. **Never log sensitive data** even in CloudWatch (passwords, tokens, PII)

## Security Benefits

**Before sanitization:**
```json
{
  "error": "Failed to upload /tmp/user_12345/session_abc/video.mp4 to s3://prod-videos-bucket/users/12345/abc/video.mp4 - AccessDenied: User arn:aws:iam::123456789012:user/lambda-exec doesn't have permission"
}
```

**After sanitization:**
```json
{
  "error": "Permission denied to access the resource"
}
```

**CloudWatch logs** still contain full details for debugging!

## Additional Resources

- [OWASP Error Handling Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [CWE-209: Information Exposure Through Error Message](https://cwe.mitre.org/data/definitions/209.html)
