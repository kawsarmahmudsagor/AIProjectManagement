"use client";

import { ImageIcon, Video } from "lucide-react";
import { useState, type PointerEvent } from "react";
import { useMediaQuery } from "@/hooks/use-media-query";
import { mediaUrl } from "@/lib/media-url";
import { cn } from "@/lib/utils";

/** The card's media area: a thumbnail image that plays the project's video on hover, if
 * one exists. The <video> element is only ever MOUNTED while actually hovering — not
 * just deferred with `preload="none"` — since a mounted-but-unloaded <video> still
 * costs a decoder instance per card; mounting on demand means zero bytes fetched for
 * every card that isn't currently hovered. */
export function ProjectCardMedia({
  thumbnailUrl,
  videoUrl,
  alt,
}: {
  thumbnailUrl: string | null;
  videoUrl: string | null;
  alt: string;
}) {
  const [hovering, setHovering] = useState(false);
  const [videoReady, setVideoReady] = useState(false);
  const canHover = useMediaQuery("(hover: hover) and (pointer: fine)");
  const prefersReducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const playable = Boolean(videoUrl) && canHover && !prefersReducedMotion;

  const onPointerEnter = (e: PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== "mouse") return; // touch devices: no hover-to-play at all
    setHovering(true);
  };
  const onPointerLeave = () => {
    setHovering(false);
    setVideoReady(false);
  };

  return (
    <div
      className="relative aspect-video w-full overflow-hidden bg-surface-2"
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
    >
      {thumbnailUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- served from our own authenticated API, not a static asset
        <img src={mediaUrl(thumbnailUrl)} alt={alt} className="h-full w-full object-cover" />
      ) : (
        <div className="flex h-full w-full items-center justify-center">
          <ImageIcon size={28} className="text-muted" />
        </div>
      )}

      {hovering && playable && videoUrl && (
        <video
          key={videoUrl}
          src={mediaUrl(videoUrl)}
          autoPlay
          muted
          loop
          playsInline
          preload="none"
          onCanPlay={() => setVideoReady(true)}
          className={cn(
            "pointer-events-none absolute inset-0 h-full w-full object-cover opacity-0 transition-opacity duration-200",
            videoReady && "opacity-100",
          )}
        />
      )}

      {videoUrl && (
        <div
          aria-hidden="true"
          className="absolute left-3 top-3 rounded-full bg-black/60 p-1.5 text-white"
        >
          <Video size={12} />
        </div>
      )}
    </div>
  );
}
