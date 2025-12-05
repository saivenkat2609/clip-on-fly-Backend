/**
 * Test script to verify yt-dlp Lambda layer is working
 *
 * Deploy this as a separate test Lambda or add to your existing function
 * to verify the layer is properly configured.
 */

const { spawn } = require('child_process');
const fs = require('fs');

const YTDLP_PATH = process.env.YTDLP_PATH || '/opt/bin/yt-dlp';

/**
 * Run a command and return output
 */
function runCommand(command, args) {
    return new Promise((resolve, reject) => {
        const proc = spawn(command, args);

        let stdout = '';
        let stderr = '';

        proc.stdout.on('data', (data) => {
            stdout += data.toString();
        });

        proc.stderr.on('data', (data) => {
            stderr += data.toString();
        });

        proc.on('close', (code) => {
            resolve({ stdout, stderr, code });
        });

        proc.on('error', (err) => {
            reject(err);
        });
    });
}

/**
 * Check if file exists
 */
function fileExists(path) {
    try {
        return fs.existsSync(path);
    } catch (err) {
        return false;
    }
}

/**
 * Check if file is executable
 */
function isExecutable(path) {
    try {
        fs.accessSync(path, fs.constants.X_OK);
        return true;
    } catch (err) {
        return false;
    }
}

/**
 * Main test handler
 */
exports.handler = async (event, context) => {
    console.log('========================================');
    console.log('yt-dlp Layer Verification Test');
    console.log('========================================');

    const results = {
        timestamp: new Date().toISOString(),
        tests: []
    };

    // Test 1: Check YTDLP_PATH environment variable
    console.log('\n[Test 1] Checking YTDLP_PATH environment variable...');
    const ytdlpPath = process.env.YTDLP_PATH;
    if (ytdlpPath) {
        console.log(`✅ YTDLP_PATH is set: ${ytdlpPath}`);
        results.tests.push({
            test: 'YTDLP_PATH Environment Variable',
            status: 'PASS',
            value: ytdlpPath
        });
    } else {
        console.log(`⚠️  YTDLP_PATH not set, using default: ${YTDLP_PATH}`);
        results.tests.push({
            test: 'YTDLP_PATH Environment Variable',
            status: 'WARN',
            value: `Not set, using default: ${YTDLP_PATH}`
        });
    }

    // Test 2: Check if yt-dlp file exists
    console.log('\n[Test 2] Checking if yt-dlp exists...');
    if (fileExists(YTDLP_PATH)) {
        console.log(`✅ yt-dlp file exists at: ${YTDLP_PATH}`);
        results.tests.push({
            test: 'yt-dlp File Exists',
            status: 'PASS',
            path: YTDLP_PATH
        });
    } else {
        console.log(`❌ yt-dlp NOT found at: ${YTDLP_PATH}`);
        console.log('\n📝 Common paths to check:');
        console.log('   - /opt/bin/yt-dlp');
        console.log('   - /opt/python/bin/yt-dlp');
        console.log('   - /opt/yt-dlp');

        results.tests.push({
            test: 'yt-dlp File Exists',
            status: 'FAIL',
            path: YTDLP_PATH,
            message: 'File not found. Check layer is attached and path is correct.'
        });

        return {
            statusCode: 500,
            body: JSON.stringify(results, null, 2)
        };
    }

    // Test 3: Check if yt-dlp is executable
    console.log('\n[Test 3] Checking if yt-dlp is executable...');
    if (isExecutable(YTDLP_PATH)) {
        console.log(`✅ yt-dlp is executable`);
        results.tests.push({
            test: 'yt-dlp Is Executable',
            status: 'PASS'
        });
    } else {
        console.log(`❌ yt-dlp exists but is NOT executable`);
        results.tests.push({
            test: 'yt-dlp Is Executable',
            status: 'FAIL',
            message: 'File exists but lacks execute permissions. Check layer was created with chmod +x.'
        });
    }

    // Test 4: Get yt-dlp version
    console.log('\n[Test 4] Running yt-dlp --version...');
    try {
        const result = await runCommand(YTDLP_PATH, ['--version']);

        if (result.code === 0) {
            const version = result.stdout.trim();
            console.log(`✅ yt-dlp version: ${version}`);
            results.tests.push({
                test: 'yt-dlp Execution (--version)',
                status: 'PASS',
                version: version,
                exitCode: result.code
            });
        } else {
            console.log(`❌ yt-dlp exited with code ${result.code}`);
            console.log(`stderr: ${result.stderr}`);
            results.tests.push({
                test: 'yt-dlp Execution (--version)',
                status: 'FAIL',
                exitCode: result.code,
                stderr: result.stderr
            });
        }
    } catch (err) {
        console.log(`❌ Failed to execute yt-dlp: ${err.message}`);
        results.tests.push({
            test: 'yt-dlp Execution (--version)',
            status: 'FAIL',
            error: err.message
        });
    }

    // Test 5: Check /opt directory contents
    console.log('\n[Test 5] Listing /opt directory...');
    try {
        if (fs.existsSync('/opt')) {
            const optContents = fs.readdirSync('/opt');
            console.log('Contents of /opt:');
            optContents.forEach(item => {
                console.log(`   - ${item}`);
            });
            results.tests.push({
                test: '/opt Directory Contents',
                status: 'INFO',
                contents: optContents
            });

            // Check /opt/bin if it exists
            if (optContents.includes('bin')) {
                const binContents = fs.readdirSync('/opt/bin');
                console.log('Contents of /opt/bin:');
                binContents.forEach(item => {
                    console.log(`   - ${item}`);
                });
                results.optBin = binContents;
            }
        } else {
            console.log('/opt directory does not exist');
            results.tests.push({
                test: '/opt Directory Contents',
                status: 'WARN',
                message: '/opt directory not found'
            });
        }
    } catch (err) {
        console.log(`Error reading /opt: ${err.message}`);
        results.tests.push({
            test: '/opt Directory Contents',
            status: 'ERROR',
            error: err.message
        });
    }

    // Test 6: Simple yt-dlp functionality test
    console.log('\n[Test 6] Testing yt-dlp with simple video info fetch...');
    try {
        const testUrl = 'https://www.youtube.com/watch?v=jNQXAC9IVRw';
        const result = await runCommand(YTDLP_PATH, [
            '--dump-json',
            '--no-playlist',
            '--no-check-formats',
            testUrl
        ]);

        if (result.code === 0) {
            const videoData = JSON.parse(result.stdout);
            console.log(`✅ Successfully fetched video info`);
            console.log(`   Title: ${videoData.title}`);
            console.log(`   Duration: ${videoData.duration}s`);
            results.tests.push({
                test: 'yt-dlp Functionality Test',
                status: 'PASS',
                videoTitle: videoData.title,
                videoDuration: videoData.duration,
                message: 'Successfully fetched video metadata'
            });
        } else {
            console.log(`⚠️  yt-dlp exited with code ${result.code}`);
            console.log(`stderr: ${result.stderr.substring(0, 200)}`);
            results.tests.push({
                test: 'yt-dlp Functionality Test',
                status: 'WARN',
                exitCode: result.code,
                message: 'yt-dlp ran but returned non-zero exit code. May need cookies for some videos.'
            });
        }
    } catch (err) {
        console.log(`⚠️  Functionality test failed: ${err.message}`);
        results.tests.push({
            test: 'yt-dlp Functionality Test',
            status: 'WARN',
            error: err.message,
            message: 'Could not fetch video info. This is normal if cookies are required.'
        });
    }

    // Summary
    console.log('\n========================================');
    console.log('Test Summary');
    console.log('========================================');

    const passed = results.tests.filter(t => t.status === 'PASS').length;
    const failed = results.tests.filter(t => t.status === 'FAIL').length;
    const warned = results.tests.filter(t => t.status === 'WARN').length;

    console.log(`✅ Passed: ${passed}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`⚠️  Warnings: ${warned}`);

    results.summary = {
        total: results.tests.length,
        passed: passed,
        failed: failed,
        warnings: warned
    };

    if (failed === 0) {
        console.log('\n🎉 All critical tests passed! Layer is working correctly.');
        results.overallStatus = 'SUCCESS';
    } else {
        console.log('\n❌ Some tests failed. Check the results above.');
        results.overallStatus = 'FAILURE';
    }

    console.log('========================================\n');

    return {
        statusCode: failed === 0 ? 200 : 500,
        body: JSON.stringify(results, null, 2)
    };
};

// For local testing
if (require.main === module) {
    exports.handler({}, {})
        .then(result => {
            console.log('\nFinal Result:');
            console.log(result.body);
            process.exit(result.statusCode === 200 ? 0 : 1);
        })
        .catch(err => {
            console.error('Test failed:', err);
            process.exit(1);
        });
}
