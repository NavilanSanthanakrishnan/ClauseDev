export const API_CONFIG = {
    BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    TIMEOUT: 600000,
    POLL_INTERVAL: 5000,
    HEALTH_CHECK_INTERVAL: 30000,
    STATUS_MIN_INTERVAL: 1000
};
