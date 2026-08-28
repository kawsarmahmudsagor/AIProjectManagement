import { apiFetch } from "@/lib/api-client";

export type ProfileOut = {
  photo_url: string | null;
  designation: string | null;
  team: string | null;
  organization: string | null;
  speciality: string | null;
  primary_skills: string[];
  secondary_skills: string[];
  professional_biography: string;
  work_experience_summary: string;
  career_objective: string;
  key_strengths: string;
  responsibilities: string;
  first_name: string;
  middle_name: string | null;
  last_name: string | null;
  preferred_name: string | null;
};

export type ProfileUpdatePayload = Partial<Omit<ProfileOut, "photo_url">>;

export const ENHANCEABLE_FIELDS = [
  "professional_biography",
  "work_experience_summary",
  "career_objective",
  "key_strengths",
  "responsibilities",
] as const;
export type EnhanceableField = (typeof ENHANCEABLE_FIELDS)[number];

export async function getProfile(): Promise<ProfileOut> {
  return apiFetch<ProfileOut>("profile");
}

export async function updateProfile(payload: ProfileUpdatePayload): Promise<ProfileOut> {
  return apiFetch<ProfileOut>("profile", { method: "PATCH", body: JSON.stringify(payload) });
}

export async function enhanceProfileField(args: {
  field: EnhanceableField;
  target_text: string;
  signal?: AbortSignal;
}): Promise<string> {
  const result = await apiFetch<{ text: string }>("profile/enhance", {
    method: "POST",
    signal: args.signal,
    body: JSON.stringify({ field: args.field, target_text: args.target_text }),
  });
  return result.text;
}

export async function uploadProfilePhoto(file: File): Promise<{ photo_url: string }> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<{ photo_url: string }>("profile/photo", { method: "POST", body: form });
}

export async function deleteProfilePhoto(): Promise<void> {
  await apiFetch("profile/photo", { method: "DELETE" });
}
