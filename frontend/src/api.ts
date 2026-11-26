import axios from "axios";
// A sleeping Render service can take more than 50 seconds to wake.
export const isDemoWorkspace = /^\/demo(?:\/|$)/.test(window.location.pathname);
export const api = axios.create({ baseURL: isDemoWorkspace ? "/demo/api" : "/api", timeout: 120000 });

export function isTransientConnectionError(e: unknown): boolean {
  if (!axios.isAxiosError(e) || axios.isCancel(e)) return false;
  const status = e.response?.status;
  return status === undefined || [502, 503, 504].includes(status);
}
export const get = async <T>(path: string): Promise<T> =>
  (await api.get(path)).data;
export function errorText(e: unknown) {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => x.msg).join(". ");
    if (isTransientConnectionError(e))
      return "The campus server may still be starting. Please retry the connection.";
  }
  return "The request could not be completed.";
}
