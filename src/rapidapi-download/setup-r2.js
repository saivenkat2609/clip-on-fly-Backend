#!/usr/bin/env node

/**
 * Setup script to upload initial API keys usage file to R2/S3
 *
 * Usage:
 *   1. Edit rapidapi-keys-usage.json with your API keys
 *   2. Run: node setup-r2.js
 */

const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3');
const fs = require('fs');
const path = require('path');

// Configuration
const BUCKET_NAME = process.env.BUCKET_NAME || 'opus-clip-videos';
const R2_KEY = process.env.API_KEYS_R2_KEY || 'config/rapidapi-keys-usage.json';
const REGION = process.env.AWS_REGION || 'us-east-1';

// Initialize S3 client
const s3 = new S3Client({
  region: REGION,
  // If using Cloudflare R2, uncomment and configure:
  // endpoint: 'https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com',
  // credentials: {
  //   accessKeyId: process.env.R2_ACCESS_KEY_ID,
  //   secretAccessKey: process.env.R2_SECRET_ACCESS_KEY
  // }
});

async function uploadUsageFile() {
  console.log('======================================');
  console.log('RapidAPI Keys Setup');
  console.log('======================================');
  console.log();

  // Read the usage file
  const usageFilePath = path.join(__dirname, 'rapidapi-keys-usage.json');

  if (!fs.existsSync(usageFilePath)) {
    console.error('❌ ERROR: rapidapi-keys-usage.json not found');
    console.error('   Please create the file first');
    process.exit(1);
  }

  const usageData = fs.readFileSync(usageFilePath, 'utf8');

  // Validate JSON
  let parsedData;
  try {
    parsedData = JSON.parse(usageData);
  } catch (err) {
    console.error('❌ ERROR: Invalid JSON in rapidapi-keys-usage.json');
    console.error(`   ${err.message}`);
    process.exit(1);
  }

  // Validate structure
  if (!parsedData.keys || !Array.isArray(parsedData.keys)) {
    console.error('❌ ERROR: Invalid structure - missing "keys" array');
    process.exit(1);
  }

  // Check for placeholder keys
  const hasPlaceholders = parsedData.keys.some(key =>
    key.apiKey.includes('REPLACE_WITH_YOUR_RAPIDAPI_KEY')
  );

  if (hasPlaceholders) {
    console.warn('⚠️  WARNING: Some API keys still have placeholder values');
    console.warn('   Please replace all "REPLACE_WITH_YOUR_RAPIDAPI_KEY_X" with actual API keys');
    console.warn();

    // Ask for confirmation
    const readline = require('readline').createInterface({
      input: process.stdin,
      output: process.stdout
    });

    const answer = await new Promise(resolve => {
      readline.question('Do you want to continue anyway? (y/N): ', resolve);
    });
    readline.close();

    if (answer.toLowerCase() !== 'y') {
      console.log('Setup cancelled');
      process.exit(0);
    }
  }

  // Display configuration
  console.log(`Bucket: ${BUCKET_NAME}`);
  console.log(`Key: ${R2_KEY}`);
  console.log(`Region: ${REGION}`);
  console.log(`API Keys: ${parsedData.keys.length}`);
  console.log(`Enabled Keys: ${parsedData.keys.filter(k => k.enabled).length}`);
  console.log(`Monthly Limit per Key: ${parsedData.monthlyLimit} requests`);
  console.log(`Total Monthly Capacity: ${parsedData.monthlyLimit * parsedData.keys.length} requests`);
  console.log();

  // Upload to S3/R2
  try {
    console.log('Uploading to S3/R2...');

    await s3.send(new PutObjectCommand({
      Bucket: BUCKET_NAME,
      Key: R2_KEY,
      Body: usageData,
      ContentType: 'application/json',
    }));

    console.log('✅ SUCCESS: API keys usage file uploaded');
    console.log();
    console.log('Next steps:');
    console.log('1. Deploy Lambda function: deploy.bat');
    console.log('2. Test Lambda: aws lambda invoke --function-name opus-rapidapi-download ...');
    console.log('3. Update Step Functions to route to this Lambda');
    console.log();

  } catch (err) {
    console.error('❌ ERROR: Failed to upload to S3/R2');
    console.error(`   ${err.message}`);

    if (err.Code === 'NoSuchBucket') {
      console.error();
      console.error('   The bucket does not exist. Please create it first:');
      console.error(`   aws s3 mb s3://${BUCKET_NAME} --region ${REGION}`);
    } else if (err.Code === 'AccessDenied') {
      console.error();
      console.error('   Access denied. Please check:');
      console.error('   1. AWS credentials are configured (aws configure)');
      console.error('   2. IAM role has s3:PutObject permission');
      console.error('   3. Bucket policy allows uploads');
    }

    process.exit(1);
  }
}

// Run setup
uploadUsageFile().catch(err => {
  console.error('Unexpected error:', err);
  process.exit(1);
});
