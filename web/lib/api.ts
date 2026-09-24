const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiCall<T>(
  method: string,
  path: string,
  body?: Record<string, unknown> | FormData
): Promise<T> {
  const url = new URL(path, API_URL).toString();
  const options: RequestInit = {
    method,
    headers: {},
  };

  if (body) {
    if (body instanceof FormData) {
      options.body = body;
    } else {
      (options.headers as Record<string, string>)["Content-Type"] =
        "application/json";
      options.body = JSON.stringify(body);
    }
  }

  const response = await fetch(url, options);

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export async function get<T>(path: string): Promise<T> {
  return apiCall<T>("GET", path);
}

export async function post<T>(
  path: string,
  body?: Record<string, unknown> | FormData
): Promise<T> {
  return apiCall<T>("POST", path, body);
}

export async function patch<T>(
  path: string,
  body?: Record<string, unknown>
): Promise<T> {
  return apiCall<T>("PATCH", path, body);
}

export function getApiUrl(path: string): string {
  return new URL(path, API_URL).toString();
}
