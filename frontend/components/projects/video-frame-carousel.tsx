"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useRef, useState, type TouchEvent } from "react";
import { mediaUrl } from "@/lib/media-url";
import { cn } from "@/lib/utils";
import type { ProjectMediaRef } from "@/lib/types";

const SWIPE_THRESHOLD_PX = 40;

/** Read-only detail-page carousel over a project's extracted video-frame stills
 * (backend/app/services/video_frame_service.py) — not an upload UI; the edit page's
 * project-video-field.tsx still owns the single video upload/replace flow, and this is
 * purely a display of what that upload produced in the background. Returns null when
 * there are no frames (no video uploaded, or extraction hasn't finished yet) — the
 * project page renders nothing in that case, same convention as the FAQ card. */
export function VideoFrameCarousel({ frames }: { frames: ProjectMediaRef[] }) {
  const [index, setIndex] = useState(0);
  const touchStartX = useRef<number | null>(null);

  if (frames.length === 0) return null;

  const goTo = (i: number) => setIndex(((i % frames.length) + frames.length) % frames.length);
  const prev = () => goTo(index - 1);
  const next = () => goTo(index + 1);

  const onTouchStart = (e: TouchEvent<HTMLDivElement>) => {
    touchStartX.current = e.touches[0]?.clientX ?? null;
  };
  const onTouchEnd = (e: TouchEvent<HTMLDivElement>) => {
    if (touchStartX.current === null) return;
    const dx = (e.changedTouches[0]?.clientX ?? touchStartX.current) - touchStartX.current;
    touchStartX.current = null;
    if (Math.abs(dx) < SWIPE_THRESHOLD_PX) return;
    if (dx > 0) prev();
    else next();
  };

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-surface-2">
      <div
        className="h-full w-full"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- served from our own authenticated API, not a static asset */}
        <img
          src={mediaUrl(frames[index].url)}
          alt=""
          className="h-full w-full object-cover"
        />
      </div>

      {frames.length > 1 && (
        <>
          <button
            type="button"
            onClick={prev}
            aria-label="Previous frame"
            className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-1.5 text-white hover:bg-black/70"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            onClick={next}
            aria-label="Next frame"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-1.5 text-white hover:bg-black/70"
          >
            <ChevronRight size={16} />
          </button>

          <div className="absolute bottom-2 left-1/2 flex -translate-x-1/2 gap-1.5">
            {frames.map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => goTo(i)}
                aria-label={`Go to frame ${i + 1}`}
                aria-current={i === index}
                className={cn(
                  "h-1.5 w-1.5 rounded-full transition-colors",
                  i === index ? "bg-white" : "bg-white/40 hover:bg-white/70",
                )}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
