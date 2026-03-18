const SUPABASE_URL = String(import.meta.env.VITE_SUPABASE_URL || '').replace(/\/+$/, '');
const SUPABASE_ANON_KEY = String(import.meta.env.VITE_SUPABASE_ANON_KEY || '');
const SESSION_STORAGE_KEY = 'clauseai.supabase.session.v1';
const DEFAULT_BUCKET = String(import.meta.env.VITE_SUPABASE_USER_FILES_BUCKET || 'user-files');

const parseFlag = (value, fallback = false) => {
    if (value == null || value === '') return fallback;
    const normalized = String(value).trim().toLowerCase();
    return ['1', 'true', 'yes', 'on'].includes(normalized);
};

const ensureConfigured = () => {
    if (!SUPABASE_URL) {
        throw new Error('Missing VITE_SUPABASE_URL');
    }
    if (!SUPABASE_ANON_KEY) {
        throw new Error('Missing VITE_SUPABASE_ANON_KEY');
    }
};

const readStoredSession = () => {
    try {
        const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return null;
        return parsed;
    } catch {
        return null;
    }
};

const writeStoredSession = (session) => {
    if (!session || typeof session !== 'object') return null;
    const expiresAt = Number(session.expires_at) || Math.floor(Date.now() / 1000) + Number(session.expires_in || 3600);
    const normalized = {
        access_token: session.access_token || null,
        refresh_token: session.refresh_token || null,
        token_type: session.token_type || 'bearer',
        expires_in: Number(session.expires_in || Math.max(1, expiresAt - Math.floor(Date.now() / 1000))),
        expires_at: expiresAt,
        user: session.user || null,
    };
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(normalized));
    return normalized;
};

const clearStoredSession = () => {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
};

const parseCallbackSession = () => {
    const hashParams = new URLSearchParams((window.location.hash || '').replace(/^#/, ''));
    const queryParams = new URLSearchParams(window.location.search || '');

    const accessToken = hashParams.get('access_token') || queryParams.get('access_token');
    const refreshToken = hashParams.get('refresh_token') || queryParams.get('refresh_token');
    const expiresIn = Number(hashParams.get('expires_in') || queryParams.get('expires_in') || 3600);
    const tokenType = hashParams.get('token_type') || queryParams.get('token_type') || 'bearer';

    if (!accessToken) return null;

    return {
        access_token: accessToken,
        refresh_token: refreshToken,
        expires_in: expiresIn,
        expires_at: Math.floor(Date.now() / 1000) + expiresIn,
        token_type: tokenType,
    };
};

const stripAuthParamsFromUrl = () => {
    const url = new URL(window.location.href);
    const toDelete = [
        'access_token',
        'refresh_token',
        'expires_in',
        'expires_at',
        'token_type',
        'type',
        'code',
        'error',
        'error_code',
        'error_description',
        'error_uri',
    ];
    toDelete.forEach((key) => url.searchParams.delete(key));
    url.hash = '';
    window.history.replaceState({}, document.title, `${url.pathname}${url.search}`);
};

const isExpiringSoon = (session) => {
    if (!session?.expires_at) return false;
    const now = Math.floor(Date.now() / 1000);
    return now >= (Number(session.expires_at) - 60);
};

const refreshSession = async (refreshToken) => {
    ensureConfigured();
    if (!refreshToken) return null;

    const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
        method: 'POST',
        headers: {
            apikey: SUPABASE_ANON_KEY,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) return null;
    const payload = await response.json().catch(() => null);
    if (!payload?.access_token) return null;
    return writeStoredSession(payload);
};

const getAuthHeaders = (accessToken = null, includeJson = true) => {
    const headers = {
        apikey: SUPABASE_ANON_KEY,
    };
    if (includeJson) headers['Content-Type'] = 'application/json';
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    return headers;
};

export const isSignupAllowed = () => parseFlag(import.meta.env.VITE_SUPABASE_ALLOW_SIGNUP, true);

export const getUserFilesBucket = () => DEFAULT_BUCKET;

export const consumeAuthCallback = () => {
    try {
        const session = parseCallbackSession();
        if (!session) return null;
        const stored = writeStoredSession(session);
        stripAuthParamsFromUrl();
        return stored;
    } catch {
        return null;
    }
};

export const getSession = async () => {
    const stored = readStoredSession();
    if (!stored?.access_token) return null;

    if (isExpiringSoon(stored) && stored.refresh_token) {
        const refreshed = await refreshSession(stored.refresh_token);
        if (refreshed?.access_token) return refreshed;
        clearStoredSession();
        return null;
    }

    return stored;
};

export const getAccessToken = async () => {
    const session = await getSession();
    return session?.access_token || null;
};

export const sendMagicLink = async (email, { shouldCreateUser = true, redirectTo = null } = {}) => {
    ensureConfigured();
    const trimmed = String(email || '').trim();
    if (!trimmed) {
        throw new Error('Email is required');
    }

    const body = {
        email: trimmed,
        create_user: Boolean(shouldCreateUser),
    };
    if (redirectTo) body.email_redirect_to = redirectTo;

    const response = await fetch(`${SUPABASE_URL}/auth/v1/otp`, {
        method: 'POST',
        headers: getAuthHeaders(null, true),
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error_description || payload.msg || payload.message || 'Failed to send magic link');
    }

    return response.json().catch(() => ({}));
};

export const getCurrentUser = async () => {
    ensureConfigured();
    const accessToken = await getAccessToken();
    if (!accessToken) return null;

    const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
        method: 'GET',
        headers: getAuthHeaders(accessToken, false),
    });

    if (response.status === 401) {
        clearStoredSession();
        return null;
    }
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error_description || payload.message || 'Failed to load current user');
    }

    return response.json();
};

export const uploadUserFile = async (file, path, bucket = DEFAULT_BUCKET) => {
    ensureConfigured();
    const accessToken = await getAccessToken();
    if (!accessToken) {
        throw new Error('Authentication required');
    }
    if (!file) {
        throw new Error('File is required');
    }
    if (!path) {
        throw new Error('Storage path is required');
    }

    const encodedBucket = encodeURIComponent(bucket);
    const encodedPath = String(path)
        .split('/')
        .map((segment) => encodeURIComponent(segment))
        .join('/');

    const response = await fetch(`${SUPABASE_URL}/storage/v1/object/${encodedBucket}/${encodedPath}`, {
        method: 'POST',
        headers: {
            ...getAuthHeaders(accessToken, false),
            'x-upsert': 'true',
            'Content-Type': file.type || 'application/octet-stream',
        },
        body: file,
    });

    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || payload.message || 'Failed to upload file');
    }

    return response.json().catch(() => ({}));
};
