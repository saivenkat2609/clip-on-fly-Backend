/**
 * Lambda Function: Download Video from YouTube (Node.js with yt-dlp)
 * Uses yt-dlp binary from Lambda layer for maximum reliability
 */

const { S3Client, HeadObjectCommand, PutObjectCommand, GetObjectCommand } = require('@aws-sdk/client-s3');
const { Upload } = require('@aws-sdk/lib-storage');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// Storage helper - works with S3, R2, B2, and any S3-compatible storage
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
        config.forcePathStyle = true;
    } else {
        console.log('[Storage] Using AWS S3 (default)');
    }

    return new S3Client(config);
}

const s3 = getStorageClient();
const BUCKET_NAME = process.env.BUCKET_NAME || 'opus-clip-videos';
const COOKIES_S3_KEY = process.env.COOKIES_S3_KEY || null;
const QUALITY_MODE = process.env.QUALITY_MODE || 'balanced';
const YTDLP_PATH = process.env.YTDLP_PATH || '/opt/bin/yt-dlp';

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
 * Download cookies from S3/R2
 */
async function downloadCookies() {
    if (!COOKIES_S3_KEY) {
        console.log('[Download] No cookies configured');
        return null;
    }

    try {
        console.log(`[Download] Loading cookies from ${BUCKET_NAME}/${COOKIES_S3_KEY}...`);

        const response = await s3.send(new GetObjectCommand({
            Bucket: BUCKET_NAME,
            Key: COOKIES_S3_KEY
        }));

        const cookieData = await streamToString(response.Body);
        const cookieFilePath = '/tmp/youtube-cookies.txt';
        fs.writeFileSync(cookieFilePath, cookieData, 'utf-8');

        const lines = cookieData.split('\n');
        const cookieCount = lines.filter(line =>
            line.trim() !== '' && !line.startsWith('#')
        ).length;

        console.log(`[Download] Loaded ${cookieCount} cookies to ${cookieFilePath}`);
        return cookieFilePath;

    } catch (error) {
        console.log(`[Download] Warning: Failed to load cookies: ${error.message}`);
        return null;
    }
}

/**
 * Run yt-dlp command and return output
 */
function runYtdlp(args, options = {}) {
    return new Promise((resolve, reject) => {
        console.log(`[Download] Running: ${YTDLP_PATH} ${args.join(' ')}`);

        const ytdlp = spawn(YTDLP_PATH, args, {
            cwd: '/tmp',
            ...options
        });

        let stdout = '';
        let stderr = '';

        if (ytdlp.stdout) {
            ytdlp.stdout.on('data', (data) => {
                stdout += data.toString();
                if (!options.silent) {
                    console.log(data.toString().trim());
                }
            });
        }

        if (ytdlp.stderr) {
            ytdlp.stderr.on('data', (data) => {
                stderr += data.toString();
                if (!options.silent) {
                    console.log(data.toString().trim());
                }
            });
        }

        ytdlp.on('close', (code) => {
            if (code === 0) {
                resolve({ stdout, stderr, code });
            } else {
                reject(new Error(`yt-dlp exited with code ${code}: ${stderr || stdout}`));
            }
        });

        ytdlp.on('error', (err) => {
            reject(new Error(`Failed to spawn yt-dlp: ${err.message}`));
        });
    });
}

/**
 * Main Lambda handler
 */
exports.handler = async (event, context) => {
    if (context) {
        context.callbackWaitsForEmptyEventLoop = false;
    }

    const startTime = Date.now();
    let localPath;
    let cookieFilePath;

    try {
        // Handle Step Functions invocation
        let payload = event;
        if (event.Payload && typeof event.Payload === 'string') {
            payload = JSON.parse(event.Payload);
        } else if (event.Payload && typeof event.Payload === 'object') {
            payload = event.Payload;
        }

        const { session_id, youtube_url } = payload;

        console.log('[Download] ===== NEW INVOCATION =====');
        console.log(`[Download] Session: ${session_id}`);
        console.log(`[Download] URL: ${youtube_url}`);
        console.log(`[Download] Lambda Request ID: ${context ? context.requestId : 'local'}`);
        console.log(`[Download] Quality Mode: ${QUALITY_MODE}`);
        console.log(`[Download] Remaining time: ${context ? context.getRemainingTimeInMillis() : 'N/A'}ms`);

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
        const s3Key = `${session_id}/original_video.mp4`;

        // Download cookies
        cookieFilePath = await downloadCookies();

        // Check if video already exists
        try {
            await s3.send(new HeadObjectCommand({
                Bucket: BUCKET_NAME,
                Key: s3Key
            }));
            console.log(`[Download] Video already exists in storage: ${s3Key}`);

            // Still get video info
            const infoArgs = ['--dump-json', '--no-playlist'];
            if (cookieFilePath) {
                infoArgs.push('--cookies', cookieFilePath);
            }
            infoArgs.push(cleanUrl);

            const infoResult = await runYtdlp(infoArgs, { silent: true });
            const videoData = JSON.parse(infoResult.stdout);

            return {
                statusCode: 200,
                session_id: session_id,
                s3_video_key: s3Key,
                video_info: {
                    title: videoData.title || 'Unknown',
                    duration: videoData.duration || 0,
                    description: (videoData.description || '').substring(0, 500),
                    uploader: videoData.uploader || 'Unknown',
                    view_count: videoData.view_count || 0,
                    thumbnail_url: videoData.thumbnail || ''
                }
            };
        } catch (err) {
            console.log('[Download] Video not found in storage, proceeding with download...');
        }

        // Get video info
        console.log('[Download] Fetching video info...');
        const infoStart = Date.now();

        const infoArgs = ['--dump-json', '--no-playlist', '--no-check-formats'];
        if (cookieFilePath) {
            infoArgs.push('--cookies', cookieFilePath);
        }
        infoArgs.push(cleanUrl);

        const infoResult = await runYtdlp(infoArgs, { silent: true });
        console.log(`[Download] Info fetched in ${((Date.now() - infoStart) / 1000).toFixed(2)}s`);

        const videoData = JSON.parse(infoResult.stdout);
        const videoInfo = {
            title: videoData.title || 'Unknown',
            duration: videoData.duration || 0,
            description: (videoData.description || '').substring(0, 500),
            uploader: videoData.uploader || 'Unknown',
            view_count: videoData.view_count || 0,
            thumbnail_url: videoData.thumbnail || ''
        };

        console.log(`[Download] Title: ${videoInfo.title}`);
        console.log(`[Download] Duration: ${videoInfo.duration} seconds`);

        if (videoInfo.duration > 3600) {
            throw new Error('Video duration exceeds 1 hour limit');
        }

        // Determine format
        let formatSpec;
        if (QUALITY_MODE === 'fast') {
            formatSpec = 'best[height<=480][ext=mp4]/best[height<=480]/worst[height>=360]';
            console.log('[Download] Mode: FAST - Using 480p max');
        } else if (QUALITY_MODE === 'best') {
            formatSpec = 'best[height<=1080][ext=mp4]/best[height<=1080]/best';
            console.log('[Download] Mode: BEST - Using 1080p max');
        } else {
            formatSpec = 'best[height<=480][ext=mp4]/best[height<=480]/worst[height>=360]';
            console.log('[Download] Mode: BALANCED - Using 480p');
        }

        // Download video
        console.log(`[Download] Downloading to ${localPath}...`);
        const downloadStart = Date.now();

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

        if (cookieFilePath) {
            downloadArgs.push('--cookies', cookieFilePath);
        }
        downloadArgs.push(cleanUrl);

        await runYtdlp(downloadArgs);

        const downloadTime = (Date.now() - downloadStart) / 1000;
        const fileStats = fs.statSync(localPath);
        const fileSizeMB = fileStats.size / (1024 * 1024);
        const downloadSpeedMBps = (fileSizeMB / downloadTime).toFixed(2);

        console.log(`[Download] Downloaded ${fileSizeMB.toFixed(2)} MB in ${downloadTime.toFixed(2)}s (${downloadSpeedMBps} MB/s)`);

        // Check remaining time
        if (context && context.getRemainingTimeInMillis) {
            const remaining = context.getRemainingTimeInMillis();
            if (remaining < 60000) {
                console.error(`[Download] ERROR: Only ${(remaining/1000).toFixed(0)}s remaining!`);
            }
            console.log(`[Download] Remaining time before upload: ${(remaining/1000).toFixed(0)}s`);
        }

        // Upload to S3/R2
        console.log(`[Download] Uploading to storage: ${s3Key}`);
        const uploadStart = Date.now();

        const fileStream = fs.createReadStream(localPath);
        const upload = new Upload({
            client: s3,
            params: {
                Bucket: BUCKET_NAME,
                Key: s3Key,
                Body: fileStream,
                ContentType: 'video/mp4'
            },
            queueSize: 4,
            partSize: 1024 * 1024 * 25,
            leavePartsOnError: false
        });

        await upload.done();

        const uploadTime = (Date.now() - uploadStart) / 1000;
        const uploadSpeedMBps = (fileSizeMB / uploadTime).toFixed(2);
        console.log(`[Download] Uploaded in ${uploadTime.toFixed(2)}s (${uploadSpeedMBps} MB/s)`);

        // Clean up
        fs.unlinkSync(localPath);
        if (cookieFilePath && fs.existsSync(cookieFilePath)) {
            fs.unlinkSync(cookieFilePath);
        }

        const totalTime = (Date.now() - startTime) / 1000;
        console.log(`[Download] Complete! Total time: ${totalTime.toFixed(2)}s`);

        return {
            statusCode: 200,
            session_id: session_id,
            s3_video_key: s3Key,
            video_info: videoInfo
        };

    } catch (error) {
        console.error(`[Download] Error: ${error.message}`);
        console.error(error.stack);
        console.error(`[Download] Full event received:`, JSON.stringify(event, null, 2));

        // Clean up on error
        if (localPath && fs.existsSync(localPath)) {
            try {
                fs.unlinkSync(localPath);
            } catch (e) {
                console.error(`[Download] Failed to clean up: ${e.message}`);
            }
        }

        if (cookieFilePath && fs.existsSync(cookieFilePath)) {
            try {
                fs.unlinkSync(cookieFilePath);
            } catch (e) {
                console.error(`[Download] Failed to clean up cookies: ${e.message}`);
            }
        }

        throw new Error(`Failed to download video: ${error.message}`);
    }
};
