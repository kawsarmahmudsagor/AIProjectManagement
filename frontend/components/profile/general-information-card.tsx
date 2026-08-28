"use client";

import type { UseFormRegister } from "react-hook-form";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PhotoUpload } from "@/components/profile/photo-upload";
import type { ProfileFormValues } from "@/lib/profile-schema";

export function GeneralInformationCard({
  register,
  photoUrl,
}: {
  register: UseFormRegister<ProfileFormValues>;
  photoUrl: string | null;
}) {
  return (
    <Card className="grid gap-6 md:grid-cols-[220px_1fr]">
      <PhotoUpload initialUrl={photoUrl} />

      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium">First Name</label>
            <Input placeholder="Your first name" {...register("first_name")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Middle Name</label>
            <Input placeholder="Optional" {...register("middle_name")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Last Name</label>
            <Input placeholder="Optional" {...register("last_name")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Preferred Name</label>
            <Input placeholder="What Jarvis should call you" {...register("preferred_name")} />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium">Designation</label>
            <Input placeholder="e.g. Software Engineer I" {...register("designation")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Speciality</label>
            <Input placeholder="e.g. RAG systems" {...register("speciality")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Team</label>
            <Input placeholder="Optional" {...register("team")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Organization</label>
            <Input placeholder="Optional" {...register("organization")} />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium">Primary Skills</label>
            <Input placeholder="e.g. Python (comma-separated)" {...register("primary_skills")} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Secondary Skills</label>
            <Input placeholder="e.g. AI Enabled (comma-separated)" {...register("secondary_skills")} />
          </div>
        </div>
      </div>
    </Card>
  );
}
