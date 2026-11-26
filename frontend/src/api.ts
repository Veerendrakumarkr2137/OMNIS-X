import axios from "axios";
export const isDemoWorkspace = /^\/demo(?:\/|$)/.test(window.location.pathname);
export const api = axios.create({
  baseURL: isDemoWorkspace ? "/demo/api" : "/api",
  timeout: 45000,
});
export const get = async <T>(path: string): Promise<T> =>
  (await api.get(path)).data;
export function errorText(e: unknown) {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => x.msg).join(". ");
    if (!e.response) return "The campus server is unavailable. Try again.";
  }
  return "The request could not be completed.";
}
