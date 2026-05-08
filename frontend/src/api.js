const configuredBase = import.meta.env.VITE_API_BASE_URL || "";
const browserHost = window.location.hostname;
const browserProtocol = window.location.protocol;

// When the app is opened from a VM IP such as http://192.168.x.x:5173,
// a build-time value of http://localhost:8000 points to the user's host machine,
// not the VM. Fall back to the same hostname on port 8000 so local VM/AWS use works.
function resolveApiBase() {
  const localHosts = ["localhost", "127.0.0.1", "0.0.0.0"];
  if (configuredBase && !(configuredBase.includes("localhost") && !localHosts.includes(browserHost))) {
    return configuredBase;
  }
  return `${browserProtocol}//${browserHost}:8000`;
}

const API_BASE = resolveApiBase();

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch (err) {
    throw new Error(`Cannot reach backend at ${API_BASE}. Open ${API_BASE}/api/health or expose/forward port 8000. Original error: ${err.message}`);
  }
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  base: API_BASE,
  health: () => request("/api/health"),
  catalogue: () => request("/api/catalogue"),
  sources: () => request("/api/sources"),
  trust: () => request("/api/trust"),
  audit: () => request("/api/audit?limit=50"),
  algorithm: () => request("/api/algorithm"),
  runQuery: (payload) => request("/api/query", { method: "POST", body: JSON.stringify(payload) }),
};
