import { writable } from 'svelte/store';

const STORAGE_KEY = 'simulation-run-history';
const MAX_RUNS = 50;
const MAX_CSV_ROWS = 100;

function loadFromStorage() {
    if (typeof window === 'undefined') return [];
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch {
        return [];
    }
}

function saveToStorage(runs) {
    if (typeof window === 'undefined') return;
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(runs));
    } catch (e) {
        console.error('Failed to save run history:', e);
        // If quota exceeded, try removing oldest runs
        if (e.name === 'QuotaExceededError') {
            const trimmed = runs.slice(0, Math.floor(runs.length / 2));
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
            } catch {
                // Give up on storage
            }
        }
    }
}

function createRunHistoryStore() {
    const { subscribe, set, update } = writable(loadFromStorage());

    return {
        subscribe,

        addRun: (runData) => {
            const run = {
                id: crypto.randomUUID(),
                timestamp: Date.now(),
                ...runData,
                // Limit CSV rows for storage
                csvData: runData.csvData ? {
                    headers: runData.csvData.headers,
                    rows: runData.csvData.rows.slice(0, MAX_CSV_ROWS)
                } : null
            };

            update(runs => {
                const newRuns = [run, ...runs].slice(0, MAX_RUNS);
                saveToStorage(newRuns);
                return newRuns;
            });

            return run.id;
        },

        updateRunStatus: (id, status, errorMessage, messageKey = null) => {
            update(runs => {
                const updates = { status, errorMessage };
                if (messageKey) {
                    updates.messageKey = messageKey;
                }
                const updated = runs.map(r =>
                    r.id === id ? { ...r, ...updates } : r
                );
                saveToStorage(updated);
                return updated;
            });
        },

        deleteRun: (id) => {
            update(runs => {
                const filtered = runs.filter(r => r.id !== id);
                saveToStorage(filtered);
                return filtered;
            });
        },

        updateRunCompletion: (id, resultData) => {
            update(runs => {
                const updated = runs.map(r => {
                    if (r.id !== id) return r;

                    // Check for family result (aggregated across all variants)
                    // _family_passed is true if ANY run in the family passed
                    const familyPassed = resultData._family_passed;
                    const isVariant = resultData._is_variant;

                    // Extract validation info from result data
                    const validation = resultData.validation || {};
                    const passed = familyPassed ?? validation.passed ?? resultData.validation_passed;
                    const reason = validation.reason ?? resultData.validation_reason ?? '';
                    const maxHeight = validation.calculated_value ?? resultData.validation_calculated_value;

                    // If result is from a variant, store the variant's message key
                    const bestMessageKey = isVariant ? resultData.message_key : null;

                    return {
                        ...r,
                        completionStatus: resultData.status === 'timeout' ? 'timeout' : 'complete',
                        validationPassed: passed,
                        validationReason: reason,
                        maxHeight: maxHeight,
                        bestVariantKey: bestMessageKey,  // Key of the best passing variant (if any)
                        familyTotalRuns: resultData._family_total_runs,
                        familyPassedCount: resultData._family_passed_count
                    };
                });
                saveToStorage(updated);
                return updated;
            });
        },

        clearAll: () => {
            set([]);
            saveToStorage([]);
        }
    };
}

export const runHistory = createRunHistoryStore();
