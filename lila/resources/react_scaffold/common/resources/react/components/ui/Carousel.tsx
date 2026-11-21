import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "./cn";

export interface Slide {
  title?: ReactNode;
  description?: ReactNode;
  content?: ReactNode;
  image?: string;
}

/** Scroll-snap carousel (swipe, arrows, dots, keyboard, pauses on hover) like {{ carousel() }} in Jinja. */
export function Carousel({ slides, autoplay = 0, loop = true, arrows = true, indicators = true, itemClassName = "basis-full", label = "Carousel", className }: {
  slides: Slide[]; autoplay?: number; loop?: boolean; arrows?: boolean; indicators?: boolean; itemClassName?: string; label?: string; className?: string;
}) {
  const track = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  const go = useCallback((target: number) => {
    const el = track.current;
    if (!el || !slides.length) return;
    const count = slides.length;
    const next = loop ? (target + count) % count : Math.max(0, Math.min(target, count - 1));
    const item = el.children[next] as HTMLElement | undefined;
    if (item) el.scrollTo({ left: item.offsetLeft - el.offsetLeft, behavior: "smooth" });
    setIndex(next);
  }, [slides.length, loop]);

  useEffect(() => {
    if (!autoplay || paused || slides.length < 2) return undefined;
    const id = window.setInterval(() => go(index + 1), autoplay);
    return () => window.clearInterval(id);
  }, [autoplay, paused, index, go, slides.length]);

  const onScroll = () => {
    const el = track.current;
    if (!el) return;
    const width = el.clientWidth || 1;
    setIndex(Math.round(el.scrollLeft / width));
  };

  return (
    <div
      className={cn("relative", className)}
      role="region"
      aria-roledescription="carousel"
      aria-label={label}
      tabIndex={0}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") go(index + 1);
        if (e.key === "ArrowLeft") go(index - 1);
      }}
    >
      <div ref={track} className="carousel-track gap-4" onScroll={onScroll}>
        {slides.map((slide, i) => (
          <div key={i} className={cn("carousel-item", itemClassName)} aria-roledescription="slide" aria-label={`${i + 1} / ${slides.length}`}>
            {slide.content ?? (
              <div className="card overflow-hidden">
                {slide.image && <img src={slide.image} alt="" className="h-56 w-full object-cover" />}
                <div className="p-6">
                  {slide.title && <h3 className="card-title">{slide.title}</h3>}
                  {slide.description && <p className="card-description">{slide.description}</p>}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      {arrows && slides.length > 1 && (
        <>
          <button type="button" onClick={() => go(index - 1)} className="btn-light btn-icon btn-sm absolute left-2 top-1/2 -translate-y-1/2 rounded-full" aria-label="Previous">‹</button>
          <button type="button" onClick={() => go(index + 1)} className="btn-light btn-icon btn-sm absolute right-2 top-1/2 -translate-y-1/2 rounded-full" aria-label="Next">›</button>
        </>
      )}
      {indicators && slides.length > 1 && (
        <div className="mt-3 flex justify-center gap-2">
          {slides.map((_, i) => (
            <button key={i} type="button" onClick={() => go(i)} aria-label={`Slide ${i + 1}`} aria-current={i === index || undefined}
              className={cn("h-2 rounded-full transition-all", i === index ? "w-6 bg-primary" : "w-2 bg-muted-foreground/40")} />
          ))}
        </div>
      )}
    </div>
  );
}
