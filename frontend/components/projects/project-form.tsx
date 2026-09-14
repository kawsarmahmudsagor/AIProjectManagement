"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { FileInput } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { DualEditorField } from "@/components/projects/fields/dual-editor-field";
import { ProjectThumbnailField } from "@/components/projects/fields/project-thumbnail-field";
import { ProjectVideoField } from "@/components/projects/fields/project-video-field";
import { ProjectInputDialog } from "@/components/projects/upload/project-input-dialog";
import { PROJECTS_NAV_QUERY_KEY } from "@/components/layout/projects-nav-section";
import { apiFetch, ApiError } from "@/lib/api-client";
import { emptyProjectFormValues, projectFormSchema, type ProjectFormValues } from "@/lib/project-schema";
import type { RichText } from "@/lib/rich-text/types";
import type { ExtractionResult, Project, ThumbnailGenerationContext } from "@/lib/types";

type SectionAutofill = { token: number; long?: RichText; short?: RichText };
const NO_AUTOFILL: SectionAutofill = { token: 0 };

// Mirrors backend/app/services/thumbnail_service.has_sufficient_context exactly (same
// 80-char / 2-technology thresholds) so the Generate button's enabled state never
// disagrees with what the server will actually accept.
const MIN_CONTEXT_CHARS = 80;

export function ProjectForm({ project }: { project?: Project }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [inputDialogOpen, setInputDialogOpen] = useState(false);

  // Holds the project's id once it exists — either passed in (edit mode) or created by
  // an auto-save triggered from the thumbnail field (create mode, per the product
  // decision to save first rather than send unsaved-form context inline). Switching the
  // form to PATCH-mode in place this way avoids remounting at the edit URL mid-flow,
  // which would collide with the thumbnail/video fields' own in-progress state.
  const [savedProjectId, setSavedProjectId] = useState<string | null>(project?.id ?? null);
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(project?.thumbnail?.url ?? null);
  const [videoUrl, setVideoUrl] = useState<string | null>(project?.video?.url ?? null);

  const [descriptionAutofill, setDescriptionAutofill] = useState<SectionAutofill>(NO_AUTOFILL);
  const [responsibilitiesAutofill, setResponsibilitiesAutofill] = useState<SectionAutofill>(NO_AUTOFILL);
  const autofillTokenRef = useRef(0);

  const {
    register,
    handleSubmit,
    watch,
    control,
    getValues,
    setValue,
    trigger,
    formState: { errors, isSubmitting, dirtyFields },
  } = useForm<ProjectFormValues>({
    resolver: zodResolver(projectFormSchema),
    defaultValues: project
      ? {
          name: project.name,
          role: project.role,
          start_date: project.start_date,
          end_date: project.end_date ?? "",
          is_current: project.is_current,
          description: project.description,
          responsibilities: project.responsibilities,
          technologies: project.technologies.join(", "),
          project_url: project.project_url ?? "",
        }
      : emptyProjectFormValues,
  });

  const isCurrent = watch("is_current");

  const buildAiContext = () => {
    const values = getValues();
    return {
      project_name: values.name || undefined,
      role: values.role || undefined,
      technologies: values.technologies
        ? values.technologies.split(",").map((t) => t.trim()).filter(Boolean)
        : undefined,
    };
  };

  const buildThumbnailContext = (): ThumbnailGenerationContext => {
    const values = getValues();
    return {
      name: values.name || undefined,
      role: values.role || undefined,
      technologies: values.technologies
        ? values.technologies.split(",").map((t) => t.trim()).filter(Boolean)
        : undefined,
      description_text: values.description.long.text || values.description.short.text || undefined,
      responsibilities_text: values.responsibilities.long.text || values.responsibilities.short.text || undefined,
    };
  };

  // Reactive, so the Generate button's disabled state updates live as the user types —
  // same idiom as DualEditorField's own reactive empty-checks via useWatch.
  const [watchedDescLong, watchedDescShort, watchedRespLong, watchedRespShort, watchedTech] = useWatch({
    control,
    name: [
      "description.long.text",
      "description.short.text",
      "responsibilities.long.text",
      "responsibilities.short.text",
      "technologies",
    ],
  });
  const contextCharCount = [watchedDescLong, watchedDescShort, watchedRespLong, watchedRespShort]
    .filter(Boolean)
    .join(" ").length;
  const contextTechCount = watchedTech ? watchedTech.split(",").map((t) => t.trim()).filter(Boolean).length : 0;
  const hasThumbnailContext = contextCharCount >= MIN_CONTEXT_CHARS || contextTechCount >= 2;

  // Extraction never overwrites a field the user has already touched or already
  // filled — same "AI never overwrites hand-written prose silently" rule as the
  // per-field Enhance buttons (frontend/DESIGN.md §4.4), just applied to a whole-form
  // autofill instead of one box at a time. A field the document didn't mention comes
  // back null/empty from the backend (never hallucinated) and is simply skipped here,
  // leaving it for the human to fill in.
  const handleExtracted = (result: ExtractionResult) => {
    const p = result.project;
    const current = getValues();

    const fillText = (
      name: "name" | "role" | "start_date" | "end_date" | "technologies",
      value: string | undefined,
      isDirty: unknown,
    ) => {
      if (!value || isDirty || (current[name] ?? "").trim()) return;
      setValue(name, value, { shouldDirty: true, shouldValidate: true });
    };

    fillText("name", p.name ?? undefined, dirtyFields.name);
    fillText("role", p.role ?? undefined, dirtyFields.role);
    fillText("start_date", p.start_date ?? undefined, dirtyFields.start_date);
    fillText("end_date", p.end_date ?? undefined, dirtyFields.end_date);
    fillText("technologies", p.technologies.length > 0 ? p.technologies.join(", ") : undefined, dirtyFields.technologies);

    const sectionAutofill = (
      section: "description" | "responsibilities",
      long: RichText,
      short: RichText,
    ): SectionAutofill => ({
      token: ++autofillTokenRef.current,
      long: !dirtyFields[section]?.long && !current[section].long.text.trim() && long.text.trim() ? long : undefined,
      short: !dirtyFields[section]?.short && !current[section].short.text.trim() && short.text.trim() ? short : undefined,
    });

    setDescriptionAutofill(sectionAutofill("description", p.description.long, p.description.short));
    setResponsibilitiesAutofill(sectionAutofill("responsibilities", p.responsibilities.long, p.responsibilities.short));
  };

  const buildPayload = (values: ProjectFormValues) => ({
    name: values.name,
    role: values.role,
    start_date: values.start_date,
    end_date: values.is_current ? null : values.end_date || null,
    is_current: values.is_current,
    description: values.description,
    responsibilities: values.responsibilities,
    technologies: values.technologies
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean),
    project_url: values.project_url || null,
  });

  /** Shared by the form's own submit AND the thumbnail/video fields' auto-save-first
   * flow — PATCHes once `savedProjectId` exists (whether from the original edit-mode
   * prop or from an earlier auto-save this session), POSTs otherwise. */
  const saveProject = async (values: ProjectFormValues): Promise<Project> => {
    const payload = buildPayload(values);
    return savedProjectId
      ? apiFetch<Project>(`projects/${savedProjectId}`, { method: "PATCH", body: JSON.stringify(payload) })
      : apiFetch<Project>("projects", { method: "POST", body: JSON.stringify(payload) });
  };

  /** Passed to ProjectThumbnailField/ProjectVideoField as `ensureSaved`. Already-saved
   * projects return immediately with no network call; an unsaved (create-mode) project
   * is validated (react-hook-form's trigger(), the same zod schema the real submit
   * uses) and saved before generating/uploading — per the product decision to auto-save
   * rather than send unsaved-form context inline. Returns null (and surfaces the
   * validation/save error inline) if either step fails, so the caller knows not to
   * proceed. */
  const ensureSaved = async (): Promise<string | null> => {
    if (savedProjectId) return savedProjectId;

    const valid = await trigger();
    if (!valid) {
      setServerError("Fill in the required project fields first, then try again.");
      return null;
    }

    try {
      const saved = await saveProject(getValues());
      setSavedProjectId(saved.id);
      queryClient.invalidateQueries({ queryKey: PROJECTS_NAV_QUERY_KEY });
      return saved.id;
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Could not save the project");
      return null;
    }
  };

  const onSubmit = async (values: ProjectFormValues) => {
    setServerError(null);
    try {
      const saved = await saveProject(values);
      queryClient.invalidateQueries({ queryKey: PROJECTS_NAV_QUERY_KEY });
      router.replace(`/projects/${saved.id}`);
      router.refresh();
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Could not save the project");
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <Card className="space-y-4">
        <div className="flex flex-col gap-6 @2xl:flex-row">
          <ProjectThumbnailField
            projectId={savedProjectId}
            thumbnailUrl={thumbnailUrl}
            onThumbnailChange={setThumbnailUrl}
            hasContext={hasThumbnailContext}
            buildContext={buildThumbnailContext}
            ensureSaved={ensureSaved}
            disabled={isSubmitting}
          />
          <div className="min-w-0 flex-1 space-y-4">
            <div className="flex justify-end">
              <Button type="button" variant="secondary" size="sm" onClick={() => setInputDialogOpen(true)} disabled={isSubmitting}>
                <FileInput size={13} /> Input
              </Button>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Project Name</label>
              <Input placeholder="Enter project name" {...register("name")} />
              {errors.name && <p className="mt-1 text-xs text-danger">{errors.name.message}</p>}
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Your Role</label>
              <Input placeholder="e.g. Lead Developer" {...register("role")} />
              {errors.role && <p className="mt-1 text-xs text-danger">{errors.role.message}</p>}
            </div>
            <div className="grid grid-cols-1 gap-4 @md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium">Start Date</label>
                <Input type="date" {...register("start_date")} />
                {errors.start_date && <p className="mt-1 text-xs text-danger">{errors.start_date.message}</p>}
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">End Date</label>
                <Input type="date" disabled={isCurrent} {...register("end_date")} />
                {errors.end_date && <p className="mt-1 text-xs text-danger">{errors.end_date.message}</p>}
                <label className="mt-2 flex items-center gap-2 text-sm">
                  <input type="checkbox" {...register("is_current")} />
                  Current Project
                </label>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <ProjectInputDialog
        open={inputDialogOpen}
        onClose={() => setInputDialogOpen(false)}
        onExtracted={handleExtracted}
        disabled={isSubmitting}
      />

      <Card>
        <DualEditorField
          section="description"
          title="Project Description"
          helperText="Fill the long form first for full detail, then generate a short summary from it. The short summary is what appears in compact views."
          control={control}
          getValues={getValues}
          setValue={setValue}
          buildContext={buildAiContext}
          autofill={descriptionAutofill}
          long={{
            name: "description.long",
            label: "Long form",
            badge: "Optional · up to 10,000 chars",
            limit: 10_000,
            placeholder:
              "Write the full, detailed project description here — context, scope, technical approach, outcomes...",
            tooltip: "Not shown in compact views directly. Used as the source for the short summary.",
            enhanceLabel: "Enhance long with AI",
          }}
          short={{
            name: "description.short",
            label: "Short summary",
            badge: "Required",
            requirement: "required",
            limit: 390,
            placeholder: "Concise summary used in compact views",
            tooltip: "Appears in compact views. Keep it under 390 characters.",
            generateLabel: "Generate from long",
            enhanceLabel: "Enhance",
            errorMessage: errors.description?.short?.text?.message,
          }}
        />
      </Card>

      <Card>
        <DualEditorField
          section="responsibilities"
          title="Your Responsibilities"
          helperText="Document your detailed contributions in the long form, then generate a short summary for display."
          control={control}
          getValues={getValues}
          setValue={setValue}
          buildContext={buildAiContext}
          autofill={responsibilitiesAutofill}
          long={{
            name: "responsibilities.long",
            label: "Long form",
            badge: "Optional · up to 10,000 chars",
            limit: 10_000,
            placeholder:
              "Write the full, detailed responsibilities here — contributions, leadership, collaboration, outcomes...",
            tooltip: "Not shown in compact views directly. Used as the source for the short summary.",
            enhanceLabel: "Enhance long with AI",
          }}
          short={{
            name: "responsibilities.short",
            label: "Short summary",
            badge: "Recommended",
            requirement: "recommended",
            limit: 390,
            placeholder: "Concise summary of your responsibilities used in compact views",
            tooltip: "Appears in compact views. Keep it under 390 characters.",
            generateLabel: "Generate from long",
            enhanceLabel: "Enhance",
            errorMessage: errors.responsibilities?.short?.text?.message,
          }}
        />
      </Card>

      <Card className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium">Technologies Used</label>
          <Input placeholder="e.g. React, FastAPI, PostgreSQL (comma-separated)" {...register("technologies")} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Project URL (Optional)</label>
          <Input placeholder="https://..." {...register("project_url")} />
        </div>
        <ProjectVideoField
          projectId={savedProjectId}
          videoUrl={videoUrl}
          onVideoChange={setVideoUrl}
          ensureSaved={ensureSaved}
          disabled={isSubmitting}
        />
      </Card>

      {serverError && <p className="text-sm text-danger">{serverError}</p>}

      <div className="flex justify-end gap-3">
        <Button type="button" variant="secondary" onClick={() => router.back()}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting} className="min-w-[140px]">
          {isSubmitting ? "Saving…" : "Save Project"}
        </Button>
      </div>
    </form>
  );
}
