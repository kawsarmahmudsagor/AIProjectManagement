import { z } from "zod";

// Comma-separated string in the form (same convention as project-schema.ts's
// `technologies` field), split into an array on submit — see profile-form.tsx.
export const profileFormSchema = z.object({
  first_name: z.string().trim().min(1, "First name is required").max(80),
  middle_name: z.string().trim().max(80).optional(),
  last_name: z.string().trim().max(80).optional(),
  preferred_name: z.string().trim().max(80).optional(),

  designation: z.string().trim().max(150).optional(),
  team: z.string().trim().max(150).optional(),
  organization: z.string().trim().max(150).optional(),
  speciality: z.string().trim().max(150).optional(),
  primary_skills: z.string().optional(),
  secondary_skills: z.string().optional(),

  professional_biography: z.string().max(550, "Must be 550 characters or fewer").optional(),
  work_experience_summary: z.string().max(390, "Must be 390 characters or fewer").optional(),
  career_objective: z.string().max(390, "Must be 390 characters or fewer").optional(),
  key_strengths: z.string().max(390, "Must be 390 characters or fewer").optional(),
  responsibilities: z.string().max(390, "Must be 390 characters or fewer").optional(),
});

export type ProfileFormValues = z.infer<typeof profileFormSchema>;
