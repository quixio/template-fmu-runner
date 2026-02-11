import { writable, get } from 'svelte/store';
import { runHistory } from './runHistory.js';

const POLL_INTERVAL = 3000; // 3 seconds
const POLL_TIMEOUT = 300000; // 5 minutes

// Store for pending runs being polled
const pendingRuns = writable(new Map());

// Store for completion events (components can subscribe to this)
export const completionEvents = writable(null);

// Track which runs have already emitted completion events (prevents duplicates)
const completedRuns = new Set();

let pollIntervalId = null;

/**
 * Get API configuration from window globals
 */
function getApiConfig() {
    const rawApiUrl = window.__API_URL__;
    const isPlaceholder = !rawApiUrl || rawApiUrl.startsWith('__RUNTIME_');

    // Strip /simulation from the end if present to get base API URL
    // When served from same origin, use empty string for relative paths
    const apiBaseUrl = isPlaceholder
        ? ''
        : rawApiUrl.replace(/\/simulation\/?$/, '');

    const authToken = (window.__HTTP_AUTH_TOKEN__ && !window.__HTTP_AUTH_TOKEN__.startsWith('__RUNTIME_'))
        ? window.__HTTP_AUTH_TOKEN__
        : '';

    // Log config on first call to help debug
    if (!getApiConfig._logged) {
        console.log('[runPolling] API config:', { rawApiUrl, apiBaseUrl, hasAuthToken: !!authToken });
        getApiConfig._logged = true;
    }

    return { apiBaseUrl, authToken };
}

/**
 * Start polling for a run's completion
 */
export function startPolling(messageKey, runId) {
    if (!messageKey) return;

    pendingRuns.update(runs => {
        runs.set(messageKey, {
            runId,
            startTime: Date.now()
        });
        return runs;
    });

    // Start the poll loop if not already running
    if (!pollIntervalId) {
        pollIntervalId = setInterval(pollOnce, POLL_INTERVAL);
        // Also poll immediately
        pollOnce();
    }
}

/**
 * Stop polling for a specific run
 */
export function stopPolling(messageKey) {
    pendingRuns.update(runs => {
        runs.delete(messageKey);
        return runs;
    });

    // Stop the interval if no more pending runs
    const runs = get(pendingRuns);
    if (runs.size === 0 && pollIntervalId) {
        clearInterval(pollIntervalId);
        pollIntervalId = null;
    }
}

/**
 * Poll all pending runs once
 */
async function pollOnce() {
    const runs = get(pendingRuns);
    if (runs.size === 0) return;

    const { apiBaseUrl, authToken } = getApiConfig();
    const headers = {};
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    for (const [messageKey, { runId, startTime }] of runs) {
        // Check for timeout
        if (Date.now() - startTime > POLL_TIMEOUT) {
            console.log(`Polling timeout for ${messageKey}`);
            stopPolling(messageKey);
            runHistory.updateRunCompletion(runId, {
                status: 'timeout',
                validation: { passed: false, reason: 'Polling timeout - run may still be processing' }
            });
            continue;
        }

        try {
            const url = `${apiBaseUrl}/runs/${encodeURIComponent(messageKey)}/result`;
            console.log(`Polling: ${url}`);

            const response = await fetch(url, { headers });

            if (response.ok) {
                // Check content type to ensure we're getting JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    console.error(`Unexpected content type: ${contentType}`);
                    const text = await response.text();
                    console.error(`Response body (first 200 chars): ${text.substring(0, 200)}`);
                    return; // Don't process non-JSON responses
                }

                // Run is complete!
                const data = await response.json();
                console.log(`Run complete: ${messageKey}`, data);

                stopPolling(messageKey);

                // Update the run history store
                runHistory.updateRunCompletion(runId, data);

                // Emit completion event for toast notifications (only once per run)
                if (!completedRuns.has(messageKey)) {
                    completedRuns.add(messageKey);
                    completionEvents.set({
                        runId,
                        messageKey,
                        data,
                        timestamp: Date.now()
                    });
                }
            } else if (response.status === 404) {
                // Still processing - continue polling
                console.log(`Run ${messageKey} not ready yet (404)`);
            } else {
                // Other error - log it
                console.error(`Polling error for ${messageKey}: ${response.status} ${response.statusText}`);
                const text = await response.text();
                console.error(`Response: ${text.substring(0, 200)}`);
            }
        } catch (err) {
            console.error(`Error polling ${messageKey}:`, err);
            // Don't stop polling on network errors - might be temporary
        }
    }
}

/**
 * Check if a run is currently being polled
 */
export function isPolling(messageKey) {
    const runs = get(pendingRuns);
    return runs.has(messageKey);
}

/**
 * Get count of pending runs
 */
export function getPendingCount() {
    return get(pendingRuns).size;
}
