let accessToken = null;

export function setAccessToken(token) {
  accessToken = token || null;
}

async function parse(response) {
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || data.message || 'Yêu cầu không thành công';
    const validationMessage = Array.isArray(detail)
      ? detail.map(item => {
          const field = Array.isArray(item.loc) ? item.loc.filter(part => part !== 'body').join('.') : '';
          return `${field ? `${field}: ` : ''}${item.msg || 'Dữ liệu không hợp lệ'}`;
        }).join('; ')
      : null;
    const error = new Error(
      typeof detail === 'string'
        ? detail
        : validationMessage || detail.message || 'Yêu cầu không thành công'
    );
    error.status = response.status;
    error.detail = detail;
    throw error;
  }
  return data;
}

export async function api(path, options = {}, retry = true) {
  const headers = { ...options.headers };
  if (!(options.body instanceof FormData)) headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetch(path, { ...options, headers, credentials: 'include' });
  if (response.status === 401 && retry && path !== '/api/auth/refresh') {
    try {
      const refreshed = await parse(await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' }));
      setAccessToken(refreshed.accessToken);
      window.dispatchEvent(new CustomEvent('auth-session-change', { detail: refreshed.user }));
      return api(path, options, false);
    } catch {
      setAccessToken(null);
      window.dispatchEvent(new CustomEvent('auth-session-change', { detail: null }));
    }
  }
  return parse(response);
}

export async function restoreAuth() {
  try {
    const data = await api('/api/auth/refresh', { method: 'POST' }, false);
    setAccessToken(data.accessToken);
    return data.user;
  } catch {
    return null;
  }
}
