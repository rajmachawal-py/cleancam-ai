/**
 * CleanCam AI — Service Worker
 * Provides offline caching for the PWA dashboard.
 *
 * Strategy:
 *   - Static assets (CSS, JS, icons): Cache-first
 *   - API calls (/complaints, /api/location): Network-first with cache fallback
 *   - Dashboard page: Network-first with offline fallback
 */

const CACHE_NAME = 'cleancam-v1';
const STATIC_ASSETS = [
    '/dashboard',
    '/static/css/dashboard.css',
    '/static/manifest.json',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
];

// Install — pre-cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Pre-caching static assets');
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// Activate — clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME)
                    .map((key) => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

// Fetch — routing strategy
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Skip non-GET requests and SSE stream
    if (event.request.method !== 'GET' || url.pathname === '/stream') {
        return;
    }

    // API calls: network-first
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/complaints')) {
        event.respondWith(networkFirst(event.request));
        return;
    }

    // Static assets & dashboard: cache-first
    event.respondWith(cacheFirst(event.request));
});

async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) return cached;

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        // Offline fallback for the dashboard page
        if (request.mode === 'navigate') {
            return caches.match('/dashboard');
        }
        return new Response('Offline', { status: 503, statusText: 'Offline' });
    }
}

async function networkFirst(request) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        const cached = await caches.match(request);
        if (cached) return cached;
        return new Response(JSON.stringify({ error: 'offline' }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' },
        });
    }
}
