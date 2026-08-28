export const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export const COOKIE = {
  accessToken: "aipm_at",
  refreshToken: "aipm_rt",
  csrf: "aipm_csrf",
} as const;
