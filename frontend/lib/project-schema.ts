import { z } from "zod";
import { countPlain } from "@/lib/rich-text/count";

const richText = (limit: number, label: string) =>
  z.object({ html: z.string(), text: z.string() }).refine((v) => countPlain(v.text) <= limit, {
    message: `${label} must be ${limit.toLocaleString()} characters or fewer`,
    path: ["text"],
  });

const requiredRichText = (limit: number, label: string, requiredMessage: string) =>
  richText(limit, label).refine((v) => v.text.trim().length > 0, { message: requiredMessage, path: ["text"] });

const EMPTY = { html: "", text: "" };

// No `.default()` on the rich-text fields deliberately — a Zod default makes a field
// optional in z.input but required in z.output, and zodResolver's generic ends up
// fighting useForm<ProjectFormValues>() over which of the two it means. We always
// supply a full shape via `emptyProjectFormValues`/mapped `project` defaults instead, so
// nothing here needs to be optional.
export const projectFormSchema = z
  .object({
    name: z.string().trim().min(1, "Project name is required").max(200),
    role: z.string().trim().min(1, "Your role is required").max(120),
    start_date: z.string().min(1, "Pick a start date"),
    end_date: z.string().optional(),
    is_current: z.boolean(),
    description: z.object({
      long: richText(10_000, "Long form"),
      short: requiredRichText(390, "Short summary", "Short summary is required"),
    }),
    responsibilities: z.object({
      long: richText(10_000, "Long form"),
      short: richText(390, "Short summary"),
    }),
    technologies: z.string(),
    project_url: z.string().optional(),
  })
  .superRefine((v, ctx) => {
    if (v.is_current) return;
    if (!v.end_date) {
      ctx.addIssue({ code: "custom", path: ["end_date"], message: "End date is required" });
      return;
    }
    if (v.end_date < v.start_date) {
      ctx.addIssue({ code: "custom", path: ["end_date"], message: "End date must be on or after the start date" });
    }
  });

export type ProjectFormValues = z.infer<typeof projectFormSchema>;

export const emptyProjectFormValues: ProjectFormValues = {
  name: "",
  role: "",
  start_date: "",
  end_date: "",
  is_current: false,
  description: { long: EMPTY, short: EMPTY },
  responsibilities: { long: EMPTY, short: EMPTY },
  technologies: "",
  project_url: "",
};
