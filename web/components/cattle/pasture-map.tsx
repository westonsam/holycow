"use client";
import { useCallback, useRef, useState } from "react";
import {
  LocateFixed,
  Plus,
  Minus,
  Maximize2,
  Layers,
  ChevronDown,
  MapPin,
  X,
  Check,
  ScanSearch,
} from "lucide-react";
import type {
  Animal,
  Assessment,
  Herd,
  NonCowDetection,
} from "@/lib/cattle/contracts";
import { assessmentLabels, time } from "./status";
import { svgPoints } from "@/lib/cattle/map-layout";
import { Dialog } from "./dialog";

interface Props {
  animals: Animal[];
  nonCowDetections: NonCowDetection[];
  herds: Herd[];
  herdFilter: string;
  setHerdFilter(value: string): void;
  openAnimal(animal: Animal): void;
  expanded?: boolean;
  onExpand(): void;
  initialBoundaries: boolean;
}
export function PastureMap({
  animals,
  nonCowDetections,
  herds,
  herdFilter,
  setHerdFilter,
  openAnimal,
  expanded,
  onExpand,
  initialBoundaries,
}: Props) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [layers, setLayers] = useState(false);
  const [boundaries, setBoundaries] = useState(initialBoundaries);
  const [markers, setMarkers] = useState(true);
  const [filter, setFilter] = useState<Assessment | "non-cow" | "all">("all");
  const [selectedOther, setSelectedOther] = useState<NonCowDetection | null>(
    null,
  );
  const closeOther = useCallback(() => setSelectedOther(null), []);
  const [hovered, setHovered] = useState<string | null>(null);
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(
    null,
  );
  const visible = animals.filter(
    (a) =>
      a.mapPosition &&
      (herdFilter === "all" || a.herdId === herdFilter) &&
      (filter === "all" || a.assessment === filter),
  );
  const focused = animals.find((a) => a.id === hovered);
  const otherVisible = nonCowDetections.filter(
    (detection) =>
      (filter === "all" || filter === "non-cow") &&
      (herdFilter === "all" ||
        herds.find((herd) => herd.id === herdFilter)?.pastureId ===
          detection.pastureId),
  );
  const reset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };
  return (
    <>
      <section
        className={`pasture-map ${expanded ? "expanded-map" : ""}`}
        aria-label="Illustrative pasture map"
      >
        <div
          className="map-viewport"
          tabIndex={0}
          aria-label="Pasture map. Drag to pan; use arrow keys to move and plus or minus to zoom."
          onKeyDown={(e) => {
            if (e.target !== e.currentTarget) return;
            if (
              [
                "ArrowLeft",
                "ArrowRight",
                "ArrowUp",
                "ArrowDown",
                "+",
                "-",
              ].includes(e.key)
            )
              e.preventDefault();
            if (e.key.startsWith("Arrow"))
              setPan((p) => ({
                x: Math.max(
                  -170,
                  Math.min(
                    170,
                    p.x +
                      (e.key === "ArrowLeft"
                        ? 25
                        : e.key === "ArrowRight"
                          ? -25
                          : 0),
                  ),
                ),
                y: Math.max(
                  -170,
                  Math.min(
                    170,
                    p.y +
                      (e.key === "ArrowUp"
                        ? 25
                        : e.key === "ArrowDown"
                          ? -25
                          : 0),
                  ),
                ),
              }));
            if (e.key === "+") setZoom((z) => Math.min(2.2, z + 0.2));
            if (e.key === "-") setZoom((z) => Math.max(1, z - 0.2));
          }}
          onPointerDown={(e) => {
            if ((e.target as Element).closest('button,[role="button"]')) return;
            drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y };
            e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            if (drag.current)
              setPan({
                x: Math.max(
                  -170,
                  Math.min(170, drag.current.px + e.clientX - drag.current.x),
                ),
                y: Math.max(
                  -170,
                  Math.min(170, drag.current.py + e.clientY - drag.current.y),
                ),
              });
          }}
          onPointerUp={() => {
            drag.current = null;
          }}
          onPointerCancel={() => {
            drag.current = null;
          }}
        >
          <div
            className="map-world"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            }}
          >
            <img
              className="ranch-aerial"
              src="/assets/ranch-aerial.png"
              alt="Illustrative aerial pasture terrain, not a real georeferenced ranch"
              draggable={false}
            />
            <div className="map-tint" />
            {boundaries && (
              <svg
                className="pasture-boundaries"
                viewBox="0 0 1000 1000"
                preserveAspectRatio="none"
                aria-label="Demo pasture boundaries"
              >
                <polygon
                  className={herdFilter === "herd-2" ? "muted-boundary" : ""}
                  points={svgPoints("herd-1")}
                  role="button"
                  tabIndex={0}
                  aria-label="Filter map to Herd 1"
                  onClick={() =>
                    setHerdFilter(herdFilter === "herd-1" ? "all" : "herd-1")
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setHerdFilter("herd-1");
                    }
                  }}
                />
                <polygon
                  className={herdFilter === "herd-1" ? "muted-boundary" : ""}
                  points={svgPoints("herd-2")}
                  role="button"
                  tabIndex={0}
                  aria-label="Filter map to Herd 2"
                  onClick={() =>
                    setHerdFilter(herdFilter === "herd-2" ? "all" : "herd-2")
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setHerdFilter("herd-2");
                    }
                  }}
                />
              </svg>
            )}
            {boundaries &&
              herds.map((herd, i) => (
                <button
                  key={herd.id}
                  className={`herd-map-label ${herdFilter !== "all" && herdFilter !== herd.id ? "dimmed" : ""}`}
                  style={{ left: i ? "51%" : "50%", top: i ? "73%" : "28%" }}
                  onClick={() =>
                    setHerdFilter(herdFilter === herd.id ? "all" : herd.id)
                  }
                >
                  {herd.name}
                </button>
              ))}
            {markers &&
              visible.map((animal) => (
                <button
                  key={animal.id}
                  className={`animal-marker marker-${animal.assessment}`}
                  style={{
                    left: `${animal.mapPosition!.x}%`,
                    top: `${animal.mapPosition!.y}%`,
                  }}
                  aria-label={`Cow ${animal.tag}, ${assessmentLabels[animal.assessment]}`}
                  onClick={() => openAnimal(animal)}
                  onMouseEnter={() => setHovered(animal.id)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(animal.id)}
                  onBlur={() => setHovered(null)}
                >
                  {animal.assessment === "priority" ? (
                    <X size={13} strokeWidth={3} />
                  ) : (
                    <span />
                  )}
                </button>
              ))}
            {markers &&
              otherVisible.map((detection) => (
                <button
                  key={detection.id}
                  className="non-cow-marker"
                  style={{
                    left: `${detection.mapPosition.x}%`,
                    top: `${detection.mapPosition.y}%`,
                  }}
                  aria-label={`Non-cow detected ${detection.id}`}
                  onClick={() => setSelectedOther(detection)}
                >
                  <span />
                </button>
              ))}
          </div>
        </div>
        <div className="map-topbar">
          <div className="map-herd-select">
            <MapPin size={14} />
            <select
              aria-label="Map herd filter"
              value={herdFilter}
              onChange={(e) => setHerdFilter(e.target.value)}
            >
              <option value="all">All pastures</option>
              {herds.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
            </select>
            <ChevronDown size={13} />
          </div>
          <button
            className="map-tool expand-map"
            onClick={onExpand}
            aria-label={expanded ? "Return to overview" : "Expand map"}
            title={expanded ? "Return to overview" : "Expand map"}
          >
            <Maximize2 size={17} />
          </button>
        </div>
        <div className="map-legend">
          <div className="legend-heading">
            Last observed <span>●</span>
          </div>
          {(["priority", "review", "clear", "unable"] as Assessment[]).map(
            (status) => (
              <button
                key={status}
                className={
                  filter !== "all" && filter !== status ? "legend-muted" : ""
                }
                aria-pressed={filter === status}
                onClick={() => setFilter(filter === status ? "all" : status)}
              >
                {status === "priority" ? (
                  <X size={13} className="legend-red" />
                ) : (
                  <span className={`legend-dot dot-${status}`} />
                )}
                <span>
                  {status === "priority"
                    ? "Priority review"
                    : assessmentLabels[status]}
                </span>
                {filter === status && <Check size={12} />}
              </button>
            ),
          )}
          <button
            className={
              filter !== "all" && filter !== "non-cow" ? "legend-muted" : ""
            }
            aria-pressed={filter === "non-cow"}
            onClick={() => setFilter(filter === "non-cow" ? "all" : "non-cow")}
          >
            <span className="legend-non-cow" />
            <span>Non-cow detected</span>
            {filter === "non-cow" && <Check size={12} />}
          </button>
          {filter !== "all" && (
            <button className="legend-reset" onClick={() => setFilter("all")}>
              Show all observations
            </button>
          )}
        </div>
        {focused && (
          <div className="map-hovercard">
            <strong>Cow {focused.tag}</strong>
            <span>
              {assessmentLabels[focused.assessment]} ·{" "}
              {time(focused.observedAt)}
            </span>
          </div>
        )}
        <div className="map-bottom-left">
          <span className="map-observation-count">
            {markers ? visible.length : 0} cow observations ·{" "}
            {markers ? otherVisible.length : 0} non-cow
          </span>
          <span className="map-disclaimer">
            Illustrative imagery · not to scale
          </span>
        </div>
        <div className="map-controls">
          {layers && (
            <div className="map-layer-menu">
              <strong>Map layers</strong>
              <label>
                <input
                  type="checkbox"
                  checked={boundaries}
                  onChange={(e) => setBoundaries(e.target.checked)}
                />{" "}
                Pasture boundaries
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={markers}
                  onChange={(e) => setMarkers(e.target.checked)}
                />{" "}
                Animal observations
              </label>
            </div>
          )}
          <button
            className={`map-tool ${layers ? "tool-active" : ""}`}
            onClick={() => setLayers(!layers)}
            aria-label="Map layers"
            aria-expanded={layers}
          >
            <Layers size={17} />
          </button>
          <button
            className="map-tool"
            onClick={reset}
            aria-label="Reset map view"
            title="Reset map view"
          >
            <LocateFixed size={18} />
          </button>
          <div className="zoom-buttons">
            <button
              className="map-tool"
              disabled={zoom >= 2.19}
              onClick={() => setZoom((z) => Math.min(2.2, z + 0.2))}
              aria-label="Zoom in"
            >
              <Plus size={20} />
            </button>
            <button
              className="map-tool"
              disabled={zoom <= 1.01}
              onClick={() => {
                setZoom((z) => Math.max(1, z - 0.2));
                if (zoom <= 1.2) setPan({ x: 0, y: 0 });
              }}
              aria-label="Zoom out"
            >
              <Minus size={20} />
            </button>
          </div>
        </div>
      </section>
      {selectedOther && (
        <Dialog
          title="Non-cow detected"
          subtitle="UNIDENTIFIED OBJECT · DEMO"
          onClose={closeOther}
        >
          <div className="non-cow-detail-icon">
            <ScanSearch size={31} />
          </div>
          <p className="dialog-copy">
            An object was detected without being classified as cattle. It stays
            separate from cow identities, herd totals and health findings.
          </p>
          <div className="detail-facts">
            <div>
              <span>Last observed</span>
              <strong>Today, {time(selectedOther.observedAt)}</strong>
            </div>
            <div>
              <span>Pasture area</span>
              <strong>
                {herds.find((h) => h.pastureId === selectedOther.pastureId)
                  ?.pasture ?? "Unassigned"}
              </strong>
            </div>
            <div>
              <span>Classification</span>
              <strong>Non-cow · species unknown</strong>
            </div>
            <div>
              <span>Source</span>
              <strong>Synthetic demo observation</strong>
            </div>
          </div>
          <button className="primary-button full-width" onClick={closeOther}>
            Return to map
          </button>
        </Dialog>
      )}
    </>
  );
}
