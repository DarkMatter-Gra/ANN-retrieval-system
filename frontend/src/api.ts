export const DEFAULT_BASE_URL = 'http://localhost:8000/api/v1';

export type ApiResult<T> = {
  code: number;
  message: string;
  data: T;
};

export type ApiError = Error & {
  status?: number;
  code?: number;
  payload?: unknown;
};

export function normalizeBaseUrl(value: string | null | undefined) {
  const raw = String(value || DEFAULT_BASE_URL).trim();
  return raw.replace(/\/+$/, '');
}

function joinApiUrl(baseUrl: string, path: string) {
  const normalizedBase = normalizeBaseUrl(baseUrl);
  return new URL(path.replace(/^\/+/, ''), `${normalizedBase}/`).toString();
}

export function formatDateTime(value: string | number | Date | null | undefined) {
  if (!value) {
    return '-';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(date);
}

export function formatBytes(value: number | null | undefined) {
  const size = Number(value);
  if (!Number.isFinite(size) || size <= 0) {
    return '0 B';
  }

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let unitIndex = 0;
  let current = size;
  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(current >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

export function safeJsonParse<T>(value: unknown, fallback: T): T {
  const text = String(value ?? '').trim();
  if (!text) {
    return fallback;
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error('JSON 格式不正确');
  }
}

export function normalizeVectorInput(value: unknown) {
  if (Array.isArray(value)) {
    return value.map((item) => Number(item));
  }

  const text = String(value ?? '').trim();
  if (!text) {
    return [];
  }

  if (text.startsWith('[')) {
    const parsed = safeJsonParse<unknown>(text, []);
    if (!Array.isArray(parsed)) {
      throw new Error('向量必须是数组');
    }
    return parsed.map((item) => Number(item));
  }

  return text
    .split(/[,\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number(item));
}

async function parseResponse<T>(response: Response): Promise<ApiResult<T>> {
  const text = await response.text();
  let payload: ApiResult<T>;

  if (text) {
    try {
      payload = JSON.parse(text) as ApiResult<T>;
    } catch {
      payload = { code: response.status, message: text, data: null as T };
    }
  } else {
    payload = { code: response.status, message: response.statusText, data: null as T };
  }

  if (!response.ok || (typeof payload.code === 'number' && payload.code !== 0)) {
    const error: ApiError = new Error(payload.message || response.statusText || 'request failed');
    error.status = response.status;
    error.code = payload.code ?? response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export async function apiCall<T>({
  baseUrl,
  token,
  path,
  method = 'GET',
  query,
  body,
  formData,
  headers = {},
}: {
  baseUrl: string;
  token?: string;
  path: string;
  method?: string;
  query?: Record<string, string | number | boolean | null | undefined>;
  body?: unknown;
  formData?: FormData;
  headers?: Record<string, string>;
}) {
  const url = new URL(joinApiUrl(baseUrl, path));

  if (query && typeof query === 'object') {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === '') {
        continue;
      }
      url.searchParams.set(key, String(value));
    }
  }

  const requestHeaders = new Headers(headers);
  requestHeaders.set('Accept', 'application/json');
  if (token) {
    requestHeaders.set('Authorization', `Bearer ${token}`);
  }

  const options: RequestInit = { method, headers: requestHeaders };
  if (formData) {
    options.body = formData;
  } else if (body !== undefined) {
    requestHeaders.set('Content-Type', 'application/json');
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);
  return parseResponse<T>(response);
}

export function statusLabel(status?: string | null) {
  const map: Record<string, string> = {
    pending: '待处理',
    running: '运行中',
    done: '已完成',
    passed: '已通过',
    failed: '失败',
    success: '成功',
    active: '启用',
    inactive: '停用',
  };

  return map[status || ''] || status || '-';
}

export function isTerminalStatus(status?: string | null): boolean {
  return status === 'done' || status === 'failed' || status === 'passed' || status === 'success';
}

export function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

export function paletteForIndex(index: number) {
  const palette = ['#69e2c3', '#7fa8ff', '#ffbf69', '#ff7272', '#b892ff', '#9be564', '#58d4ff', '#ff8fab'];
  return palette[index % palette.length];
}
