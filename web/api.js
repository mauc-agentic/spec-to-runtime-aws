// Cliente de la API. El navegador nunca envía usuario ni rol: los pone la API desde el token.
const { apiUrl } = window.APP_CONFIG;

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || `Error ${status}`);
    this.status = status;
    this.code = body?.code;
    this.body = body || {};
  }
}

export function createApi(getToken, onUnauthorized) {
  async function request(method, path, body) {
    let response;
    try {
      response = await fetch(apiUrl + path, {
        method,
        headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, { code: "network", message: "Sin conexión con el servidor." });
    }
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) onUnauthorized();
    if (!response.ok) throw new ApiError(response.status, data);
    return data;
  }
  return {
    ask: (prompt, profile, sessionId) =>
      request("POST", "/questions", { prompt, profile, ...(sessionId ? { session_id: sessionId } : {}) }),
    request: (id) => request("GET", `/requests/${encodeURIComponent(id)}`),
    sessions: (offset = 0) => request("GET", `/sessions?offset=${Number(offset) || 0}`),
    session: (id) => request("GET", `/sessions/${encodeURIComponent(id)}`),
    sync: () => request("POST", "/admin/sync"),
    syncStatus: () => request("GET", "/admin/sync"),
  };
}
