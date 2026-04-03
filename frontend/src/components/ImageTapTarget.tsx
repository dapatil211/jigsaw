import type { MouseEvent } from "react";
import { useMemo, useRef } from "react";

import type { Point } from "../types";

interface ImageTapTargetProps {
  imageUrl: string;
  maxPoints: number;
  onChange: (points: Point[]) => void;
  points: Point[];
  title: string;
  labels?: string[];
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(1, value));
}

export function ImageTapTarget({
  imageUrl,
  maxPoints,
  onChange,
  points,
  title,
  labels,
}: ImageTapTargetProps) {
  const frameRef = useRef<HTMLDivElement | null>(null);

  const orderedPoints = useMemo(() => points.slice(0, maxPoints), [points, maxPoints]);

  const handleTap = (event: MouseEvent<HTMLButtonElement>) => {
    const frame = frameRef.current;
    if (!frame) {
      return;
    }

    const rect = frame.getBoundingClientRect();
    const x = clampPercent((event.clientX - rect.left) / rect.width);
    const y = clampPercent((event.clientY - rect.top) / rect.height);

    const nextPoints =
      maxPoints === 1 ? [{ x, y }] : [...orderedPoints, { x, y }].slice(0, maxPoints);

    onChange(nextPoints);
  };

  const handleUndo = () => {
    onChange(orderedPoints.slice(0, -1));
  };

  return (
    <section className="tap-target">
      <div className="tap-target-header">
        <div>
          <p className="eyebrow">Tap guide</p>
          <h3>{title}</h3>
        </div>
        <button
          className="tertiary-button"
          onClick={handleUndo}
          disabled={!orderedPoints.length}
          type="button"
        >
          Undo
        </button>
      </div>

      <button className="tap-frame" onClick={handleTap} type="button">
        <div className="tap-frame-inner" ref={frameRef}>
          <img alt={title} src={imageUrl} />
          {orderedPoints.map((point, index) => (
            <span
              className="tap-point"
              key={`${point.x}-${point.y}-${index}`}
              style={{ left: `${point.x * 100}%`, top: `${point.y * 100}%` }}
            >
              {labels?.[index] ? labels[index][0] : index + 1}
            </span>
          ))}
        </div>
      </button>

      {orderedPoints.length ? (
        <ul className="point-list inline-points">
          {orderedPoints.map((point, index) => (
            <li key={`${point.x}-${point.y}-${index}`}>
              <strong>{labels?.[index] ?? `Point ${index + 1}`}</strong>
              <span>
                {(point.x * 100).toFixed(1)}%, {(point.y * 100).toFixed(1)}%
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="hint">Tap directly on the image to mark points.</p>
      )}
    </section>
  );
}
