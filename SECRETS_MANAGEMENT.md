# Secrets Management Migration Guide

## Overview

This document provides a comprehensive guide for migrating from environment variable-based secrets to AWS Secrets Manager, addressing High Priority Issue #8 from PROJECT_IMPROVEMENTS.md.

## Current State and Risks

### Current Implementation
Currently, all sensitive credentials are stored as plaintext environment variables in:
- `.env` files (local development)
- AWS Lambda environment variables (production)
- Serverless Framework configuration files

### Security Risks
1. **Plaintext Storage**: Secrets are visible in AWS Console, CloudFormation templates, and deployment logs
2. **No Audit Trail**: No tracking of who accessed which secrets and when
3. **No Rotation**: Manual secret rotation is error-prone and rarely done
4. **Broad Access**: Anyone with Lambda read permissions can view all secrets
5. **Version Control Risk**: `.env` files may accidentally be committed to git

### Affected Secrets
The following secrets need to be migrated:
- `GROQ_API_KEY` - AI model API key
- `FIREBASE_WEB_API_KEY` - Firebase authentication (should be replaced with service account)
- `ASSEMBLYAI_API_KEY` - Transcription service
- `DEEPGRAM_API_KEY` - Alternative transcription service
- `REDIS_PASSWORD` - Cache authentication (if applicable)
- Any database credentials or connection strings

---

## Migration Strategy

### Phase 1: AWS Secrets Manager Setup (Manual - AWS Console)

#### Step 1: Create Secrets in AWS Secrets Manager

For each secret, create an entry in AWS Secrets Manager:

```bash
# Example: Store Groq API Key
aws secretsmanager create-secret \
    --name prod/opus-clip/groq-api-key \
    --description "Groq API Key for AI clip detection" \
    --secret-string '{"api_key":"YOUR_ACTUAL_KEY_HERE"}' \
    --region us-east-1

# Example: Store AssemblyAI API Key
aws secretsmanager create-secret \
    --name prod/opus-clip/assemblyai-api-key \
    --description "AssemblyAI API Key for transcription" \
    --secret-string '{"api_key":"YOUR_ACTUAL_KEY_HERE"}' \
    --region us-east-1

# Example: Store Deepgram API Key
aws secretsmanager create-secret \
    --name prod/opus-clip/deepgram-api-key \
    --description "Deepgram API Key for transcription" \
    --secret-string '{"api_key":"YOUR_ACTUAL_KEY_HERE"}' \
    --region us-east-1
```

**Naming Convention:**
- Format: `{environment}/{application}/{secret-name}`
- Examples:
  - `prod/opus-clip/groq-api-key`
  - `dev/opus-clip/groq-api-key`
  - `staging/opus-clip/groq-api-key`

#### Step 2: Configure IAM Policies

Create a least-privilege IAM policy for each Lambda function to access only the secrets it needs.

**Example: Policy for Clip Detection Lambda (needs Groq API)**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:prod/opus-clip/groq-api-key-*"
      ]
    }
  ]
}
```

**Example: Policy for Transcription Lambda (needs AssemblyAI and Deepgram)**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:prod/opus-clip/assemblyai-api-key-*",
        "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:prod/opus-clip/deepgram-api-key-*"
      ]
    }
  ]
}
```

#### Step 3: Update Serverless Framework Configuration

Add IAM permissions to each Lambda function in `serverless.yml`:

```yaml
functions:
  clip-detection:
    handler: lambda_function.lambda_handler
    # ... other configuration ...
    iamRoleStatements:
      - Effect: Allow
        Action:
          - secretsmanager:GetSecretValue
          - secretsmanager:DescribeSecret
        Resource:
          - arn:aws:secretsmanager:${aws:region}:${aws:accountId}:secret:prod/opus-clip/groq-api-key-*

  transcribe:
    handler: lambda_function.lambda_handler
    # ... other configuration ...
    iamRoleStatements:
      - Effect: Allow
        Action:
          - secretsmanager:GetSecretValue
          - secretsmanager:DescribeSecret
        Resource:
          - arn:aws:secretsmanager:${aws:region}:${aws:accountId}:secret:prod/opus-clip/assemblyai-api-key-*
          - arn:aws:secretsmanager:${aws:region}:${aws:accountId}:secret:prod/opus-clip/deepgram-api-key-*
```

---

### Phase 2: Code Changes (Implementation)

#### Create Shared Secrets Helper Module

Create `opus-clip-cloud/src/shared/secrets_manager.py`:

```python
"""
Secrets Manager Helper
Provides caching and error handling for AWS Secrets Manager access
"""

import boto3
import json
import os
from typing import Dict, Optional
from datetime import datetime, timedelta

# Initialize Secrets Manager client
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# In-memory cache to avoid repeated API calls (15 minute TTL)
_secrets_cache: Dict[str, Dict] = {}


def get_secret(secret_name: str, cache_ttl_minutes: int = 15) -> Optional[str]:
    """
    Retrieve secret from AWS Secrets Manager with caching

    Args:
        secret_name: Full ARN or name of the secret (e.g., 'prod/opus-clip/groq-api-key')
        cache_ttl_minutes: How long to cache the secret in memory (default 15 minutes)

    Returns:
        Secret value as string, or None if retrieval fails

    Example:
        groq_key = get_secret('prod/opus-clip/groq-api-key')
        if groq_key:
            api_data = json.loads(groq_key)
            GROQ_API_KEY = api_data['api_key']
    """
    current_time = datetime.now()

    # Check cache first
    if secret_name in _secrets_cache:
        cached_data = _secrets_cache[secret_name]
        if cached_data['expires_at'] > current_time:
            print(f"[Secrets] Using cached value for {secret_name}")
            return cached_data['value']
        else:
            print(f"[Secrets] Cache expired for {secret_name}, fetching new value")
            del _secrets_cache[secret_name]

    # Fetch from Secrets Manager
    try:
        print(f"[Secrets] Fetching secret: {secret_name}")
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_value = response['SecretString']

        # Cache the secret
        _secrets_cache[secret_name] = {
            'value': secret_value,
            'expires_at': current_time + timedelta(minutes=cache_ttl_minutes)
        }

        print(f"[Secrets] Successfully fetched and cached {secret_name}")
        return secret_value

    except secrets_client.exceptions.ResourceNotFoundException:
        print(f"[Secrets] ERROR: Secret not found: {secret_name}")
        return None
    except secrets_client.exceptions.InvalidRequestException as e:
        print(f"[Secrets] ERROR: Invalid request for {secret_name}: {str(e)}")
        return None
    except secrets_client.exceptions.InvalidParameterException as e:
        print(f"[Secrets] ERROR: Invalid parameter for {secret_name}: {str(e)}")
        return None
    except Exception as e:
        print(f"[Secrets] ERROR: Failed to fetch {secret_name}: {str(e)}")
        return None


def get_api_key(secret_name: str, key_field: str = 'api_key') -> Optional[str]:
    """
    Convenience function to get API key from a JSON secret

    Args:
        secret_name: Name of the secret
        key_field: JSON field name containing the key (default: 'api_key')

    Returns:
        API key string or None if not found

    Example:
        GROQ_API_KEY = get_api_key('prod/opus-clip/groq-api-key')
    """
    secret_json = get_secret(secret_name)
    if not secret_json:
        return None

    try:
        secret_data = json.loads(secret_json)
        return secret_data.get(key_field)
    except json.JSONDecodeError:
        print(f"[Secrets] ERROR: Secret {secret_name} is not valid JSON")
        return None


def clear_cache():
    """Clear the secrets cache (useful for testing or forced refresh)"""
    global _secrets_cache
    _secrets_cache = {}
    print("[Secrets] Cache cleared")
```

#### Update Lambda Functions to Use Secrets Manager

**Example 1: Clip Detection Lambda**

Update `opus-clip-cloud/src/clip-detection/lambda_function.py`:

```python
import os
import sys
import json

# Add shared modules to path
sys.path.insert(0, '/opt/python')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Import secrets manager
try:
    from secrets_manager import get_api_key
    SECRETS_MANAGER_ENABLED = True
except ImportError as e:
    print(f"[ClipDetection] Warning: Secrets manager not available: {e}")
    SECRETS_MANAGER_ENABLED = False

# Get Groq API Key
if SECRETS_MANAGER_ENABLED:
    # Try to get from Secrets Manager first
    GROQ_API_KEY = get_api_key('prod/opus-clip/groq-api-key')
    if not GROQ_API_KEY:
        print("[ClipDetection] WARNING: Failed to fetch from Secrets Manager, falling back to environment variable")
        GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
else:
    # Fall back to environment variable
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in Secrets Manager or environment variables")

# Rest of your Lambda code...
def lambda_handler(event, context):
    # Use GROQ_API_KEY for API calls
    pass
```

**Example 2: Transcription Lambda**

Update `opus-clip-cloud/src/transcribe/lambda_function.py`:

```python
import os
import sys
import json

# Add shared modules to path
sys.path.insert(0, '/opt/python')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Import secrets manager
try:
    from secrets_manager import get_api_key
    SECRETS_MANAGER_ENABLED = True
except ImportError as e:
    print(f"[Transcribe] Warning: Secrets manager not available: {e}")
    SECRETS_MANAGER_ENABLED = False

# Get API Keys
if SECRETS_MANAGER_ENABLED:
    ASSEMBLYAI_API_KEY = get_api_key('prod/opus-clip/assemblyai-api-key')
    DEEPGRAM_API_KEY = get_api_key('prod/opus-clip/deepgram-api-key')

    # Fall back to environment variables if Secrets Manager fails
    if not ASSEMBLYAI_API_KEY:
        print("[Transcribe] WARNING: AssemblyAI key not in Secrets Manager, using env var")
        ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
    if not DEEPGRAM_API_KEY:
        print("[Transcribe] WARNING: Deepgram key not in Secrets Manager, using env var")
        DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')
else:
    ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
    DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')

# Validate at least one transcription service is available
if not ASSEMBLYAI_API_KEY and not DEEPGRAM_API_KEY:
    raise ValueError("No transcription API keys found in Secrets Manager or environment variables")

# Rest of your Lambda code...
```

---

### Phase 3: Secret Rotation Setup

#### Enable Automatic Rotation (90-day cycle)

For each secret, enable automatic rotation:

```bash
# Enable rotation for Groq API key
aws secretsmanager rotate-secret \
    --secret-id prod/opus-clip/groq-api-key \
    --rotation-lambda-arn arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:SecretsManagerRotation \
    --rotation-rules AutomaticallyAfterDays=90 \
    --region us-east-1
```

#### Create Rotation Lambda (Optional - for custom rotation logic)

If you need custom rotation logic (e.g., calling an API to generate new keys), create a rotation Lambda:

```python
"""
Secrets Rotation Lambda
Handles automatic rotation of API keys in Secrets Manager
"""

import boto3
import json
import os

secrets_client = boto3.client('secretsmanager')

def lambda_handler(event, context):
    """
    Handles secret rotation for AWS Secrets Manager

    Rotation steps:
    1. createSecret - Generate new API key
    2. setSecret - Store new key in Secrets Manager
    3. testSecret - Verify new key works
    4. finishSecret - Mark rotation complete
    """
    arn = event['SecretId']
    token = event['ClientRequestToken']
    step = event['Step']

    # Get secret metadata
    metadata = secrets_client.describe_secret(SecretId=arn)

    if step == "createSecret":
        create_secret(secrets_client, arn, token)
    elif step == "setSecret":
        set_secret(secrets_client, arn, token)
    elif step == "testSecret":
        test_secret(secrets_client, arn, token)
    elif step == "finishSecret":
        finish_secret(secrets_client, arn, token)
    else:
        raise ValueError("Invalid step parameter")


def create_secret(client, arn, token):
    """Generate new secret value"""
    # For API keys, you'd call the provider's API to generate a new key
    # This is service-specific - see provider documentation
    print(f"[Rotation] Creating new secret for {arn}")

    # Example: Generate new random API key (replace with actual API call)
    # new_key = call_provider_api_to_generate_key()
    # new_secret = json.dumps({"api_key": new_key})

    # For now, just log that rotation is needed
    print(f"[Rotation] WARNING: Manual key rotation required for {arn}")


def set_secret(client, arn, token):
    """Store new secret value"""
    print(f"[Rotation] Setting new secret for {arn}")


def test_secret(client, arn, token):
    """Verify new secret works"""
    print(f"[Rotation] Testing new secret for {arn}")


def finish_secret(client, arn, token):
    """Mark rotation complete"""
    print(f"[Rotation] Finishing rotation for {arn}")
    client.finish_secret_rotation(
        SecretId=arn,
        ClientRequestToken=token
    )
```

---

## Deployment Steps

### Step-by-Step Migration Process

#### 1. Pre-Deployment Preparation

1. **Document all current secrets**:
   ```bash
   # List all environment variables in Lambda functions
   aws lambda list-functions --query 'Functions[*].[FunctionName,Environment.Variables]' --output table
   ```

2. **Create secrets in AWS Secrets Manager** (as shown in Phase 1, Step 1)

3. **Test secret retrieval**:
   ```bash
   aws secretsmanager get-secret-value --secret-id prod/opus-clip/groq-api-key
   ```

#### 2. Deploy Shared Secrets Module

1. **Add secrets_manager.py to Lambda layers**:
   ```bash
   cd opus-clip-cloud/src/shared
   # Create deployment package
   mkdir -p python
   cp secrets_manager.py python/
   zip -r secrets-layer.zip python/

   # Upload to Lambda layer
   aws lambda publish-layer-version \
       --layer-name opus-clip-secrets-manager \
       --description "Secrets Manager helper for Opus Clip" \
       --zip-file fileb://secrets-layer.zip \
       --compatible-runtimes python3.9 python3.10 python3.11
   ```

2. **Update serverless.yml to include the layer**:
   ```yaml
   layers:
     secretsManager:
       path: layers/secrets-manager
       name: ${self:service}-secrets-manager
       description: Secrets Manager helper
       compatibleRuntimes:
         - python3.9
         - python3.10
   ```

#### 3. Deploy Code Changes

1. **Update Lambda functions** with secrets manager integration (as shown in Phase 2)

2. **Deploy backend**:
   ```bash
   cd opus-clip-cloud
   serverless deploy --stage prod
   ```

3. **Verify deployment**:
   ```bash
   # Check Lambda logs for successful secret retrieval
   aws logs tail /aws/lambda/opus-clip-clip-detection --follow
   ```

#### 4. Remove Environment Variables (After Verification)

Once you've verified secrets are being fetched successfully:

1. **Remove secrets from serverless.yml**:
   ```yaml
   # BEFORE (remove these):
   environment:
     GROQ_API_KEY: ${env:GROQ_API_KEY}
     ASSEMBLYAI_API_KEY: ${env:ASSEMBLYAI_API_KEY}

   # AFTER (keep only non-sensitive config):
   environment:
     AWS_REGION: us-east-1
     STAGE: prod
   ```

2. **Redeploy**:
   ```bash
   serverless deploy --stage prod
   ```

3. **Delete secrets from local .env files** (after confirming production works)

---

## Security Best Practices

### 1. Principle of Least Privilege
- Each Lambda function should only have access to the secrets it needs
- Use separate IAM roles per Lambda function
- Never grant `secretsmanager:*` permissions

### 2. Secret Naming Convention
- Use hierarchical naming: `{environment}/{application}/{secret-name}`
- Include rotation date in description
- Tag secrets with metadata (application, owner, rotation-policy)

### 3. Monitoring and Alerts
Set up CloudWatch alarms for:
- Failed secret retrieval attempts
- Secrets not rotated in 90+ days
- Unusual access patterns

```bash
# Example: CloudWatch metric filter for failed secret access
aws logs put-metric-filter \
    --log-group-name /aws/lambda/your-function \
    --filter-name FailedSecretAccess \
    --filter-pattern "[Secrets] ERROR:" \
    --metric-transformations \
        metricName=SecretAccessFailures,metricNamespace=OpusClip,metricValue=1
```

### 4. Audit Trail
Enable AWS CloudTrail logging for Secrets Manager:
```json
{
  "eventSource": "secretsmanager.amazonaws.com",
  "eventName": ["GetSecretValue", "PutSecretValue", "DeleteSecret", "RotateSecret"]
}
```

### 5. Encryption at Rest
- Secrets Manager automatically encrypts secrets using AWS KMS
- Optionally, specify a custom KMS key for additional control:
  ```bash
  aws secretsmanager create-secret \
      --name prod/opus-clip/groq-api-key \
      --kms-key-id arn:aws:kms:us-east-1:YOUR_ACCOUNT_ID:key/YOUR_KEY_ID \
      --secret-string '{"api_key":"YOUR_KEY"}'
  ```

---

## Testing

### Local Development

For local development, create a `.env.local` file with test secrets:

```bash
# .env.local (DO NOT COMMIT)
GROQ_API_KEY=test_key_for_local_development
ASSEMBLYAI_API_KEY=test_key_for_local_development
```

Update code to check for local environment:

```python
import os

# Check if running locally
IS_LOCAL = os.environ.get('AWS_EXECUTION_ENV') is None

if IS_LOCAL:
    # Use local .env file
    from dotenv import load_dotenv
    load_dotenv('.env.local')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
else:
    # Use Secrets Manager in AWS
    from secrets_manager import get_api_key
    GROQ_API_KEY = get_api_key('prod/opus-clip/groq-api-key')
```

### Integration Testing

Test secret retrieval in each Lambda function:

```python
def test_secret_retrieval():
    """Test that secrets can be retrieved successfully"""
    from secrets_manager import get_api_key

    # Test Groq API key
    groq_key = get_api_key('prod/opus-clip/groq-api-key')
    assert groq_key is not None, "Failed to retrieve Groq API key"
    assert len(groq_key) > 0, "Groq API key is empty"

    print("[Test] ✅ Secret retrieval successful")
    return True
```

---

## Cost Estimation

### AWS Secrets Manager Pricing (as of 2024)
- **Secret storage**: $0.40 per secret per month
- **API calls**: $0.05 per 10,000 API calls

### Example Cost Calculation
Assuming 5 secrets with 1,000,000 Lambda invocations per month:
- Secret storage: 5 secrets × $0.40 = $2.00/month
- API calls: 1,000,000 ÷ 10,000 × $0.05 = $5.00/month (without caching)
- **With 15-minute caching**: ~$0.10/month (assuming average Lambda lifetime of 15 min)

**Total estimated cost**: ~$2.10/month

**ROI**: The security benefits far outweigh the minimal cost.

---

## Rollback Plan

If issues occur after migration:

### 1. Immediate Rollback
Redeploy previous version with environment variables:
```bash
cd opus-clip-cloud
git checkout <previous-commit>
serverless deploy --stage prod
```

### 2. Hybrid Mode (Fallback to Env Vars)
The code examples above already include fallback logic:
```python
if SECRETS_MANAGER_ENABLED:
    API_KEY = get_api_key('prod/opus-clip/groq-api-key')
    if not API_KEY:
        API_KEY = os.environ.get('GROQ_API_KEY')  # Fallback
else:
    API_KEY = os.environ.get('GROQ_API_KEY')
```

This ensures environment variables still work during transition.

---

## Success Criteria

✅ Migration is complete when:
1. All secrets stored in AWS Secrets Manager
2. All Lambda functions successfully retrieve secrets
3. No plaintext secrets in environment variables
4. CloudWatch logs show successful secret retrieval
5. No application errors related to missing secrets
6. Automated rotation configured (90-day cycle)
7. IAM policies follow least-privilege principle

---

## Additional Resources

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [Rotating AWS Secrets Manager Secrets](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html)
- [AWS Lambda with Secrets Manager](https://aws.amazon.com/blogs/security/how-to-securely-provide-database-credentials-to-lambda-functions-by-using-aws-secrets-manager/)

---

## Questions or Issues?

If you encounter any issues during migration:
1. Check CloudWatch logs for error messages
2. Verify IAM permissions using AWS Policy Simulator
3. Ensure secret names match exactly (case-sensitive)
4. Confirm secrets exist in the correct AWS region
5. Test secret retrieval using AWS CLI first

For additional support, consult AWS documentation or contact your DevOps team.
