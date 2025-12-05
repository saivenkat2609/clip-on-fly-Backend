/**
 * Lambda Function: Handle Video Upload (Direct Upload Flow)
 * Generates pre-signed URLs for direct S3/R2 upload from client
 * This avoids API Gateway size limits and provides faster uploads
 */

const { S3Client, HeadObjectCommand, PutObjectCommand } = require('@aws-sdk/client-s3');
const { getSignedUrl } = require('@aws-sdk/s3-request-presigner');

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
const MAX_FILE_SIZE = parseInt(process.env.MAX_FILE_SIZE || '524288000'); // 500MB default
const UPLOAD_EXPIRY = parseInt(process.env.UPLOAD_EXPIRY || '3600'); // 1 hour

/**
 * Generate pre-signed upload URL
 */
async function generateUploadUrl(session_id, fileName, fileSize, contentType) {
    console.log(`[Upload] Generating upload URL for session: ${session_id}`);
    console.log(`[Upload] File: ${fileName}, Size: ${(fileSize / 1024 / 1024).toFixed(2)} MB`);

    // Validate file size
    if (fileSize > MAX_FILE_SIZE) {
        throw new Error(`File size ${(fileSize / 1024 / 1024).toFixed(2)} MB exceeds limit of ${(MAX_FILE_SIZE / 1024 / 1024).toFixed(2)} MB`);
    }

    // Validate content type
    const allowedTypes = ['video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska'];
    if (!allowedTypes.includes(contentType)) {
        console.log(`[Upload] Warning: Uncommon content type: ${contentType}`);
    }

    const s3Key = `${session_id}/uploaded_video.mp4`;

    const command = new PutObjectCommand({
        Bucket: BUCKET_NAME,
        Key: s3Key,
        ContentType: contentType,
        ContentLength: fileSize
    });

    const uploadUrl = await getSignedUrl(s3, command, {
        expiresIn: UPLOAD_EXPIRY
    });

    console.log(`[Upload] Generated pre-signed URL (expires in ${UPLOAD_EXPIRY}s)`);

    return {
        uploadUrl,
        s3Key,
        expiresIn: UPLOAD_EXPIRY
    };
}

/**
 * Verify uploaded file exists
 */
async function verifyUpload(s3Key) {
    try {
        console.log(`[Upload] Verifying upload: ${s3Key}`);

        const response = await s3.send(new HeadObjectCommand({
            Bucket: BUCKET_NAME,
            Key: s3Key
        }));

        const fileSizeMB = (response.ContentLength / 1024 / 1024).toFixed(2);
        console.log(`[Upload] Verified! Size: ${fileSizeMB} MB`);

        return {
            exists: true,
            size: response.ContentLength,
            contentType: response.ContentType,
            lastModified: response.LastModified
        };
    } catch (error) {
        console.log(`[Upload] Verification failed: ${error.message}`);
        return {
            exists: false,
            error: error.message
        };
    }
}

/**
 * Main Lambda handler
 */
exports.handler = async (event, context) => {
    if (context) {
        context.callbackWaitsForEmptyEventLoop = false;
    }

    try {
        // Handle Step Functions invocation
        let payload = event;
        if (event.Payload && typeof event.Payload === 'string') {
            payload = JSON.parse(event.Payload);
        } else if (event.Payload && typeof event.Payload === 'object') {
            payload = event.Payload;
        }

        const action = payload.action || 'verify';
        const session_id = payload.session_id;

        console.log('[Upload] ===== NEW INVOCATION =====');
        console.log(`[Upload] Action: ${action}`);
        console.log(`[Upload] Session: ${session_id}`);

        if (!session_id) {
            throw new Error('Missing required parameter: session_id');
        }

        // Action: Generate pre-signed URL (called from API Gateway)
        if (action === 'generate') {
            const { fileName, fileSize, contentType } = payload;

            if (!fileName || !fileSize || !contentType) {
                throw new Error('Missing required parameters: fileName, fileSize, contentType');
            }

            const result = await generateUploadUrl(session_id, fileName, fileSize, contentType);

            return {
                statusCode: 200,
                session_id: session_id,
                ...result
            };
        }

        // Action: Verify upload (called from Step Functions)
        if (action === 'verify') {
            const s3Key = payload.s3_video_key || `${session_id}/uploaded_video.mp4`;

            const verification = await verifyUpload(s3Key);

            if (!verification.exists) {
                throw new Error(`Upload not found or verification failed: ${verification.error}`);
            }

            console.log('[Upload] Verification complete! Ready for processing.');

            return {
                statusCode: 200,
                session_id: session_id,
                s3_video_key: s3Key,
                video_info: {
                    title: payload.video_title || 'Uploaded Video',
                    duration: 0, // Will be detected during transcription
                    description: payload.video_description || '',
                    uploader: payload.user_email || 'Unknown',
                    view_count: 0,
                    thumbnail_url: ''
                },
                file_size: verification.size,
                content_type: verification.contentType
            };
        }

        throw new Error(`Unknown action: ${action}`);

    } catch (error) {
        console.error(`[Upload] Error: ${error.message}`);
        console.error(error.stack);
        throw new Error(`Upload handler failed: ${error.message}`);
    }
};
