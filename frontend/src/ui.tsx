import * as Dialog from "@radix-ui/react-dialog";
import { Box, X, Orbit } from "lucide-react";
import type { ReactNode } from "react";
export function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon">
        <Box size={24} strokeWidth={1.7} />
      </span>
      OMNIS<span className="brand-x">-X</span>
    </div>
  );
}
export function Modal({
  title,
  description,
  close,
  children,
}: {
  title: string;
  description?: string;
  close: () => void;
  children: ReactNode;
}) {
  return (
    <Dialog.Root
      open
      onOpenChange={(o) => {
        if (!o) close();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content
          className="modal"
          aria-describedby={description ? "dialog-desc" : undefined}
        >
          <button
            className="icon close"
            onClick={close}
            aria-label="Close dialog"
          >
            <X size={18} />
          </button>
          <Dialog.Title>{title}</Dialog.Title>
          {description && (
            <Dialog.Description id="dialog-desc">
              {description}
            </Dialog.Description>
          )}
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Pill({
  children,
  tone = "teal",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return (
    <span className={"pill " + tone}>
      <i />
      {children}
    </span>
  );
}
export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <Orbit size={22} />
      <p>{children}</p>
    </div>
  );
}
export function CampusArt() {
  // Isometric campus model. Each floor is projected from the same world coordinates.
  const project = (x: number, y: number, z: number) =>
    [264 + (x - y) * 1.04, 178 + (x + y) * 0.51 - z].join(",");
  const face = (pts: number[][]) =>
    pts.map((p) => project(p[0], p[1], p[2])).join(" ");
  const blocks = [
    [-94, -55, 55, 41, 46],
    [-28, -99, 51, 40, 74],
    [47, -72, 38, 38, 40],
    [-70, 31, 54, 35, 29],
    [10, -12, 67, 42, 52],
    [62, 47, 35, 27, 26],
  ].sort((a, b) => a[0] + a[1] - b[0] - b[1]);
  return (
    <svg
      className="campus-art"
      viewBox="30 0 470 325"
      role="img"
      aria-label="Isometric digital twin of six connected campus buildings"
    >
      <defs>
        <pattern id="dots" width="12" height="12" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r=".8" fill="#8fcbc4" opacity=".3" />
        </pattern>
        <radialGradient id="halo">
          <stop stopColor="#2d8d79" stopOpacity=".28" />
          <stop offset="1" stopColor="#0c2828" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="540" height="330" fill="url(#dots)" />
      <ellipse cx="260" cy="168" rx="222" ry="145" fill="url(#halo)" />
      {[
        -140, -120, -100, -80, -60, -40, -20, 0, 20, 40, 60, 80, 100, 120, 140,
      ].map((t) => (
        <g key={t} stroke="#42726e" opacity=".46" strokeWidth=".65">
          <polyline
            fill="none"
            points={face([
              [t, -130, 0],
              [t, 130, 0],
            ])}
          />
          <polyline
            fill="none"
            points={face([
              [-140, t, 0],
              [140, t, 0],
            ])}
          />
        </g>
      ))}
      <g fill="none" stroke="#58d9bd" strokeWidth="2" opacity=".85">
        {[
          [
            [-70, -34, 1],
            [-70, 3, 1],
            [38, 3, 1],
            [38, 63, 1],
            [81, 63, 1],
          ],
          [
            [0, -76, 1],
            [0, -38, 1],
            [68, -38, 1],
          ],
          [
            [-43, 50, 1],
            [-43, 3, 1],
          ],
        ].map((p, i) => (
          <polyline key={i} points={face(p)} />
        ))}
      </g>
      {blocks.map(([x, y, w, d, h], idx) => (
        <g key={idx} stroke="#91d2c3" strokeWidth="1" strokeLinejoin="round">
          <polygon
            fill="#1a443f"
            points={face([
              [x, y + d, 0],
              [x + w, y + d, 0],
              [x + w, y + d, h],
              [x, y + d, h],
            ])}
          />
          <polygon
            fill="#102e30"
            points={face([
              [x + w, y, 0],
              [x + w, y + d, 0],
              [x + w, y + d, h],
              [x + w, y, h],
            ])}
          />
          <polygon
            fill="#37665c"
            points={face([
              [x, y, h],
              [x + w, y, h],
              [x + w, y + d, h],
              [x, y + d, h],
            ])}
          />
          <polygon
            fill="#244f48"
            points={face([
              [x + 5, y + 5, h + 1],
              [x + w - 5, y + 5, h + 1],
              [x + w - 5, y + d - 5, h + 1],
              [x + 5, y + d - 5, h + 1],
            ])}
          />
          {Array.from({ length: Math.floor(h / 10) - 1 }, (_, j) => (
            <g key={j} strokeWidth="2.5" strokeDasharray="3 3" stroke="#77bcae">
              <polyline
                points={face([
                  [x + 3, y + d, j * 10 + 8],
                  [x + w - 3, y + d, j * 10 + 8],
                ])}
              />
              <polyline
                opacity=".65"
                points={face([
                  [x + w, y + 3, j * 10 + 8],
                  [x + w, y + d - 3, j * 10 + 8],
                ])}
              />
            </g>
          ))}
        </g>
      ))}
      <g
        fontFamily="monospace"
        fontSize="9"
        letterSpacing="1"
        fill="#c3e6de"
        strokeWidth=".8"
      >
        <path d="M275 69 L310 40 H381" fill="none" stroke="#83bfb0" />
        <circle cx="275" cy="69" r="3" fill="#8bf6c9" />
        <text x="319" y="35">
          NORTH HALL
        </text>
        <path d="M199 185 L150 220 H75" fill="none" stroke="#83bfb0" />
        <text x="76" y="215">
          WEST HALL
        </text>
        <circle cx="199" cy="185" r="3" fill="#8bf6c9" />
      </g>
    </svg>
  );
}
