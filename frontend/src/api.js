const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function api(path, options = {}) {
  const token = localStorage.getItem("order-audit-token");
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the HTTP status when the server response is not JSON.
    }
    throw new Error(message);
  }
  return response;
}

export async function getJson(path) {
  return (await api(path)).json();
}

export async function postJson(path, payload) {
  return (await api(path, { method: "POST", body: JSON.stringify(payload) })).json();
}

export async function putJson(path, payload) {
  return (await api(path, { method: "PUT", body: JSON.stringify(payload) })).json();
}

export async function download(path, filename) {
  const response = await api(path);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
