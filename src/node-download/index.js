/**
 * Lambda Function: Download Video from YouTube (Node.js with yt-dlp)
 * Uses yt-dlp binary from Lambda layer for maximum reliability
 * Matches Python version functionality with R2/S3 support and SigV4 signatures
 */

const { S3Client, HeadObjectCommand, GetObjectCommand } = require('@aws-sdk/client-s3');
const { Upload } = require('@aws-sdk/lib-storage');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// Storage helper - works with S3, R2, B2, and any S3-compatible storage
// AWS SDK v3 automatically uses SigV4 signatures for all S3-compatible services
function getStorageClient() {
    const endpoint = process.env.R2_ENDPOINT || process.env.STORAGE_ENDPOINT;
    const accessKey = process.env.R2_ACCESS_KEY || process.env.AWS_ACCESS_KEY_ID;
    const secretKey = process.env.R2_SECRET_KEY || process.env.AWS_SECRET_ACCESS_KEY;
    const region = process.env.AWS_REGION || 'auto';

    const config = {
        credentials: {
            accessKeyId: accessKey,
            secretAccessKey: secretKey
        },
        region: region
    };

    if (endpoint) {
        console.log(`[Storage] Using custom endpoint: ${endpoint}`);
        config.endpoint = endpoint;
        config.forcePathStyle = true;  // Required for R2 and S3-compatible storage
    } else {
        console.log('[Storage] Using AWS S3 (default)');
    }

    return new S3Client(config);
}

const s3 = getStorageClient();
const BUCKET_NAME = process.env.BUCKET_NAME || 'opus-clip-videos';
const COOKIES_S3_KEY = process.env.COOKIES_S3_KEY || null;  // Optional: youtube-cookies.txt
const QUALITY_MODE = process.env.QUALITY_MODE || 'balanced';  // 'fast', 'balanced', 'best'
const SKIP_INFO_FETCH = (process.env.SKIP_INFO_FETCH || 'false').toLowerCase() === 'true';
const YTDLP_PATH = process.env.YTDLP_PATH || '/opt/bin/yt-dlp';

// S3 Transfer configuration for faster uploads (matches Python's TransferConfig)
const TRANSFER_CONFIG = {
    queueSize: 10,              // max_concurrency in Python
    partSize: 1024 * 1024 * 25, // 25 MB (multipart_chunksize in Python)
};

/**
 * Convert stream to string
 */
async function streamToString(stream) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        stream.on('data', (chunk) => chunks.push(chunk));
        stream.on('error', reject);
        stream.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    });
}

/**
 * Download cookies from R2/S3 (matches Python behavior exactly)
 */
async function downloadCookies() {
    if (!COOKIES_S3_KEY) {
        return null;
    }

    try {
        const cookies_file = '/tmp/youtube-cookies.txt';
        console.log('[Download] Attempting to download cookies...');
        console.log(`[Download]   Bucket: ${BUCKET_NAME}`);
        console.log(`[Download]   Key: ${COOKIES_S3_KEY}`);
        console.log(`[Download]   Storage: ${process.env.R2_ENDPOINT ? 'R2' : 'AWS S3'}`);

        // Check if file exists first
        try {
            await s3.send(new HeadObjectCommand({
                Bucket: BUCKET_NAME,
                Key: COOKIES_S3_KEY
            }));
            console.log('[Download]   File exists in bucket!');
        } catch (head_error) {
            console.log(`[Download]   File NOT found in bucket: ${head_error.message}`);
            console.log(`[Download]   Make sure file is uploaded to: ${BUCKET_NAME}/${COOKIES_S3_KEY}`);
            throw head_error;
        }

        // Download cookie file
        const response = await s3.send(new GetObjectCommand({
            Bucket: BUCKET_NAME,
            Key: COOKIES_S3_KEY
        }));

        const cookieData = await streamToString(response.Body);
        fs.writeFileSync(cookies_file, cookieData, 'utf-8');

        console.log('[Download] Cookies downloaded successfully');
        return cookies_file;

    } catch (error) {
        console.log(`[Download] Warning: Failed to download cookies: ${error.message}`);
        console.log('[Download] Continuing WITHOUT cookies (will use Android client)');
        return null;
    }
}

/**
 * Run yt-dlp command and return output
 */
function runYtdlp(args, options = {}) {
    return new Promise((resolve, reject) => {
        const timeout = options.timeout || 240000; // Default 4 minutes

        if (!options.silent) {
            console.log(`[Download] Running: ${YTDLP_PATH} ${args.join(' ')}`);
        }

        const ytdlp = spawn(YTDLP_PATH, args, {
            cwd: '/tmp',
        });

        let stdout = '';
        let stderr = '';
        let timeoutId;

        // Set timeout
        if (timeout) {
            timeoutId = setTimeout(() => {
                ytdlp.kill();
                reject(new Error(`Command timed out after ${timeout}ms`));
            }, timeout);
        }

        if (ytdlp.stdout) {
            ytdlp.stdout.on('data', (data) => {
                stdout += data.toString();
                if (!options.silent && !options.captureOutput) {
                    process.stdout.write(data);
                }
            });
        }

        if (ytdlp.stderr) {
            ytdlp.stderr.on('data', (data) => {
                stderr += data.toString();
                if (!options.silent && !options.captureOutput) {
                    process.stderr.write(data);
                }
            });
        }

        ytdlp.on('close', (code) => {
            if (timeoutId) clearTimeout(timeoutId);

            if (code === 0) {
                resolve({ stdout, stderr, code });
            } else {
                reject(new Error(`yt-dlp exited with code ${code}: ${stderr || stdout}`));
            }
        });

        ytdlp.on('error', (err) => {
            if (timeoutId) clearTimeout(timeoutId);
            reject(new Error(`Failed to spawn yt-dlp: ${err.message}`));
        });
    });
}

/**
 * Main Lambda handler
 * Matches Python version output format exactly
 */
exports.handler = async (event, context) => {
    if (context) {
        context.callbackWaitsForEmptyEventLoop = false;
    }

    const startTime = Date.now();
    let localPath;
    let cookiesFile;

    try {
        // Handle Step Functions invocation
        let payload = event;
        if (event.Payload && typeof event.Payload === 'string') {
            payload = JSON.parse(event.Payload);
        } else if (event.Payload && typeof event.Payload === 'object') {
            payload = event.Payload;
        }

        const session_id = payload.session_id;
        const youtube_url = payload.youtube_url;

        console.log('[Download] ===== NEW INVOCATION =====');
        console.log(`[Download] Session: ${session_id}`);
        console.log(`[Download] URL: ${youtube_url}`);
        console.log(`[Download] Lambda Request ID: ${context ? context.requestId : 'N/A'}`);

        if (!session_id || !youtube_url) {
            throw new Error(`Missing required parameters: session_id=${session_id}, youtube_url=${youtube_url}`);
        }

        // Clean URL
        let cleanUrl = youtube_url;
        if (youtube_url.includes('&') && youtube_url.includes('v=')) {
            const videoId = youtube_url.split('v=')[1].split('&')[0];
            cleanUrl = `https://www.youtube.com/watch?v=${videoId}`;
            console.log(`[Download] Cleaned URL: ${cleanUrl}`);
        }

        // Setup paths
        const outputFilename = `${session_id}_video.mp4`;
        localPath = path.join('/tmp', outputFilename);
        const s3_key = `${session_id}/original_video.mp4`;

        // Check if yt-dlp exists
        if (!fs.existsSync(YTDLP_PATH)) {
            throw new Error(`yt-dlp binary not found at ${YTDLP_PATH}. Make sure yt-dlp layer is attached.`);
        }

        // Download cookies if configured
        cookiesFile = await downloadCookies();

        let video_info;

        // Optionally skip info fetch for maximum speed (matches Python)
        if (SKIP_INFO_FETCH) {
            console.log('[Download] Skipping info fetch (SKIP_INFO_FETCH=true) - going straight to download');
            video_info = {
                title: 'Unknown (skipped info fetch)',
                duration: 0,
                description: '',
                uploader: 'Unknown',
                view_count: 0,
                thumbnail_url: ''
            };
        } else {
            // Get video info first (matches Python behavior)
            console.log('[Download] Fetching video info...');
            const infoStart = Date.now();

            const infoArgs = [
                '--dump-json',
                '--no-playlist',
                '--no-check-formats',  // Skip format validation for speed
                '--skip-download',     // Only get info
            ];

            // With cookies, use default client (like Python version)
            if (cookiesFile && fs.existsSync(cookiesFile)) {
                infoArgs.push('--cookies', cookiesFile);
                console.log('[Download] Using cookies with default client');
                // Don't force player_client - let yt-dlp choose automatically
            } else {
                console.log('[Download] No cookies - using android client');
                infoArgs.push('--extractor-args', 'youtube:player_client=android');
                infoArgs.push('--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip');
            }

            infoArgs.push(cleanUrl);

            try {
                const infoResult = await runYtdlp(infoArgs, {
                    timeout: 45000,  // 45 seconds
                    captureOutput: true,
                    silent: true
                });

                const infoTime = ((Date.now() - infoStart) / 1000).toFixed(2);
                console.log(`[Download] Info fetched in ${infoTime}s`);

                const videoData = JSON.parse(infoResult.stdout);
                video_info = {
                    title: videoData.title || 'Unknown',
                    duration: videoData.duration || 0,
                    description: (videoData.description || '').substring(0, 500),
                    uploader: videoData.uploader || 'Unknown',
                    view_count: videoData.view_count || 0,
                    thumbnail_url: videoData.thumbnail || ''
                };

                console.log(`[Download] Title: ${video_info.title}`);
                console.log(`[Download] Duration: ${video_info.duration} seconds`);

                // Check duration limit (1 hour max)
                if (video_info.duration > 3600) {
                    throw new Error('Video duration exceeds 1 hour limit');
                }

            } catch (error) {
                if (error.message.includes('timed out')) {
                    throw new Error('Video info fetch timeout after 45 seconds');
                }
                console.log(`[Download] yt-dlp stderr: ${error.message}`);
                throw new Error(`Failed to get video info: ${error.message}`);
            }
        }

        // Check if video already exists in storage (avoid re-downloading)
        try {
            await s3.send(new HeadObjectCommand({
                Bucket: BUCKET_NAME,
                Key: s3_key
            }));
            console.log(`[Download] Video already exists in storage: ${s3_key}`);
            console.log('[Download] Skipping download - using existing file');

            return {
                statusCode: 200,
                session_id: session_id,
                s3_video_key: s3_key,
                video_info: video_info
            };
        } catch (err) {
            console.log('[Download] Video not found in storage, proceeding with download...');
        }

        // Download video using yt-dlp (matches Python behavior)
        console.log(`[Download] Downloading to ${localPath}...`);
        const downloadStart = Date.now();

        // Determine optimal format - matches Python logic exactly
        let formatSpec;
        if (QUALITY_MODE === 'fast') {
            formatSpec = 'best[height<=480][ext=mp4]/best[height<=480]/worst[height>=360]';
            console.log('[Download] Mode: FAST - Using 480p max (smallest/fastest)');
        } else if (QUALITY_MODE === 'best') {
            formatSpec = 'best[height<=1080][ext=mp4]/best[height<=1080]/best';
            console.log('[Download] Mode: BEST - Using 1080p max');
        } else {  // balanced (default)
            formatSpec = 'best[height<=480][ext=mp4]/best[height<=480]/worst[height>=360]';
            console.log('[Download] Mode: BALANCED - Using 480p (optimized for speed)');
        }

        const downloadArgs = [
            '--format', formatSpec,
            '--output', localPath,
            '--no-playlist',
            '--no-continue',
            '--no-part',
            '--no-mtime',
            '--concurrent-fragments', '8',
            '--buffer-size', '128K',
            '--retries', '3',
            '--fragment-retries', '3',
            '--force-ipv4',
            '--newline',
            '--progress'
        ];

        // With cookies, use default client (matches Python)
        if (cookiesFile && fs.existsSync(cookiesFile)) {
            downloadArgs.push('--cookies', cookiesFile);
        } else {
            downloadArgs.push('--extractor-args', 'youtube:player_client=android');
            downloadArgs.push('--user-agent', 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip');
        }

        downloadArgs.push(cleanUrl);

        console.log('[Download] Starting yt-dlp download (progress will be shown below)...');
        console.log(`[Download] Expected file size: ~${(video_info.duration * 0.5).toFixed(1)} MB (480p estimate)`);

        try {
            await runYtdlp(downloadArgs, {
                timeout: 240000,  // 4 minutes
                captureOutput: false  // Let output stream to CloudWatch
            });

            const downloadTime = ((Date.now() - downloadStart) / 1000).toFixed(2);
            const fileSize = fs.statSync(localPath).size;
            const fileSizeMB = fileSize / (1024 * 1024);
            const downloadSpeedMBps = (fileSizeMB / parseFloat(downloadTime)).toFixed(2);

            console.log(`[Download] yt-dlp completed in ${downloadTime}s (${downloadSpeedMBps} MB/s)`);

        } catch (error) {
            if (error.message.includes('timed out')) {
                throw new Error('Video download timeout (4 minutes) - 480p should download faster. Check Lambda network speed.');
            }
            console.log(`[Download] yt-dlp failed: ${error.message}`);
            throw new Error(`yt-dlp download failed: ${error.message}`);
        }

        // Verify file exists
        if (!fs.existsSync(localPath)) {
            throw new Error(`Downloaded file not found at ${localPath}`);
        }

        const fileSize = fs.statSync(localPath).size;
        const fileSizeMB = (fileSize / (1024 * 1024)).toFixed(2);
        console.log(`[Download] Downloaded ${fileSizeMB} MB`);

        // Upload to R2/S3 with multipart for faster transfer (matches Python)
        console.log(`[Download] Uploading to S3: ${s3_key}`);
        const uploadStart = Date.now();

        const fileStream = fs.createReadStream(localPath);

        // Use multipart upload for files > 25MB (matches Python's transfer_config)
        if (fileSize > 25 * 1024 * 1024) {
            console.log('[Download] Using multipart upload (10 concurrent threads)');
            const upload = new Upload({
                client: s3,
                params: {
                    Bucket: BUCKET_NAME,
                    Key: s3_key,
                    Body: fileStream,
                    ContentType: 'video/mp4'
                },
                queueSize: TRANSFER_CONFIG.queueSize,
                partSize: TRANSFER_CONFIG.partSize,
                leavePartsOnError: false
            });
            await upload.done();
        } else {
            const upload = new Upload({
                client: s3,
                params: {
                    Bucket: BUCKET_NAME,
                    Key: s3_key,
                    Body: fileStream,
                    ContentType: 'video/mp4'
                }
            });
            await upload.done();
        }

        const uploadTime = ((Date.now() - uploadStart) / 1000).toFixed(2);
        const uploadSpeedMBps = (parseFloat(fileSizeMB) / parseFloat(uploadTime)).toFixed(2);
        console.log(`[Download] Uploaded in ${uploadTime}s (${uploadSpeedMBps} MB/s)`);

        // Clean up local file
        fs.unlinkSync(localPath);

        const totalTime = ((Date.now() - startTime) / 1000).toFixed(2);
        console.log(`[Download] Complete! Total time: ${totalTime}s`);

        // Return format matching Python version exactly
        return {
            statusCode: 200,
            session_id: session_id,
            s3_video_key: s3_key,
            video_info: video_info
        };

    } catch (error) {
        console.log(`[Download] Error: ${error.message}`);

        // Clean up on error
        if (localPath && fs.existsSync(localPath)) {
            try {
                fs.unlinkSync(localPath);
            } catch (e) {
                // Ignore cleanup errors
            }
        }

        if (cookiesFile && fs.existsSync(cookiesFile)) {
            try {
                fs.unlinkSync(cookiesFile);
            } catch (e) {
                // Ignore cleanup errors
            }
        }

        throw new Error(`Failed to download video: ${error.message}`);
    }
};
