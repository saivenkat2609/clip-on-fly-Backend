/**
 * Lambda Function: Download Video from YouTube (Node.js with yt-dlp)
 * Uses yt-dlp binary from Lambda layer for maximum reliability
 * Matches Python version functionality with R2/S3 support and SigV4 signatures
 * INTEGRATED: With structured logging, metrics, DynamoDB tracking, WebSocket notifications
 */

const {
  S3Client,
  HeadObjectCommand,
  GetObjectCommand,
} = require("@aws-sdk/client-s3");
const { Upload } = require("@aws-sdk/lib-storage");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const https = require("https");

const SUPABASE_URL = (process.env.SUPABASE_URL || '').replace(/\/$/, '');
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || '';

function updateSupabaseStatus(session_id, status) {
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) return Promise.resolve();
  return new Promise((resolve) => {
    try {
      const body = JSON.stringify({ status });
      const url = new URL(`${SUPABASE_URL}/rest/v1/videos?session_id=eq.${encodeURIComponent(session_id)}`);
      const req = https.request({ hostname: url.hostname, path: url.pathname + url.search, method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          'apikey': SUPABASE_SERVICE_ROLE_KEY, 'Prefer': 'return=minimal', 'Content-Length': Buffer.byteLength(body) }
      }, () => resolve());
      req.on('error', (e) => { console.log(`[Supabase] status update failed: ${e.message}`); resolve(); });
      req.write(body); req.end();
    } catch (e) { console.log(`[Supabase] status update failed: ${e.message}`); resolve(); }
  });
}

// Import scalability utilities (graceful fallback if not available)
let logger, updateVideoSession, notifyProcessingProgress, trackVideoDownloadTime, UTILITIES_AVAILABLE;
try {
  // Try to load from Lambda Layer at /opt/nodejs/node_modules
  const sharedUtils = require('/opt/nodejs/shared-utils');
  logger = sharedUtils.logger;
  updateVideoSession = sharedUtils.updateVideoSession;
  notifyProcessingProgress = sharedUtils.notifyProcessingProgress;
  trackVideoDownloadTime = sharedUtils.trackVideoDownloadTime;
  UTILITIES_AVAILABLE = true;
  console.log("[Download] Scalability utilities loaded successfully");
} catch (e) {
  console.log(`[Download] Warning: Scalability utilities not available: ${e.message}`);
  console.log("[Download] Using inline notification functions");
  UTILITIES_AVAILABLE = false;

  // Fallback inline WebSocket notification
  const AWS = require('@aws-sdk/client-dynamodb');
  const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
  const { DynamoDBDocumentClient, QueryCommand } = require('@aws-sdk/lib-dynamodb');
  const { ApiGatewayManagementApiClient, PostToConnectionCommand } = require('@aws-sdk/client-apigatewaymanagementapi');

  const dynamoClient = new DynamoDBClient({ region: process.env.AWS_REGION || 'us-east-1' });
  const docClient = DynamoDBDocumentClient.from(dynamoClient);

  // Inline notification function
  notifyProcessingProgress = async (session_id, status, progress, message) => {
    const WEBSOCKET_API_ENDPOINT = process.env.WEBSOCKET_API_ENDPOINT;
    const WEBSOCKET_TABLE = process.env.DYNAMODB_WEBSOCKET_CONNECTIONS_TABLE || 'prod-websocket-connections';

    if (!WEBSOCKET_API_ENDPOINT) {
      console.log(`[WebSocket] ⚠️ WEBSOCKET_API_ENDPOINT not configured`);
      return;
    }

    try {
      // Get connections for this session
      const queryResult = await docClient.send(new QueryCommand({
        TableName: WEBSOCKET_TABLE,
        IndexName: 'session_id-index',
        KeyConditionExpression: 'session_id = :sid',
        ExpressionAttributeValues: { ':sid': session_id }
      }));

      const connections = queryResult.Items || [];
      console.log(`[WebSocket] 📡 Found ${connections.length} connection(s) for session ${session_id}`);

      if (connections.length === 0) return;

      // Prepare message
      const wsMessage = {
        event: 'processing_progress',
        session_id,
        status,
        timestamp: Math.floor(Date.now() / 1000),
        data: { status, progress, message }
      };

      console.log(`[WebSocket] 📤 Sending: ${status} @ ${progress}%`);

      // Send to all connections
      const apiGwClient = new ApiGatewayManagementApiClient({
        endpoint: WEBSOCKET_API_ENDPOINT,
        region: process.env.AWS_REGION || 'us-east-1'
      });

      for (const conn of connections) {
        try {
          await apiGwClient.send(new PostToConnectionCommand({
            ConnectionId: conn.connection_id,
            Data: Buffer.from(JSON.stringify(wsMessage))
          }));
          console.log(`[WebSocket]    ✅ Sent to ${conn.connection_id}`);
        } catch (err) {
          console.log(`[WebSocket]    ❌ Failed: ${err.message}`);
        }
      }
    } catch (error) {
      console.log(`[WebSocket] ❌ Error: ${error.message}`);
    }
  };

  // Fallback functions
  logger = { info: console.log, error: console.error, warning: console.warn };
  updateVideoSession = async () => {};
  trackVideoDownloadTime = () => {};
}

// Storage helper - works with S3, R2, B2, and any S3-compatible storage
// AWS SDK v3 automatically uses SigV4 signatures for all S3-compatible services
function getStorageClient() {
  const endpoint = process.env.R2_ENDPOINT || process.env.STORAGE_ENDPOINT;
  const accessKey = process.env.R2_ACCESS_KEY || process.env.AWS_ACCESS_KEY_ID;
  const secretKey =
    process.env.R2_SECRET_KEY || process.env.AWS_SECRET_ACCESS_KEY;
  const region = process.env.AWS_REGION || "auto";

  const config = {
    credentials: {
      accessKeyId: accessKey,
      secretAccessKey: secretKey,
    },
    region: region,
  };

  if (endpoint) {
    console.log(`[Storage] Using custom endpoint: ${endpoint}`);
    config.endpoint = endpoint;
    config.forcePathStyle = true; // Required for R2 and S3-compatible storage
  } else {
    console.log("[Storage] Using AWS S3 (default)");
  }

  return new S3Client(config);
}

const s3 = getStorageClient();
const BUCKET_NAME = process.env.BUCKET_NAME || "opus-clip-videos";
const COOKIES_S3_KEY = process.env.COOKIES_S3_KEY || null; // Optional: youtube-cookies.txt
const QUALITY_MODE = process.env.QUALITY_MODE || "balanced"; // 'fast', 'balanced', 'best'
const SKIP_INFO_FETCH =
  (process.env.SKIP_INFO_FETCH || "false").toLowerCase() === "true";
const YTDLP_PATH = process.env.YTDLP_PATH || "/opt/bin/yt-dlp";

// S3 Transfer configuration for faster uploads (matches Python's TransferConfig)
const TRANSFER_CONFIG = {
  queueSize: 10, // max_concurrency in Python
  partSize: 1024 * 1024 * 25, // 25 MB (multipart_chunksize in Python)
};

// S3 Prefix Sharding for high throughput
const ENABLE_S3_SHARDING = (process.env.ENABLE_S3_SHARDING || 'true').toLowerCase() === 'true';

/**
 * Generate S3 prefix with hash-based sharding for higher throughput.
 *
 * Structure: users/{hash_prefix}/{user_id}/{session_id}/
 *
 * This distributes load across 256 prefixes (16^2) instead of 1.
 * Throughput: 3,500 PUTs/sec → 896,000 PUTs/sec
 *
 * @param {string} user_id - User identifier
 * @param {string} session_id - Session identifier
 * @returns {string} S3 prefix path without trailing slash
 */
function getS3Prefix(user_id, session_id) {
  if (ENABLE_S3_SHARDING && user_id) {
    // Hash user_id to get consistent prefix (using Node.js crypto)
    const crypto = require('crypto');
    const hash = crypto.createHash('md5').update(user_id).digest('hex');

    // Use first 2 characters as shard key (256 possible values: 00-ff)
    const shardPrefix = hash.substring(0, 2);

    // Full prefix with sharding
    return `users/${shardPrefix}/${user_id}/${session_id}`;
  } else {
    // Legacy prefix structure (for backwards compatibility) or if user_id not available
    return `users/${user_id || 'unknown'}/${session_id}`;
  }
}

/**
 * Generate S3 key for video file.
 *
 * @param {string} user_id - User identifier
 * @param {string} session_id - Session identifier
 * @param {string} filename - Video filename (default: original_video.mp4)
 * @returns {string} Full S3 key path
 */
function getVideoKey(user_id, session_id, filename = 'original_video.mp4') {
  const prefix = getS3Prefix(user_id, session_id);
  return `${prefix}/${filename}`;
}

/**
 * CRITICAL ISSUE #6: Validate YouTube URL format to prevent injection attacks
 *
 * @param {string} url - YouTube URL to validate
 * @returns {boolean} - True if valid YouTube URL, False otherwise
 */
function validateYoutubeUrl(url) {
  if (!url || typeof url !== 'string') {
    return false;
  }

  // Remove whitespace
  url = url.trim();

  // YouTube URL patterns - must match exactly 11-character video ID
  const youtubePatterns = [
    /^https?:\/\/(www\.)?youtube\.com\/watch\?v=[\w-]{11}/,
    /^https?:\/\/youtu\.be\/[\w-]{11}/,
    /^https?:\/\/m\.youtube\.com\/watch\?v=[\w-]{11}/,
  ];

  for (const pattern of youtubePatterns) {
    if (pattern.test(url)) {
      return true;
    }
  }

  return false;
}

/**
 * Convert stream to string
 */
async function streamToString(stream) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    stream.on("data", (chunk) => chunks.push(chunk));
    stream.on("error", reject);
    stream.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
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
    const cookies_file = "/tmp/youtube-cookies.txt";
    console.log("[Download] Attempting to download cookies...");
    console.log(`[Download]   Bucket: ${BUCKET_NAME}`);
    console.log(`[Download]   Key: ${COOKIES_S3_KEY}`);
    console.log(
      `[Download]   Storage: ${process.env.R2_ENDPOINT ? "R2" : "AWS S3"}`
    );

    // Check if file exists first
    try {
      await s3.send(
        new HeadObjectCommand({
          Bucket: BUCKET_NAME,
          Key: COOKIES_S3_KEY,
        })
      );
      console.log("[Download]   File exists in bucket!");
    } catch (head_error) {
      console.log(
        `[Download]   File NOT found in bucket: ${head_error.message}`
      );
      console.log(
        `[Download]   Make sure file is uploaded to: ${BUCKET_NAME}/${COOKIES_S3_KEY}`
      );
      throw head_error;
    }

    // Download cookie file
    const response = await s3.send(
      new GetObjectCommand({
        Bucket: BUCKET_NAME,
        Key: COOKIES_S3_KEY,
      })
    );

    const cookieData = await streamToString(response.Body);
    fs.writeFileSync(cookies_file, cookieData, "utf-8");

    console.log("[Download] Cookies downloaded successfully");
    return cookies_file;
  } catch (error) {
    console.log(
      `[Download] Warning: Failed to download cookies: ${error.message}`
    );
    console.log(
      "[Download] Continuing WITHOUT cookies (will use Android client)"
    );
    return null;
  }
}

/**
 * HIGH PRIORITY ISSUE #26: Validate downloaded video file
 *
 * Validates that the downloaded file is:
 * 1. A valid video file (has video streams)
 * 2. Not corrupted
 * 3. Has acceptable duration (30s - 1 hour)
 * 4. Has acceptable file size
 *
 * @param {string} localPath - Path to downloaded video file
 * @returns {Promise<Object>} - Video validation info with duration, size, format
 * @throws {Error} - If video is invalid, corrupted, or out of acceptable range
 */
async function validateDownloadedVideo(localPath) {
  console.log('[Download] HIGH PRIORITY FIX #26: Validating downloaded video file...');

  // Check file exists
  if (!fs.existsSync(localPath)) {
    throw new Error('Downloaded file not found');
  }

  // Check file size is reasonable (min 1MB, max 2GB)
  const fileSize = fs.statSync(localPath).size;
  const fileSizeMB = fileSize / (1024 * 1024);
  console.log(`[Download] File size: ${fileSizeMB.toFixed(2)} MB`);

  if (fileSize < 1024 * 1024) {  // Less than 1MB
    throw new Error('Downloaded file too small - likely corrupted or incomplete');
  }

  if (fileSize > 2 * 1024 * 1024 * 1024) {  // More than 2GB
    throw new Error('Downloaded file too large - exceeds 2GB limit');
  }

  // Use ffprobe to validate video file
  const ffprobePath = process.env.FFPROBE_PATH || '/opt/bin/ffprobe';

  try {
    // Get video metadata using ffprobe
    const probeArgs = [
      '-v', 'error',
      '-show_entries', 'format=duration,format_name:stream=codec_type,codec_name',
      '-of', 'json',
      localPath
    ];

    const probeResult = await new Promise((resolve, reject) => {
      const ffprobe = spawn(ffprobePath, probeArgs);
      let stdout = '';
      let stderr = '';

      ffprobe.stdout.on('data', (data) => { stdout += data.toString(); });
      ffprobe.stderr.on('data', (data) => { stderr += data.toString(); });

      const timeoutId = setTimeout(() => {
        ffprobe.kill();
        reject(new Error('Video validation timeout - file may be corrupted'));
      }, 30000);  // 30 second timeout

      ffprobe.on('close', (code) => {
        clearTimeout(timeoutId);
        if (code === 0) {
          resolve({ stdout, stderr });
        } else {
          reject(new Error(`ffprobe error: ${stderr || stdout}`));
        }
      });

      ffprobe.on('error', (err) => {
        clearTimeout(timeoutId);
        reject(new Error(`Failed to spawn ffprobe: ${err.message}`));
      });
    });

    const probeData = JSON.parse(probeResult.stdout);

    // Validate format exists
    if (!probeData.format) {
      throw new Error('Invalid video file - no format information found');
    }

    // Validate duration
    if (!probeData.format.duration) {
      throw new Error('Invalid video file - no duration information found');
    }

    const duration = parseFloat(probeData.format.duration);
    console.log(`[Download] Video duration: ${duration.toFixed(2)} seconds`);

    // Check duration range (30 seconds - 1 hour)
    if (duration < 30) {
      throw new Error(`Video too short - must be at least 30 seconds (got ${duration.toFixed(1)}s)`);
    }

    if (duration > 3600) {
      throw new Error(`Video too long - must be less than 1 hour (got ${(duration / 60).toFixed(1)} minutes)`);
    }

    // Validate video streams exist
    if (!probeData.streams || probeData.streams.length === 0) {
      throw new Error('Invalid video file - no stream information found');
    }

    let hasVideoStream = false;
    let videoCodec = null;

    for (const stream of probeData.streams) {
      if (stream.codec_type === 'video') {
        hasVideoStream = true;
        videoCodec = stream.codec_name || 'unknown';
        break;
      }
    }

    if (!hasVideoStream) {
      throw new Error('Invalid video file - no video stream found (audio-only or corrupted)');
    }

    console.log(`[Download] Video codec: ${videoCodec}`);
    console.log(`[Download] Format: ${probeData.format.format_name || 'unknown'}`);
    console.log('[Download] ✓ Video file validation passed!');

    return {
      duration: duration,
      size_mb: fileSizeMB,
      codec: videoCodec,
      format: probeData.format.format_name || 'unknown'
    };

  } catch (error) {
    throw new Error(`Video validation failed: ${error.message}`);
  }
}

/**
 * HIGH PRIORITY ISSUE #19: Retry wrapper with exponential backoff
 *
 * Retries a function with exponential backoff on failure.
 * Delays: 1s, 2s, 4s (3 attempts total)
 *
 * @param {Function} fn - Async function to retry
 * @param {number} maxAttempts - Maximum retry attempts (default: 3)
 * @param {string} operationName - Name for logging
 * @returns {Promise} - Result of the function
 */
async function retryWithBackoff(fn, maxAttempts = 3, operationName = 'operation') {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      console.log(`[Download] HIGH PRIORITY FIX #19: Attempting ${operationName} (attempt ${attempt}/${maxAttempts})...`);
      const result = await fn();
      if (attempt > 1) {
        console.log(`[Download] ✓ ${operationName} succeeded on attempt ${attempt}`);
      }
      return result;
    } catch (error) {
      console.log(`[Download] ✗ ${operationName} failed on attempt ${attempt}: ${error.message}`);

      if (attempt === maxAttempts) {
        console.log(`[Download] All ${maxAttempts} attempts failed for ${operationName}`);
        throw error;
      }

      // Exponential backoff: 1s, 2s, 4s
      const delaySeconds = Math.pow(2, attempt - 1);
      console.log(`[Download] Waiting ${delaySeconds}s before retry...`);
      await new Promise(resolve => setTimeout(resolve, delaySeconds * 1000));
    }
  }
}

/**
 * Run yt-dlp command and return output
 */
function runYtdlp(args, options = {}) {
  return new Promise((resolve, reject) => {
    const timeout = options.timeout || 240000; // Default 4 minutes

    if (!options.silent) {
      console.log(`[Download] Running: ${YTDLP_PATH} ${args.join(" ")}`);
    }

    const ytdlp = spawn(YTDLP_PATH, args, {
      cwd: "/tmp",
    });

    let stdout = "";
    let stderr = "";
    let timeoutId;

    // Set timeout
    if (timeout) {
      timeoutId = setTimeout(() => {
        ytdlp.kill();
        reject(new Error(`Command timed out after ${timeout}ms`));
      }, timeout);
    }

    if (ytdlp.stdout) {
      ytdlp.stdout.on("data", (data) => {
        stdout += data.toString();
        if (!options.silent && !options.captureOutput) {
          process.stdout.write(data);
        }
      });
    }

    if (ytdlp.stderr) {
      ytdlp.stderr.on("data", (data) => {
        stderr += data.toString();
        if (!options.silent && !options.captureOutput) {
          process.stderr.write(data);
        }
      });
    }

    ytdlp.on("close", (code) => {
      if (timeoutId) clearTimeout(timeoutId);

      if (code === 0) {
        resolve({ stdout, stderr, code });
      } else {
        reject(
          new Error(`yt-dlp exited with code ${code}: ${stderr || stdout}`)
        );
      }
    });

    ytdlp.on("error", (err) => {
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
    if (event.Payload && typeof event.Payload === "string") {
      payload = JSON.parse(event.Payload);
    } else if (event.Payload && typeof event.Payload === "object") {
      payload = event.Payload;
    }

    const session_id = payload.session_id;
    const youtube_url = payload.youtube_url;

    console.log("[Download] ===== NEW INVOCATION =====");
    console.log(`[Download] Session: ${session_id}`);
    console.log(`[Download] URL: ${youtube_url}`);
    console.log(
      `[Download] Lambda Request ID: ${context ? context.requestId : "N/A"}`
    );

    // Update session status
    if (UTILITIES_AVAILABLE) {
      try {
        await updateVideoSession(session_id, payload.user_id || 'unknown', {
          status: 'downloading',
          current_step: 'Downloading video from YouTube'
        });
        await notifyProcessingProgress(session_id, 'downloading', 5, 'Downloading video...');
        await updateSupabaseStatus(session_id, 'downloading');
      } catch (e) {
        console.log(`[Download] Warning: Session update failed: ${e.message}`);
      }
    }

    if (!session_id || !youtube_url) {
      throw new Error(
        `Missing required parameters: session_id=${session_id}, youtube_url=${youtube_url}`
      );
    }

    // CRITICAL ISSUE #6: Validate YouTube URL format to prevent injection attacks
    console.log('[Download] CRITICAL FIX #6: Validating YouTube URL...');
    if (!validateYoutubeUrl(youtube_url)) {
      throw new Error(`Invalid YouTube URL format: ${youtube_url}. Only youtube.com, youtu.be, and m.youtube.com URLs are allowed.`);
    }
    console.log('[Download] ✓ YouTube URL validation passed');

    // Clean URL
    let cleanUrl = youtube_url;
    if (youtube_url.includes("&") && youtube_url.includes("v=")) {
      const videoId = youtube_url.split("v=")[1].split("&")[0];
      cleanUrl = `https://www.youtube.com/watch?v=${videoId}`;
      console.log(`[Download] Cleaned URL: ${cleanUrl}`);
    }

    // Setup paths
    const outputFilename = `${session_id}_video.mp4`;
    localPath = path.join("/tmp", outputFilename);
    const user_id = payload.user_id || 'unknown';
    const s3_key = getVideoKey(user_id, session_id, 'original_video.mp4');
    console.log(`[Download] S3 key with sharding: ${s3_key}`);

    // Check if yt-dlp exists
    if (!fs.existsSync(YTDLP_PATH)) {
      throw new Error(
        `yt-dlp binary not found at ${YTDLP_PATH}. Make sure yt-dlp layer is attached.`
      );
    }

    // Download cookies if configured
    cookiesFile = await downloadCookies();

    let video_info;

    // Optionally skip info fetch for maximum speed (matches Python)
    if (SKIP_INFO_FETCH) {
      console.log(
        "[Download] Skipping info fetch (SKIP_INFO_FETCH=true) - going straight to download"
      );
      video_info = {
        title: "Unknown (skipped info fetch)",
        duration: 0,
        description: "",
        uploader: "Unknown",
        view_count: 0,
        thumbnail_url: "",
      };
    } else {
      // Get video info first (matches Python behavior)
      console.log("[Download] Fetching video info...");
      const infoStart = Date.now();

      const infoArgs = [
        "--dump-json",
        "--no-playlist",
        "--no-check-formats", // Skip format validation for speed
        "--skip-download", // Only get info
      ];

      // With cookies, use default client (like Python version)
      if (cookiesFile && fs.existsSync(cookiesFile)) {
        infoArgs.push("--cookies", cookiesFile);
        console.log("[Download] Using cookies with default client");
        // Don't force player_client - let yt-dlp choose automatically
      } else {
        console.log("[Download] No cookies - using android client");
        infoArgs.push("--extractor-args", "youtube:player_client=android");
        infoArgs.push(
          "--user-agent",
          "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip"
        );
      }

      infoArgs.push(cleanUrl);

      try {
        const infoResult = await runYtdlp(infoArgs, {
          timeout: 45000, // 45 seconds
          captureOutput: true,
          silent: true,
        });

        const infoTime = ((Date.now() - infoStart) / 1000).toFixed(2);
        console.log(`[Download] Info fetched in ${infoTime}s`);

        const videoData = JSON.parse(infoResult.stdout);
        video_info = {
          title: videoData.title || "Unknown",
          duration: videoData.duration || 0,
          description: (videoData.description || "").substring(0, 500),
          uploader: videoData.uploader || "Unknown",
          view_count: videoData.view_count || 0,
          thumbnail_url: videoData.thumbnail || "",
        };

        console.log(`[Download] Title: ${video_info.title}`);
        console.log(`[Download] Duration: ${video_info.duration} seconds`);

        // Check duration limit (1 hour max)
        if (video_info.duration > 3600) {
          throw new Error("Video duration exceeds 1 hour limit");
        }
      } catch (error) {
        if (error.message.includes("timed out")) {
          throw new Error("Video info fetch timeout after 45 seconds");
        }
        console.log(`[Download] yt-dlp stderr: ${error.message}`);
        throw new Error(`Failed to get video info: ${error.message}`);
      }
    }

    // Check if video already exists in storage (avoid re-downloading)
    try {
      await s3.send(
        new HeadObjectCommand({
          Bucket: BUCKET_NAME,
          Key: s3_key,
        })
      );
      console.log(`[Download] Video already exists in storage: ${s3_key}`);
      console.log("[Download] Skipping download - using existing file");

      return {
        statusCode: 200,
        session_id: session_id,
        s3_video_key: s3_key,
        video_info: video_info,
      };
    } catch (err) {
      console.log(
        "[Download] Video not found in storage, proceeding with download..."
      );
    }

    // Download video using yt-dlp (matches Python behavior)
    console.log(`[Download] Downloading to ${localPath}...`);
    const downloadStart = Date.now();

    // Determine optimal format - matches Python logic exactly
    let formatSpec;
    if (QUALITY_MODE === "fast") {
      formatSpec =
        "best[height<=480][ext=mp4]/best[height<=480]/worst[height>=360]";
      console.log("[Download] Mode: FAST - Using 480p max (smallest/fastest)");
    } else if (QUALITY_MODE === "best") {
      formatSpec = "best[height<=1080][ext=mp4]/best[height<=1080]/best";
      console.log("[Download] Mode: BEST - Using 1080p max");
    } else {
      // balanced (default)
      formatSpec =
        "best[height<=480][ext=mp4]/best[height<=480]/worst[height>=360]";
      console.log(
        "[Download] Mode: BALANCED - Using 480p (optimized for speed)"
      );
    }

    const downloadArgs = [
      "--format",
      formatSpec,
      "--output",
      localPath,
      "--no-playlist",
      "--no-continue",
      "--no-part",
      "--no-mtime",
      "--concurrent-fragments",
      "8",
      "--buffer-size",
      "128K",
      "--retries",
      "3",
      "--fragment-retries",
      "3",
      "--force-ipv4",
      "--newline",
      "--progress",
    ];

    // With cookies, use default client (matches Python)
    if (cookiesFile && fs.existsSync(cookiesFile)) {
      downloadArgs.push("--cookies", cookiesFile);
    } else {
      downloadArgs.push("--extractor-args", "youtube:player_client=android");
      downloadArgs.push(
        "--user-agent",
        "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip"
      );
    }

    downloadArgs.push(cleanUrl);

    console.log(
      "[Download] Starting yt-dlp download (progress will be shown below)..."
    );
    console.log(
      `[Download] Expected file size: ~${(video_info.duration * 0.5).toFixed(
        1
      )} MB (480p estimate)`
    );

    try {
      // HIGH PRIORITY ISSUE #19: Retry yt-dlp download with exponential backoff
      await retryWithBackoff(
        async () => {
          return await runYtdlp(downloadArgs, {
            timeout: 240000, // 4 minutes
            captureOutput: false, // Let output stream to CloudWatch
          });
        },
        3,
        'yt-dlp download'
      );

      const downloadTime = ((Date.now() - downloadStart) / 1000).toFixed(2);
      const fileSize = fs.statSync(localPath).size;
      const fileSizeMB = fileSize / (1024 * 1024);
      const downloadSpeedMBps = (fileSizeMB / parseFloat(downloadTime)).toFixed(
        2
      );

      console.log(
        `[Download] yt-dlp completed in ${downloadTime}s (${downloadSpeedMBps} MB/s)`
      );
    } catch (error) {
      if (error.message.includes("timed out")) {
        throw new Error(
          "Video download timeout (4 minutes) - 480p should download faster. Check Lambda network speed."
        );
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

    // HIGH PRIORITY ISSUE #26: Validate downloaded video file (if ffprobe available)
    const SKIP_VIDEO_VALIDATION = process.env.SKIP_VIDEO_VALIDATION === 'true';
    const ffprobePath = process.env.FFPROBE_PATH || '/opt/bin/ffprobe';

    if (!SKIP_VIDEO_VALIDATION && fs.existsSync(ffprobePath)) {
      try {
        const validationInfo = await validateDownloadedVideo(localPath);
        console.log(`[Download] Video validated: ${validationInfo.duration.toFixed(1)}s, ${validationInfo.size_mb.toFixed(2)}MB, ${validationInfo.codec}, ${validationInfo.format}`);
      } catch (validationError) {
        console.log(`[Download] ✗ Video validation failed: ${validationError.message}`);
        // Clean up invalid file
        if (fs.existsSync(localPath)) {
          fs.unlinkSync(localPath);
        }
        throw new Error(`Downloaded video validation failed: ${validationError.message}`);
      }
    } else {
      console.log(`[Download] ⚠️ Skipping video validation - ffprobe not available at ${ffprobePath}`);
      console.log(`[Download] Set SKIP_VIDEO_VALIDATION=false and ensure ffprobe is in Lambda layer for validation`);
    }

    // Upload to R2/S3 with multipart for faster transfer (matches Python)
    console.log(`[Download] Uploading to S3: ${s3_key}`);
    console.log(`[Download] File size: ${fileSizeMB} MB`);
    const uploadStart = Date.now();

    try {
      const fileStream = fs.createReadStream(localPath);
      let lastProgress = 0;

      // Use multipart upload for files > 25MB (matches Python's transfer_config)
      if (fileSize > 25 * 1024 * 1024) {
        console.log("[Download] Using multipart upload (10 concurrent threads)");
        const upload = new Upload({
          client: s3,
          params: {
            Bucket: BUCKET_NAME,
            Key: s3_key,
            Body: fileStream,
            ContentType: "video/mp4",
          },
          queueSize: TRANSFER_CONFIG.queueSize,
          partSize: TRANSFER_CONFIG.partSize,
          leavePartsOnError: false,
        });

        // Track upload progress
        upload.on("httpUploadProgress", (progress) => {
          if (progress.loaded && progress.total) {
            const percentage = ((progress.loaded / progress.total) * 100).toFixed(1);
            const uploadedMB = (progress.loaded / (1024 * 1024)).toFixed(1);
            const totalMB = (progress.total / (1024 * 1024)).toFixed(1);

            // Print every 25%
            if (Math.floor(percentage / 25) > lastProgress) {
              lastProgress = Math.floor(percentage / 25);
              console.log(`[Upload Progress] ${percentage}% (${uploadedMB}/${totalMB} MB)`);

              // Notify progress
              if (UTILITIES_AVAILABLE) {
                const overallProgress = 10 + (percentage * 0.1); // 10-20% of total pipeline
                notifyProcessingProgress(session_id, 'downloading', overallProgress, `Uploading video: ${percentage}%`).catch(() => {});
              }
            }
          }
        });

        await upload.done();
      } else {
        const upload = new Upload({
          client: s3,
          params: {
            Bucket: BUCKET_NAME,
            Key: s3_key,
            Body: fileStream,
            ContentType: "video/mp4",
          },
        });
        await upload.done();
      }

      const uploadTime = ((Date.now() - uploadStart) / 1000).toFixed(2);
      const uploadSpeedMBps = (
        parseFloat(fileSizeMB) / parseFloat(uploadTime)
      ).toFixed(2);
      console.log(
        `[Download] ✓ Upload complete in ${uploadTime}s (${uploadSpeedMBps} MB/s)`
      );
    } catch (uploadError) {
      const uploadTime = ((Date.now() - uploadStart) / 1000).toFixed(2);
      console.log(`[Download] ✗ Upload failed after ${uploadTime}s`);
      console.log(`[Download] Error: ${uploadError.message}`);
      throw new Error(`S3 upload failed: ${uploadError.message}`);
    }

    // Clean up local file
    fs.unlinkSync(localPath);

    const totalTime = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(`[Download] Complete! Total time: ${totalTime}s`);

    // Track metrics and update session
    if (UTILITIES_AVAILABLE) {
      try {
        trackVideoDownloadTime(session_id, Date.now() - startTime);
        await updateSupabaseStatus(session_id, 'downloaded');
        await updateVideoSession(session_id, payload.user_id || 'unknown', {
          status: 'downloaded',
          current_step: 'Video downloaded successfully',
          video_info: video_info
        });
      } catch (e) {
        console.log(`[Download] Warning: Metrics tracking failed: ${e.message}`);
      }
    }

    // Return format matching Python version exactly
    return {
      statusCode: 200,
      session_id: session_id,
      s3_video_key: s3_key,
      video_info: video_info,
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
