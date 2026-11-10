
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const DEFAULT_TIMEOUT_MS = 15000;

export class ApiError extends Error {
  constructor(message, { status, details } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

async function request(path, options = {}) {
  const {
    timeout = DEFAULT_TIMEOUT_MS,
    signal,
    headers = {},
    ...fetchOptions
  } = options;

  const controller = new AbortController();
  let timedOut = false;

  const abortFromCaller = () => controller.abort();

  if (signal?.aborted) {
    controller.abort();
  } else {
    signal?.addEventListener("abort", abortFromCaller, { once: true });
  }

  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeout);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(fetchOptions.body ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
    });

    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    if (!response.ok) {
      const message =
        typeof body === "object" && body !== null
          ? body.detail || body.message || `Request failed (${response.status})`
          : body || `Request failed (${response.status})`;

      throw new ApiError(String(message), {
        status: response.status,
        details: body,
      });
    }

    return body;
  } catch (error) {
    if (error instanceof ApiError) throw error;

    if (timedOut) {
      throw new ApiError(`Request timed out after ${timeout}ms`);
    }

    if (error.name === "AbortError") {
      throw error;
    }

    throw new ApiError(error.message || "Network error");
  } finally {
    clearTimeout(timeoutId);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}

export const api = {
  get(path, options = {}) {
    return request(path, { ...options, method: "GET" });
  },

  post(path, body, options = {}) {
    return request(path, {
      ...options,
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  put(path, body, options = {}) {
    return request(path, {
      ...options,
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  patch(path, body, options = {}) {
    return request(path, {
      ...options,
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  delete(path, options = {}) {
    return request(path, { ...options, method: "DELETE" });
  },
};
