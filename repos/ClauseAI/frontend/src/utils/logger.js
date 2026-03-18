const LOG_LEVELS = {
    debug: 10,
    info: 20,
    warn: 30,
    error: 40,
};

const REDACT_KEYS = new Set([
    'password',
    'token',
    'auth',
    'auth_hash',
    'x-auth-hash',
    'authorization',
    'file_content',
    'bill_text',
    'user_bill_raw_text',
]);

const MAX_STRING_LENGTH = 1500;

function truncate(value) {
    if (value.length <= MAX_STRING_LENGTH) return value;
    return `${value.slice(0, MAX_STRING_LENGTH)}...[truncated:${value.length - MAX_STRING_LENGTH}]`;
}

function sanitize(value, depth = 0) {
    if (depth > 5) return '[max_depth_exceeded]';
    if (Array.isArray(value)) return value.map((item) => sanitize(item, depth + 1));
    if (value && typeof value === 'object') {
        return Object.entries(value).reduce((result, [key, item]) => {
            if (REDACT_KEYS.has(String(key).toLowerCase())) {
                result[key] = '[REDACTED]';
            } else {
                result[key] = sanitize(item, depth + 1);
            }
            return result;
        }, {});
    }
    if (value instanceof Error) {
        return {
            name: value.name,
            message: value.message,
            stack: value.stack,
        };
    }
    if (typeof value === 'string') return truncate(value);
    return value;
}

function resolveLevel() {
    const envLevel = import.meta.env.VITE_LOG_LEVEL;
    const level = (envLevel || (import.meta.env.DEV ? 'debug' : 'info')).toLowerCase();
    return LOG_LEVELS[level] ? level : 'info';
}

function shouldLog(messageLevel) {
    return LOG_LEVELS[messageLevel] >= LOG_LEVELS[resolveLevel()];
}

function write(level, scope, message, meta) {
    if (!shouldLog(level)) return;
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [${level.toUpperCase()}] [${scope}] ${message}`;
    const consoleFn = level === 'debug' ? console.debug : console[level];
    if (meta === undefined) {
        consoleFn(prefix);
        return;
    }
    consoleFn(prefix, sanitize(meta));
}

export function createLogger(scope) {
    return {
        debug(message, meta) {
            write('debug', scope, message, meta);
        },
        info(message, meta) {
            write('info', scope, message, meta);
        },
        warn(message, meta) {
            write('warn', scope, message, meta);
        },
        error(message, meta) {
            write('error', scope, message, meta);
        },
        child(childScope) {
            return createLogger(`${scope}:${childScope}`);
        },
    };
}
