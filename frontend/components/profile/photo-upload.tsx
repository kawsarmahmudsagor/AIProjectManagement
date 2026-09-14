"use client";

import { Trash2, Upload, UserRound } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api-client";
import { mediaUrl } from "@/lib/media-url";
import { deleteProfilePhoto, uploadProfilePhoto } from "@/lib/profile";

/** Upload/remove happen immediately (not part of the form's batched Save Changes) —
 * matches the reference mockup, where the photo buttons sit apart from the rest of the
 * form fields.
 *
 * `initialUrl`/`result.photo_url` are bare backend paths (e.g. "profile/photo"), not
 * full URLs — resolved through mediaUrl() at render time, same convention as every new
 * media surface (see lib/media-url.ts's docstring for the bug this fixes). */
export function PhotoUpload({ initialUrl }: { initialUrl: string | null }) {
  const [path, setPath] = useState(initialUrl);
  const [cacheBust, setCacheBust] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const url = path ? `${mediaUrl(path)}${cacheBust ? `?t=${cacheBust}` : ""}` : null;

  const onFileChange = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await uploadProfilePhoto(file);
      setPath(result.photo_url);
      setCacheBust(Date.now());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not upload photo");
    } finally {
      setBusy(false);
    }
  };

  const onRemove = async () => {
    setBusy(true);
    setError(null);
    try {
      await deleteProfilePhoto();
      setPath(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove photo");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex aspect-square w-full max-w-[220px] items-center justify-center overflow-hidden rounded-lg border border-border bg-surface-2">
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element -- user-uploaded, served from our own API
          <img src={url} alt="Profile photo" className="h-full w-full object-cover" />
        ) : (
          <UserRound size={48} className="text-muted" />
        )}
      </div>
      <div className="flex gap-2">
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => void onFileChange(e.target.files?.[0])}
        />
        <Button type="button" variant="secondary" disabled={busy} onClick={() => inputRef.current?.click()}>
          <Upload size={14} /> Upload Image
        </Button>
        {url && (
          <Button type="button" variant="danger" disabled={busy} onClick={() => void onRemove()}>
            <Trash2 size={14} /> Remove
          </Button>
        )}
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
