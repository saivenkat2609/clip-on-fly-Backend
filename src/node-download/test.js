/**
 * Local test script for Node.js download Lambda
 */

// Set environment variables for testing
process.env.BUCKET_NAME = process.env.BUCKET_NAME || 'opus-clip-videos';
process.env.QUALITY_MODE = process.env.QUALITY_MODE || 'balanced';
process.env.AWS_REGION = process.env.AWS_REGION || 'us-east-1';

// Optional: Set cookies file location in S3/R2
// process.env.COOKIES_S3_KEY = 'youtube-cookies.txt';

// If using R2, set these:
// process.env.R2_ENDPOINT = 'https://your-account-id.r2.cloudflarestorage.com';
// process.env.R2_ACCESS_KEY = 'your-access-key';
// process.env.R2_SECRET_KEY = 'your-secret-key';

// For local testing without S3, you can also set cookies manually:
// (This is just for testing - in production, cookies come from S3/R2)

const handler = require('./index').handler;

// Test video URLs (short videos for testing)
const TEST_URLS = [
    'https://www.youtube.com/watch?v=jNQXAC9IVRw', // "Me at the zoo" - first YouTube video (18s)
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ', // Rick Roll (3:33)
    // Add your test URL here
];

async function runTest(url) {
    console.log('\n================================================');
    console.log(`Testing URL: ${url}`);
    console.log('================================================\n');

    // Test with direct payload (for direct Lambda invocation)
    const event = {
        session_id: 'test-' + Date.now(),
        youtube_url: url
    };

    // Uncomment to test Step Functions format:
    // const event = {
    //     Payload: {
    //         session_id: 'test-' + Date.now(),
    //         youtube_url: url
    //     }
    // };

    const context = {
        requestId: 'local-test-' + Date.now(),
        getRemainingTimeInMillis: () => 300000 // 5 minutes
    };

    try {
        const startTime = Date.now();
        const result = await handler(event, context);
        const duration = ((Date.now() - startTime) / 1000).toFixed(2);

        console.log('\n✅ SUCCESS!');
        console.log(`   Duration: ${duration}s`);
        console.log(`   Session ID: ${result.session_id}`);
        console.log(`   S3 Key: ${result.s3_video_key}`);
        console.log(`   Title: ${result.video_info.title}`);
        console.log(`   Length: ${result.video_info.duration}s`);
        console.log(`   Uploader: ${result.video_info.uploader}`);

        return true;
    } catch (error) {
        console.error('\n❌ FAILED!');
        console.error(`   Error: ${error.message}`);
        console.error(`   Stack: ${error.stack}`);
        return false;
    }
}

async function main() {
    console.log('================================================');
    console.log('Node.js Download Lambda - Local Test');
    console.log('================================================');
    console.log(`Bucket: ${process.env.BUCKET_NAME}`);
    console.log(`Quality: ${process.env.QUALITY_MODE}`);
    console.log(`Region: ${process.env.AWS_REGION}`);
    console.log(`Storage: ${process.env.R2_ENDPOINT ? 'R2/Custom' : 'AWS S3'}`);

    // Get URL from command line or use first test URL
    const testUrl = process.argv[2] || TEST_URLS[0];

    const success = await runTest(testUrl);

    console.log('\n================================================');
    if (success) {
        console.log('✅ All tests passed!');
        process.exit(0);
    } else {
        console.log('❌ Tests failed');
        process.exit(1);
    }
}

// Run tests
main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
});
