/**
 * Cloudflare Worker: Cleanup Expired Video Clips from R2
 *
 * Schedule: Run daily via Cron Trigger
 * Purpose: Delete clips older than 3 days from R2 bucket
 *
 * Setup:
 * 1. Deploy this worker to Cloudflare
 * 2. Add R2 binding named "R2_BUCKET"
 * 3. Set environment variables:
 *    - FIREBASE_PROJECT_ID
 *    - FIREBASE_WEB_API_KEY
 * 4. Add Cron Trigger: "0 2 * * *" (runs daily at 2 AM UTC)
 */

export default {
  /**
   * Scheduled cleanup (runs daily)
   */
  async scheduled(event, env, ctx) {
    console.log('[Cleanup] Starting scheduled cleanup job');

    try {
      const stats = await cleanupExpiredClips(env);

      console.log('[Cleanup] Job completed successfully');
      console.log(`[Cleanup] Deleted ${stats.deletedClips} expired clips from R2`);
      console.log(`[Cleanup] Updated ${stats.updatedVideos} Firestore documents`);

      return stats;
    } catch (error) {
      console.error('[Cleanup] Job failed:', error);
      throw error;
    }
  },

  /**
   * HTTP endpoint for manual trigger
   */
  async fetch(request, env, ctx) {
    // Verify authorization (simple token auth)
    const authHeader = request.headers.get('Authorization');
    const expectedToken = env.CLEANUP_AUTH_TOKEN;

    if (expectedToken && authHeader !== `Bearer ${expectedToken}`) {
      return new Response('Unauthorized', { status: 401 });
    }

    try {
      const stats = await cleanupExpiredClips(env);

      return new Response(JSON.stringify({
        success: true,
        ...stats,
        timestamp: new Date().toISOString()
      }), {
        headers: { 'Content-Type': 'application/json' }
      });
    } catch (error) {
      return new Response(JSON.stringify({
        success: false,
        error: error.message
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
};

/**
 * Main cleanup logic
 */
async function cleanupExpiredClips(env) {
  const { R2_BUCKET, FIREBASE_PROJECT_ID, FIREBASE_WEB_API_KEY } = env;

  if (!R2_BUCKET) {
    throw new Error('R2_BUCKET binding not configured');
  }

  const now = Date.now();
  let deletedClips = 0;
  let updatedVideos = 0;
  const processedVideos = new Set();

  console.log('[Cleanup] Fetching all clips from R2...');

  // List all objects in the clips directory
  // R2 path structure: users/{userId}/{sessionId}/clips/clip_N.mp4
  const listOptions = {
    prefix: 'users/',
    include: ['customMetadata']
  };

  let cursor;
  do {
    const listed = await R2_BUCKET.list({ ...listOptions, cursor });
    cursor = listed.truncated ? listed.cursor : undefined;

    for (const object of listed.objects) {
      // Only process clip files
      if (!object.key.includes('/clips/clip_')) {
        continue;
      }

      // Check if expired
      // Objects older than 3 days are expired
      const uploadTime = object.uploaded.getTime();
      const age = now - uploadTime;
      const threeDaysInMs = 3 * 24 * 60 * 60 * 1000;

      if (age > threeDaysInMs) {
        console.log(`[Cleanup] Deleting expired clip: ${object.key} (age: ${Math.floor(age / (24 * 60 * 60 * 1000))} days)`);

        // Delete from R2
        await R2_BUCKET.delete(object.key);
        deletedClips++;

        // Parse user_id and session_id from key
        // Format: users/{userId}/{sessionId}/clips/clip_N.mp4
        const pathParts = object.key.split('/');
        if (pathParts.length >= 4 && pathParts[0] === 'users') {
          const userId = pathParts[1];
          const sessionId = pathParts[2];
          const videoKey = `${userId}:${sessionId}`;

          // Mark video for Firestore update (only once per video)
          if (!processedVideos.has(videoKey)) {
            processedVideos.add(videoKey);

            // Update Firestore to mark video as expired
            try {
              await updateFirestoreVideoExpired(userId, sessionId, FIREBASE_PROJECT_ID, FIREBASE_WEB_API_KEY);
              updatedVideos++;
            } catch (error) {
              console.error(`[Cleanup] Failed to update Firestore for ${videoKey}:`, error.message);
            }
          }
        }
      }
    }
  } while (cursor);

  return {
    deletedClips,
    updatedVideos,
    processedAt: new Date().toISOString()
  };
}

/**
 * Update Firestore to mark video as expired
 */
async function updateFirestoreVideoExpired(userId, sessionId, projectId, apiKey) {
  const url = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/users/${userId}/videos/${sessionId}?key=${apiKey}&updateMask.fieldPaths=status&updateMask.fieldPaths=expiredAt`;

  const body = {
    fields: {
      status: { stringValue: 'expired' },
      expiredAt: { timestampValue: new Date().toISOString() }
    }
  };

  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Firestore update failed: ${response.status} - ${error}`);
  }

  console.log(`[Cleanup] Updated Firestore document: users/${userId}/videos/${sessionId}`);
}
