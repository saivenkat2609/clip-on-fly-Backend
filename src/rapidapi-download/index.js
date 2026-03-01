/**
 * Lambda Function: Download Video from YouTube using RapidAPI
 *
 * Features:
 * - Automatic API key rotation (10 keys, 300 requests/month each = 3000/month total)
 * - R2/S3 storage for API key usage tracking
 * - RapidAPI integration for YouTube downloads
 * - Direct URL download (no yt-dlp dependency)
 * - Integrated with shared utilities (DynamoDB, WebSocket, metrics)
 */

const {
  S3Client,
  HeadObjectCommand,
  GetObjectCommand,
  PutObjectCommand,
} = require("@aws-sdk/client-s3");
const { Upload } = require("@aws-sdk/lib-storage");
const https = require("https");
const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

// Import shared utilities
let logger,
  updateVideoSession,
  notifyProcessingProgress,
  trackVideoDownloadTime,
  UTILITIES_AVAILABLE;
try {
  const sharedUtils = require("/opt/nodejs/shared-utils");
  logger = sharedUtils.logger;
  updateVideoSession = sharedUtils.updateVideoSession;
  notifyProcessingProgress = sharedUtils.notifyProcessingProgress;
  trackVideoDownloadTime = sharedUtils.trackVideoDownloadTime;
  UTILITIES_AVAILABLE = true;
  console.log("[RapidAPI] Shared utilities loaded successfully");
} catch (e) {
  console.log(
    `[RapidAPI] Warning: Shared utilities not available: ${e.message}`
  );
  UTILITIES_AVAILABLE = false;
  logger = { info: console.log, error: console.error, warning: console.warn };
  updateVideoSession = async () => {};
  notifyProcessingProgress = async () => {};
  trackVideoDownloadTime = () => {};
}

// Storage configuration
function getStorageClient() {
  const endpoint = process.env.R2_ENDPOINT || process.env.STORAGE_ENDPOINT;
  const accessKey = process.env.R2_ACCESS_KEY || process.env.AWS_ACCESS_KEY_ID;
  const secretKey =
    process.env.R2_SECRET_KEY || process.env.AWS_SECRET_ACCESS_KEY;
  const region = process.env.AWS_REGION || "us-east-1";

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
    config.forcePathStyle = true;
  } else {
    console.log("[Storage] Using AWS S3 (default)");
  }

  return new S3Client(config);
}

const s3 = getStorageClient();
const BUCKET_NAME = process.env.BUCKET_NAME || "opus-clip-videos";
const API_KEYS_R2_KEY =
  process.env.API_KEYS_R2_KEY || "rapidapi-keys-usage.json";
const RAPIDAPI_HOST =
  process.env.RAPIDAPI_HOST ||
  "youtube-video-fast-downloader-24-7.p.rapidapi.com";

// S3 Prefix Sharding
const ENABLE_S3_SHARDING =
  (process.env.ENABLE_S3_SHARDING || "true").toLowerCase() === "true";

function getS3Prefix(user_id, session_id) {
  if (ENABLE_S3_SHARDING && user_id) {
    const crypto = require("crypto");
    const hash = crypto.createHash("md5").update(user_id).digest("hex");
    const shardPrefix = hash.substring(0, 2);
    return `users/${shardPrefix}/${user_id}/${session_id}`;
  } else {
    return `users/${user_id || "unknown"}/${session_id}`;
  }
}

function getVideoKey(user_id, session_id, filename = "original_video.mp4") {
  const prefix = getS3Prefix(user_id, session_id);
  return `${prefix}/${filename}`;
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
 * Load API keys usage data from R2
 */
async function loadApiKeysUsage() {
  try {
    console.log("[RapidAPI] Loading API keys usage from R2...");
    const response = await s3.send(
      new GetObjectCommand({
        Bucket: BUCKET_NAME,
        Key: API_KEYS_R2_KEY,
      })
    );

    const data = await streamToString(response.Body);
    const usage = JSON.parse(data);
    console.log(
      `[RapidAPI] Loaded usage data for ${usage.keys.length} API keys`
    );
    return usage;
  } catch (error) {
    if (error.name === "NoSuchKey") {
      console.log("[RapidAPI] No usage file found, creating new one");
      // Return default structure if file doesn't exist
      return {
        keys: [],
        lastReset: new Date().toISOString(),
        monthlyLimit: 300,
      };
    }
    throw error;
  }
}

/**
 * Save API keys usage data to R2
 */
async function saveApiKeysUsage(usage) {
  console.log("[RapidAPI] Saving API keys usage to R2...");
  await s3.send(
    new PutObjectCommand({
      Bucket: BUCKET_NAME,
      Key: API_KEYS_R2_KEY,
      Body: JSON.stringify(usage, null, 2),
      ContentType: "application/json",
    })
  );
  console.log("[RapidAPI] Usage data saved successfully");
}

/**
 * Get next available API key
 */
async function getNextApiKey() {
  const usage = await loadApiKeysUsage();

  // Check if we need to reset monthly counters
  const now = new Date();
  const lastReset = new Date(usage.lastReset);
  const monthsDiff =
    (now.getFullYear() - lastReset.getFullYear()) * 12 +
    (now.getMonth() - lastReset.getMonth());

  if (monthsDiff >= 1) {
    console.log("[RapidAPI] Monthly reset - resetting all counters");
    usage.keys.forEach((key) => {
      key.usedThisMonth = 0;
    });
    usage.lastReset = now.toISOString();
    await saveApiKeysUsage(usage);
  }

  // Find key with available quota
  const availableKey = usage.keys.find(
    (key) => key.enabled && key.usedThisMonth < usage.monthlyLimit
  );

  if (!availableKey) {
    throw new Error(
      "No API keys available - all keys exhausted for this month"
    );
  }

  console.log(
    `[RapidAPI] Selected API key: ${availableKey.name} (${availableKey.usedThisMonth}/${usage.monthlyLimit} used)`
  );
  return availableKey;
}

/**
 * Update API key usage after request
 */
async function incrementApiKeyUsage(keyName) {
  const usage = await loadApiKeysUsage();
  const key = usage.keys.find((k) => k.name === keyName);

  if (key) {
    key.usedThisMonth++;
    key.totalUsed++;
    key.lastUsed = new Date().toISOString();
    await saveApiKeysUsage(usage);
    console.log(
      `[RapidAPI] Updated ${keyName}: ${key.usedThisMonth}/${usage.monthlyLimit} used this month`
    );
  }
}

/**
 * Make HTTPS request
 */
function httpsRequest(url, options = {}) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const protocol = parsedUrl.protocol === "https:" ? https : http;

    const reqOptions = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || (parsedUrl.protocol === "https:" ? 443 : 80),
      path: parsedUrl.pathname + parsedUrl.search,
      method: options.method || "GET",
      headers: options.headers || {},
    };

    const req = protocol.request(reqOptions, (res) => {
      let data = "";

      res.on("data", (chunk) => {
        data += chunk;
      });

      res.on("end", () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: data,
        });
      });
    });

    req.on("error", (err) => {
      reject(err);
    });

    if (options.body) {
      req.write(options.body);
    }

    req.end();
  });
}

/**
 * Get YouTube video download URL from RapidAPI
 */
async function getYoutubeDownloadUrl(youtubeUrl, apiKey) {
  console.log("[RapidAPI] Fetching download URL from RapidAPI...");

  const videoId = extractVideoId(youtubeUrl);
  if (!videoId) {
    throw new Error("Invalid YouTube URL");
  }

  // RapidAPI endpoint (adjust based on actual API you're using)
  const apiUrl = `https://${RAPIDAPI_HOST}/download_video/%7B${videoId}%7D?quality=247`;

  const response = await httpsRequest(apiUrl, {
    method: "GET",
    headers: {
      "X-RapidAPI-Key": apiKey,
      "X-RapidAPI-Host": RAPIDAPI_HOST,
    },
  });

  if (response.statusCode !== 200) {
    throw new Error(
      `RapidAPI error: ${response.statusCode} - ${response.body}`
    );
  }

  const data = JSON.parse(response.body);

  // Extract video info and download URL (adjust based on actual API response structure)
  const videoInfo = {
    title: data.title || data.name || "Unknown",
    duration: data.lengthSeconds || data.duration || 0,
    description: (data.shortDescription || data.description || "").substring(0, 500),
    uploader: data.author || data.uploader || "Unknown",
    view_count: data.viewCount || data.views || 0,
    thumbnail_url: data.thumbnails?.[0]?.url || data.thumbnail || "",
  };

  // Check for direct file URL (some APIs return file/reserved_file fields)
  let downloadUrl = data.file || data.reserved_file;

  // If not found, try formats array (other APIs)
  if (!downloadUrl) {
    const formats = data.formats || data.adaptiveFormats || [];
    const videoFormat =
      formats.find(
        (f) => f.qualityLabel && f.qualityLabel.includes("480p") && f.url
      ) || formats.find((f) => f.url); // Fallback to any format with URL

    if (videoFormat && videoFormat.url) {
      downloadUrl = videoFormat.url;
    }
  }

  if (!downloadUrl) {
    console.log("[RapidAPI] Response data:", JSON.stringify(data, null, 2));
    throw new Error("No download URL found in RapidAPI response");
  }

  console.log(`[RapidAPI] Found download URL for: ${videoInfo.title}`);

  // Check if file needs time to be ready
  if (data.comment && data.comment.includes("soon be ready")) {
    console.log(`[RapidAPI] Note: ${data.comment}`);
  }

  return {
    downloadUrl: downloadUrl,
    videoInfo: videoInfo,
  };
}

/**
 * Extract YouTube video ID from URL
 */
function extractVideoId(url) {
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /youtube\.com\/watch\?.*?v=([a-zA-Z0-9_-]{11})/,
  ];

  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }

  return null;
}

/**
 * Download file from URL with progress tracking
 */
async function downloadFromUrl(url, localPath, session_id) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const protocol = parsedUrl.protocol === "https:" ? https : http;

    console.log("[Download] Starting download from URL...");

    const req = protocol.get(url, (res) => {
      if (res.statusCode === 302 || res.statusCode === 301) {
        // Follow redirect
        console.log("[Download] Following redirect...");
        return downloadFromUrl(res.headers.location, localPath, session_id)
          .then(resolve)
          .catch(reject);
      }

      if (res.statusCode === 404) {
        // File not ready yet, will be retried by caller
        reject(new Error(`File not ready (404)`));
        return;
      }

      if (res.statusCode !== 200) {
        reject(new Error(`Download failed with status ${res.statusCode}`));
        return;
      }

      const totalBytes = parseInt(res.headers["content-length"] || "0");
      let downloadedBytes = 0;
      let lastProgressPercent = 0;

      const fileStream = fs.createWriteStream(localPath);

      res.on("data", (chunk) => {
        downloadedBytes += chunk.length;
        fileStream.write(chunk);

        if (totalBytes > 0) {
          const progress = Math.floor((downloadedBytes / totalBytes) * 100);
          if (progress >= lastProgressPercent + 10 && UTILITIES_AVAILABLE) {
            notifyProcessingProgress(
              session_id,
              "downloading",
              progress,
              `Downloaded ${(downloadedBytes / (1024 * 1024)).toFixed(1)} MB`
            ).catch(() => {});
            lastProgressPercent = progress;
          }
        }
      });

      res.on("end", () => {
        fileStream.end();
        console.log(
          `[Download] Download complete: ${(
            downloadedBytes /
            (1024 * 1024)
          ).toFixed(2)} MB`
        );
        resolve();
      });

      res.on("error", (err) => {
        fileStream.close();
        reject(err);
      });
    });

    req.on("error", (err) => {
      reject(err);
    });

    req.setTimeout(300000, () => {
      // 5 minute timeout
      req.destroy();
      reject(new Error("Download timeout"));
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
  let selectedKey;

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
    const user_id = payload.user_id || "unknown";

    console.log("[RapidAPI] ===== NEW INVOCATION =====");
    console.log(`[RapidAPI] Session: ${session_id}`);
    console.log(`[RapidAPI] URL: ${youtube_url}`);
    console.log(`[RapidAPI] User: ${user_id}`);

    // Update session status
    if (UTILITIES_AVAILABLE) {
      try {
        await updateVideoSession(session_id, user_id, {
          status: "downloading",
          current_step: "Getting download URL from RapidAPI",
        });
        await notifyProcessingProgress(
          session_id,
          "downloading",
          5,
          "Fetching video info..."
        );
      } catch (e) {
        console.log(`[RapidAPI] Warning: Session update failed: ${e.message}`);
      }
    }

    if (!session_id || !youtube_url) {
      throw new Error(
        `Missing required parameters: session_id=${session_id}, youtube_url=${youtube_url}`
      );
    }

    // Setup paths
    const s3_key = getVideoKey(user_id, session_id, "original_video.mp4");
    console.log(`[RapidAPI] S3 key: ${s3_key}`);

    // Check if video already exists
    try {
      await s3.send(
        new HeadObjectCommand({
          Bucket: BUCKET_NAME,
          Key: s3_key,
        })
      );
      console.log(`[RapidAPI] Video already exists: ${s3_key}`);

      return {
        statusCode: 200,
        session_id: session_id,
        s3_video_key: s3_key,
        video_info: {
          title: "Existing video (skipped download)",
          duration: 0,
          description: "",
          uploader: "",
          view_count: 0,
          thumbnail_url: "",
        },
      };
    } catch (err) {
      console.log("[RapidAPI] Video not found, proceeding with download...");
    }

    // Get next available API key
    selectedKey = await getNextApiKey();

    // Get download URL from RapidAPI
    const { downloadUrl, videoInfo } = await getYoutubeDownloadUrl(
      youtube_url,
      selectedKey.apiKey
    );

    // Increment API key usage
    await incrementApiKeyUsage(selectedKey.name);

    console.log(`[RapidAPI] Video: ${videoInfo.title}`);
    console.log(`[RapidAPI] Duration: ${videoInfo.duration}s`);

    // Check duration limit
    if (videoInfo.duration > 3600) {
      throw new Error("Video duration exceeds 1 hour limit");
    }

    // Download video from URL
    const outputFilename = `${session_id}_video.mp4`;
    localPath = path.join("/tmp", outputFilename);

    console.log(`[RapidAPI] Downloading to ${localPath}...`);
    const downloadStart = Date.now();

    // Retry logic for 404 (file not ready yet)
    // API says file ready in 20-300 seconds
    let downloadAttempt = 0;
    const maxAttempts = 5;
    const retryDelays = [30000, 60000, 90000, 120000, 150000]; // 30s, 60s, 90s, 120s, 150s

    while (downloadAttempt < maxAttempts) {
      try {
        downloadAttempt++;
        console.log(`[RapidAPI] Download attempt ${downloadAttempt}/${maxAttempts}`);
        await downloadFromUrl(downloadUrl, localPath, session_id);
        break; // Success, exit loop
      } catch (err) {
        if (err.message.includes("File not ready (404)") && downloadAttempt < maxAttempts) {
          const delay = retryDelays[downloadAttempt - 1];
          console.log(`[RapidAPI] File not ready yet, waiting ${delay / 1000}s before retry...`);
          await new Promise((resolve) => setTimeout(resolve, delay));
        } else {
          throw err; // Re-throw if not 404 or max attempts reached
        }
      }
    }

    const downloadTime = ((Date.now() - downloadStart) / 1000).toFixed(2);
    console.log(`[RapidAPI] Download completed in ${downloadTime}s`);

    // Verify file exists
    if (!fs.existsSync(localPath)) {
      throw new Error(`Downloaded file not found at ${localPath}`);
    }

    const fileSize = fs.statSync(localPath).size;
    const fileSizeMB = (fileSize / (1024 * 1024)).toFixed(2);
    console.log(`[RapidAPI] Downloaded ${fileSizeMB} MB`);

    // Upload to S3/R2
    console.log(`[RapidAPI] Uploading to S3: ${s3_key}`);
    const uploadStart = Date.now();

    const fileStream = fs.createReadStream(localPath);
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

    const uploadTime = ((Date.now() - uploadStart) / 1000).toFixed(2);
    console.log(`[RapidAPI] Upload completed in ${uploadTime}s`);

    // Clean up local file
    fs.unlinkSync(localPath);

    const totalTime = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(`[RapidAPI] Total time: ${totalTime}s`);

    // Track metrics
    if (UTILITIES_AVAILABLE) {
      try {
        trackVideoDownloadTime(session_id, Date.now() - startTime);
        await updateVideoSession(session_id, user_id, {
          status: "downloaded",
          current_step: "Video downloaded successfully",
          video_info: videoInfo,
        });
      } catch (e) {
        console.log(
          `[RapidAPI] Warning: Metrics tracking failed: ${e.message}`
        );
      }
    }

    return {
      statusCode: 200,
      session_id: session_id,
      s3_video_key: s3_key,
      video_info: videoInfo,
      api_key_used: selectedKey.name,
      requests_remaining: 300 - selectedKey.usedThisMonth - 1,
    };
  } catch (error) {
    console.log(`[RapidAPI] Error: ${error.message}`);

    // Clean up
    if (localPath && fs.existsSync(localPath)) {
      try {
        fs.unlinkSync(localPath);
      } catch (e) {
        // Ignore cleanup errors
      }
    }

    throw new Error(`Failed to download video: ${error.message}`);
  }
};
