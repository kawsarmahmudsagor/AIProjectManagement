"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { GeneralInformationCard } from "@/components/profile/general-information-card";
import { PlainTextEnhanceField } from "@/components/profile/plain-text-enhance-field";
import { ApiError } from "@/lib/api-client";
import { profileFormSchema, type ProfileFormValues } from "@/lib/profile-schema";
import { updateProfile, type ProfileOut } from "@/lib/profile";

function toFormValues(profile: ProfileOut): ProfileFormValues {
  return {
    first_name: profile.first_name,
    middle_name: profile.middle_name ?? "",
    last_name: profile.last_name ?? "",
    preferred_name: profile.preferred_name ?? "",
    designation: profile.designation ?? "",
    team: profile.team ?? "",
    organization: profile.organization ?? "",
    speciality: profile.speciality ?? "",
    primary_skills: profile.primary_skills.join(", "),
    secondary_skills: profile.secondary_skills.join(", "),
    professional_biography: profile.professional_biography,
    work_experience_summary: profile.work_experience_summary,
    career_objective: profile.career_objective,
    key_strengths: profile.key_strengths,
    responsibilities: profile.responsibilities,
  };
}

const splitList = (v?: string) => (v ? v.split(",").map((s) => s.trim()).filter(Boolean) : []);

export function ProfileForm({ profile }: { profile: ProfileOut }) {
  const [serverError, setServerError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    formState: { isSubmitting, isDirty },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    defaultValues: toFormValues(profile),
  });

  const onSubmit = async (values: ProfileFormValues) => {
    setServerError(null);
    setSaved(false);
    try {
      await updateProfile({
        first_name: values.first_name,
        middle_name: values.middle_name || null,
        last_name: values.last_name || null,
        preferred_name: values.preferred_name || null,
        designation: values.designation || null,
        team: values.team || null,
        organization: values.organization || null,
        speciality: values.speciality || null,
        primary_skills: splitList(values.primary_skills),
        secondary_skills: splitList(values.secondary_skills),
        professional_biography: values.professional_biography ?? "",
        work_experience_summary: values.work_experience_summary ?? "",
        career_objective: values.career_objective ?? "",
        key_strengths: values.key_strengths ?? "",
        responsibilities: values.responsibilities ?? "",
      });
      setSaved(true);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Could not save your profile");
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">General Information</h1>
        <Button type="submit" disabled={!isDirty || isSubmitting} className="min-w-[140px]">
          {isSubmitting ? "Saving…" : "Save Changes"}
        </Button>
      </div>

      <GeneralInformationCard register={register} photoUrl={profile.photo_url} />

      <Card className="space-y-4">
        <PlainTextEnhanceField
          name="professional_biography"
          label="Professional Biography"
          limit={550}
          placeholder="Summarize who you are professionally…"
          control={control}
        />
        <PlainTextEnhanceField
          name="work_experience_summary"
          label="Work Experience Summary"
          limit={390}
          placeholder="Summarize your overall work experience, domains, and impact…"
          control={control}
        />
        <PlainTextEnhanceField
          name="career_objective"
          label="Career Objective"
          limit={390}
          placeholder="What are your career goals and aspirations?"
          control={control}
        />
        <PlainTextEnhanceField
          name="key_strengths"
          label="Key Strengths"
          limit={390}
          placeholder="List your core strengths and what sets you apart…"
          control={control}
        />
        <PlainTextEnhanceField
          name="responsibilities"
          label="Responsibilities"
          limit={390}
          placeholder="Describe your typical responsibilities and ownership areas…"
          control={control}
        />
      </Card>

      {serverError && <p className="text-sm text-danger">{serverError}</p>}
      {saved && !isDirty && <p className="text-sm text-accent">Saved.</p>}
    </form>
  );
}
