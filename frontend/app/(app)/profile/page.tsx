import { ProfileForm } from "@/components/profile/profile-form";
import { serverApiFetch } from "@/lib/server-api";
import type { ProfileOut } from "@/lib/profile";

const EMPTY_PROFILE: ProfileOut = {
  photo_url: null,
  designation: null,
  team: null,
  organization: null,
  speciality: null,
  primary_skills: [],
  secondary_skills: [],
  professional_biography: "",
  work_experience_summary: "",
  career_objective: "",
  key_strengths: "",
  responsibilities: "",
  first_name: "",
  middle_name: null,
  last_name: null,
  preferred_name: null,
};

export default async function ProfilePage() {
  let profile = EMPTY_PROFILE;
  try {
    profile = await serverApiFetch<ProfileOut>("profile");
  } catch {
    // backend not reachable yet — form still renders with empty defaults
  }

  return (
    <div className="max-w-4xl">
      <ProfileForm profile={profile} />
    </div>
  );
}
