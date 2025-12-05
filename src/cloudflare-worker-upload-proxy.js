/**
 * Cloudflare Worker: R2 Upload Proxy
 *
 * This worker acts as a proxy between your frontend and R2 bucket,
 * bypassing CORS issues with direct R2 uploads from browsers.
 *
 * Deploy this to Cloudflare Workers and update your frontend to use it.
 */

// Configuration - Set these in Worker environment variables
const R2_BUCKET_NAME = 'opus-clip-videos';
const ALLOWED_ORIGINS = [
  'http://localhost:8080',
  'http://localhost:5173',
  'https://reframe-ai.netlify.app'
];

export default {
  async fetch(request, env) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return handleCORS(request);
    }

    // Get origin and verify
    const origin = request.headers.get('Origin');

    // Route requests
    const url = new URL(request.url);
    const path = url.pathname;

    if (path.startsWith('/upload/')) {
      return handleUpload(request, env, origin);
    }

    return new Response('Not Found', { status: 404 });
  }
};

/**
 * Handle CORS preflight requests
 */
function handleCORS(request) {
  const origin = request.headers.get('Origin');

  // Check if origin is allowed
  const isAllowed = ALLOWED_ORIGINS.includes(origin) || ALLOWED_ORIGINS.includes('*');

  if (!isAllowed) {
    return new Response('Forbidden', { status: 403 });
  }

  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': origin || '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-Session-Id, X-User-Id',
      'Access-Control-Max-Age': '86400',
    }
  });
}

/**
 * Add CORS headers to response
 */
function addCORSHeaders(response, origin) {
  const headers = new Headers(response.headers);
  headers.set('Access-Control-Allow-Origin', origin || '*');
  headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  headers.set('Access-Control-Allow-Headers', 'Content-Type, X-Session-Id, X-User-Id');

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

/**
 * Handle file upload to R2
 */
async function handleUpload(request, env, origin) {
  try {
    // Only allow PUT requests
    if (request.method !== 'PUT') {
      return new Response('Method not allowed', { status: 405 });
    }

    // Get session ID and user ID from headers or URL
    const url = new URL(request.url);
    const sessionId = request.headers.get('X-Session-Id') || url.searchParams.get('session_id');
    const userId = request.headers.get('X-User-Id') || url.searchParams.get('user_id');

    if (!sessionId) {
      return addCORSHeaders(
        new Response(JSON.stringify({ error: 'session_id is required' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }),
        origin
      );
    }

    // Get R2 bucket from environment
    const bucket = env.OPUS_CLIP_VIDEOS; // This is the R2 bucket binding

    // Generate R2 key
    const r2Key = `${sessionId}/uploaded_video.mp4`;

    console.log(`[Worker] Uploading to R2: ${r2Key}`);

    // Get the file data
    const fileData = await request.arrayBuffer();
    const contentType = request.headers.get('Content-Type') || 'video/mp4';

    // Upload to R2
    await bucket.put(r2Key, fileData, {
      httpMetadata: {
        contentType: contentType
      },
      customMetadata: {
        userId: userId || 'unknown',
        uploadedAt: new Date().toISOString()
      }
    });

    console.log(`[Worker] Upload successful: ${r2Key}`);

    // Return success
    return addCORSHeaders(
      new Response(JSON.stringify({
        success: true,
        session_id: sessionId,
        s3_key: r2Key,
        message: 'Upload successful'
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }),
      origin
    );

  } catch (error) {
    console.error('[Worker] Upload error:', error);

    return addCORSHeaders(
      new Response(JSON.stringify({
        error: error.message || 'Upload failed'
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }),
      origin
    );
  }
}
