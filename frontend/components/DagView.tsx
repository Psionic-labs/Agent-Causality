"use client";

/* Failure-story DAG. Positions come from the story. Highlight walks causal
 * links only, so a filter gap does not light ancestors across it. */

import { useEffect, useRef } from "react";
import {
  clickSuppressed,
  fitZoomMax,
  letterboxFit,
  panBy,
  resetView,
  zoomAt,
  type View,
} from "../lib/viewport.ts";
import { nodeClassNames } from "../lib/render.ts";
import { selectEvent } from "../lib/use-selection.ts";
import { causalAsEdge, storyHighlight, type FailureStory } from "../lib/failureColumn.ts";
import { Legend } from "./Legend.tsx";

export interface ViewApi {
  reset: () => void;
}

interface Props {
  story: FailureStory;
  selectedId: string | null;
  apiRef: React.MutableRefObject<ViewApi | null>;
}

interface Mark {
  x: number;
  y: number;
}

function edgeCurve(a: Mark, b: Mark): string {
  const mx = (a.x + b.x) / 2;
  return `M ${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`;
}

function causalCurve(a: Mark, b: Mark): string {
  // The 18px marker square covers a tip that lands on the node center.
  const endX = b.x + (a.x <= b.x ? -12 : 12);
  const mx = (a.x + endX) / 2;
  return `M ${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${endX} ${b.y}`;
}

export function DagView({ story, selectedId, apiRef }: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const gRef = useRef<SVGGElement | null>(null);
  const viewRef = useRef<View>({ k: 1, tx: 0, ty: 0 });
  const suppressRef = useRef(false);
  const boxRef = useRef({ w: story.bounds.w, h: story.bounds.h });
  const layoutKey = `${story.bounds.w}x${story.bounds.h}:${story.nodes.map((placed) => placed.node.id).join("\0")}`;

  const applyView = () => {
    const g = gRef.current;
    if (!g) return;
    const v = viewRef.current;
    g.setAttribute("transform", `translate(${v.tx} ${v.ty}) scale(${v.k})`);
  };

  useEffect(() => {
    apiRef.current = {
      reset() {
        viewRef.current = resetView();
        applyView();
      },
    };
    return () => {
      apiRef.current = null;
    };
  }, [apiRef]);

  useEffect(() => {
    boxRef.current = { w: story.bounds.w, h: story.bounds.h };
    viewRef.current = resetView();
    applyView();
  }, [layoutKey]);

  const showEmpty = story.nodes.length === 0;
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const toContent = (clientX: number, clientY: number): [number, number] => {
      const rect = svg.getBoundingClientRect();
      const fit = letterboxFit(rect.width, rect.height, boxRef.current.w, boxRef.current.h);
      return [
        (clientX - rect.left - fit.offsetX) / fit.scale,
        (clientY - rect.top - fit.offsetY) / fit.scale,
      ];
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const [px, py] = toContent(e.clientX, e.clientY);
      // Upper clamp scales with content width so labels stay reachable in
      // traces of any size; k = 1 always fits (viewBox spans the bounds).
      const max = fitZoomMax(boxRef.current.w);
      viewRef.current = zoomAt(viewRef.current, px, py, e.deltaY < 0 ? 1.2 : 1 / 1.2, 0.2, max);
      applyView();
    };
    let drag: { x: number; y: number } | null = null;
    // No pointer capture here: capturing the pointer to the <svg> would
    // retarget the click to the svg and node onClick handlers would never
    // fire. Move/up are tracked on the window instead, so panning still
    // works when the pointer leaves the svg.
    const onPointerDown = (e: PointerEvent) => {
      drag = { x: e.clientX, y: e.clientY };
    };
    const onPointerMove = (e: PointerEvent) => {
      if (!drag) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      if (clickSuppressed(dx, dy)) suppressRef.current = true;
      const rect = svg.getBoundingClientRect();
      const fit = letterboxFit(rect.width, rect.height, boxRef.current.w, boxRef.current.h);
      viewRef.current = panBy(viewRef.current, dx / fit.scale, dy / fit.scale);
      drag = { x: e.clientX, y: e.clientY };
      applyView();
    };
    const onPointerUp = () => {
      drag = null;
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    svg.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
    return () => {
      svg.removeEventListener("wheel", onWheel);
      svg.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
    };
  }, [showEmpty]);

  if (story.nodes.length === 0) {
    return (
      <svg id="dag" role="img" aria-label="causal DAG" preserveAspectRatio="xMidYMid meet" ref={svgRef}>
        <g ref={gRef}>
          <text x={20} y={30}>
            no events
          </text>
        </g>
      </svg>
    );
  }

  const highlight = storyHighlight(story, selectedId);
  const byId = new Map(story.nodes.map((placed) => [placed.node.id, placed]));
  const { bounds } = story;
  return (
    <div className="dag-wrap">
      <div className="dag-stage">
        <svg
          id="dag"
          role="img"
          aria-label="causal DAG"
          ref={svgRef}
          preserveAspectRatio="xMidYMid meet"
          viewBox={`0 0 ${bounds.w} ${bounds.h}`}
        >
          <defs>
            <marker
              id="causal-arrow"
              viewBox="0 0 8 8"
              refX="8"
              refY="4"
              markerWidth="6"
              markerHeight="6"
              orient="auto"
            >
              <path d="M0 0 L8 4 L0 8 Z" fill="context-stroke" />
            </marker>
          </defs>
          <g id="viewport" ref={gRef}>
            {story.links.map((link) => {
              switch (link.kind) {
                case "causal": {
                  const edge = causalAsEdge(link);
                  const a = byId.get(edge.parent);
                  const b = byId.get(edge.child);
                  if (!a || !b) return null;
                  const on =
                    !!highlight.lit && highlight.lit.has(link.parent) && highlight.lit.has(link.child);
                  return (
                    <path
                      key={`${edge.parent}->${edge.child}`}
                      d={causalCurve(a, b)}
                      className={on ? "edge lit" : "edge"}
                      markerEnd="url(#causal-arrow)"
                    >
                      {link.omitted ? (
                        <title>{`${link.omitted.length} hidden by filter`}</title>
                      ) : null}
                    </path>
                  );
                }
                case "filter-gap": {
                  const a = byId.get(link.upstream);
                  const b = byId.get(link.downstream);
                  if (!a || !b) return null;
                  return (
                    <path
                      key={`gap:${link.upstream}->${link.downstream}`}
                      className="gap"
                      d={edgeCurve(a, b)}
                    >
                      <title>{`${link.omitted.length} hidden by filter`}</title>
                    </path>
                  );
                }
                case "filter-stub": {
                  const node = byId.get(link.downstream);
                  if (!node) return null;
                  return (
                    <path
                      key={`stub:${link.downstream}`}
                      className="gap"
                      d={`M ${node.x} ${node.y - 28} L ${node.x} ${node.y - 10}`}
                    >
                      <title>{`${link.omitted.length} hidden by filter`}</title>
                    </path>
                  );
                }
              }
              const unreachable: never = link;
              return unreachable;
            })}
            {story.nodes.map((placed) => {
              const n = placed.node;
              const onClick = () => {
                if (suppressRef.current) {
                  suppressRef.current = false;
                  return;
                }
                selectEvent(n.id);
              };
              return (
                <g
                  key={n.id}
                  className={nodeClassNames(n, {
                    selectedId: highlight.selectedId,
                    failureId: story.failureId,
                    litSet: highlight.lit,
                  })}
                  transform={`translate(${placed.x} ${placed.y})`}
                  onClick={onClick}
                >
                  <rect x={-9} y={-9} width={18} height={18} rx={1} />
                  <text x={16} y={4}>
                    {placed.labelText}
                  </text>
                  {placed.roleText ? (
                    <text x={16} y={18}>
                      {placed.roleText}
                    </text>
                  ) : null}
                  <title>{placed.roleText ? `${n.label} ${placed.roleText}` : n.label}</title>
                </g>
              );
            })}
          </g>
        </svg>
        <div className="viz-scanlines" aria-hidden="true" />
      </div>
      <div className="dag-foot">
        <Legend filterGap />
      </div>
    </div>
  );
}
