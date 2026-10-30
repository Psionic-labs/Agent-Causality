/* Failure story for the causal DAG. Visible declared ancestors of the
 * failure. A hidden stretch is a filter gap or a stub, not an edge. */

import { filterOverview, filterSession } from "./filter.ts";
import { ancestorsOf, parentMap } from "./timeline.ts";
import type { GraphOverview, OverviewEdge, OverviewNode } from "./types.ts";

export interface CausalLink {
  readonly kind: "causal";
  readonly parent: string;
  readonly child: string;
  /** Hidden nodes on a parallel path whose endpoints this same edge draws. */
  readonly omitted?: readonly [string, ...string[]];
}

export interface FilterGap {
  readonly kind: "filter-gap";
  readonly upstream: string;
  readonly downstream: string;
  readonly omitted: readonly [string, ...string[]];
}

export interface FilterStub {
  readonly kind: "filter-stub";
  readonly downstream: string;
  readonly omitted: readonly [string, ...string[]];
}

export type ColumnLink = CausalLink | FilterGap | FilterStub;

export interface StoryNode {
  readonly node: OverviewNode;
  readonly labelText: string;
  readonly roleText: string | null;
  readonly x: number;
  readonly y: number;
}

export interface FailureStory {
  readonly failureId: string | null;
  readonly nodes: readonly StoryNode[];
  readonly links: readonly ColumnLink[];
  readonly bounds: { readonly w: number; readonly h: number };
}

export interface StoryHighlight {
  readonly selectedId: string | null;
  readonly lit: ReadonlySet<string> | null;
}

const EMPTY_BOUNDS = { w: 320, h: 160 };
const LABEL_LIMIT = 28;
const X0 = 40;
const X_PITCH = 260;
const Y0 = 48;
const Y_PITCH = 72;
const LABEL_ROOM_X = 230;
const LABEL_ROOM_Y = 40;

export function isCausalLink(link: ColumnLink): link is CausalLink {
  return link.kind === "causal";
}

export function isFilterGap(link: ColumnLink): link is FilterGap {
  return link.kind === "filter-gap";
}

export function isFilterStub(link: ColumnLink): link is FilterStub {
  return link.kind === "filter-stub";
}

/** The only conversion from a story link to an overview edge. */
export function causalAsEdge(link: CausalLink): OverviewEdge {
  return { parent: link.parent, child: link.child };
}

function emptyStory(): FailureStory {
  return { failureId: null, nodes: [], links: [], bounds: EMPTY_BOUNDS };
}

function truncateLabel(label: string): string {
  if (label.length <= LABEL_LIMIT) return label;
  return `${label.slice(0, LABEL_LIMIT - 1)}…`;
}

function compareIds(seq: ReadonlyMap<string, number>, a: string, b: string): number {
  return (seq.get(a) ?? 0) - (seq.get(b) ?? 0) || (a < b ? -1 : a > b ? 1 : 0);
}

function compareNodes(a: OverviewNode, b: OverviewNode): number {
  return a.logical_seq - b.logical_seq || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
}

function nonEmptySorted(
  ids: ReadonlySet<string>,
  seq: ReadonlyMap<string, number>,
): readonly [string, ...string[]] | null {
  const sorted = [...ids].sort((a, b) => compareIds(seq, a, b));
  const [first, ...rest] = sorted;
  if (first === undefined) return null;
  return [first, ...rest];
}

/**
 * Hidden nodes upstream of `hiddenParents`, grouped by the visible story
 * node each path reaches. A cycle must not hide a later hop that does
 * reach a visible ancestor, so reachability is a fixed point.
 */
function hiddenUpstream(
  hiddenParents: readonly string[],
  parentOf: ReadonlyMap<string, string[]>,
  keep: ReadonlySet<string>,
  scopedIds: ReadonlySet<string>,
): { upstreams: Map<string, Set<string>>; dead: Set<string> } {
  const hiddenReachable = new Set<string>();
  const pending = [...hiddenParents];
  const seen = new Set<string>();
  while (pending.length > 0) {
    const id = pending.pop();
    if (id === undefined || seen.has(id)) continue;
    seen.add(id);
    if (!scopedIds.has(id) || keep.has(id)) continue;
    hiddenReachable.add(id);
    for (const parent of parentOf.get(id) ?? []) pending.push(parent);
  }

  const reach = new Map<string, Set<string>>();
  for (const id of hiddenReachable) reach.set(id, new Set());
  let changed = true;
  while (changed) {
    changed = false;
    for (const id of hiddenReachable) {
      const got = reach.get(id);
      if (!got) continue;
      for (const parent of parentOf.get(id) ?? []) {
        if (!scopedIds.has(parent)) continue;
        const fromParent = keep.has(parent) ? [parent] : [...(reach.get(parent) ?? [])];
        for (const upstream of fromParent) {
          if (got.has(upstream)) continue;
          got.add(upstream);
          changed = true;
        }
      }
    }
  }

  const upstreams = new Map<string, Set<string>>();
  const dead = new Set<string>();
  for (const id of hiddenReachable) {
    const ups = reach.get(id);
    if (!ups || ups.size === 0) {
      dead.add(id);
      continue;
    }
    for (const upstream of ups) {
      const bucket = upstreams.get(upstream) ?? new Set<string>();
      bucket.add(id);
      upstreams.set(upstream, bucket);
    }
  }
  return { upstreams, dead };
}

/** Longest causal-ancestor depth. Gaps do not add depth. A cycle contributes 0. */
function causalDepth(ids: readonly string[], links: readonly ColumnLink[]): Map<string, number> {
  const parentOf = new Map<string, string[]>();
  for (const link of links) {
    if (link.kind !== "causal") continue;
    const list = parentOf.get(link.child) ?? [];
    list.push(link.parent);
    parentOf.set(link.child, list);
  }
  const depth = new Map<string, number>();
  const visit = (id: string, stack: Set<string>): number => {
    const known = depth.get(id);
    if (known !== undefined) return known;
    if (stack.has(id)) return 0;
    stack.add(id);
    let d = 0;
    for (const parent of parentOf.get(id) ?? []) d = Math.max(d, visit(parent, stack) + 1);
    stack.delete(id);
    depth.set(id, d);
    return d;
  };
  for (const id of ids) visit(id, new Set());
  return depth;
}

export function failureColumn(
  overview: GraphOverview,
  sessionAgent: string | null,
  hidden: ReadonlySet<string>,
  failureId: string | null,
): FailureStory {
  const scoped = filterSession(overview, sessionAgent);
  const visible = filterOverview(scoped, hidden, failureId);
  if (failureId === null || !scoped.nodes.some((node) => node.id === failureId)) return emptyStory();

  const parents = parentMap(scoped.edges);
  const ancestors = ancestorsOf(failureId, parents);
  const ordered = visible.nodes.filter((node) => node.id === failureId || ancestors.has(node.id));
  ordered.sort(compareNodes);

  const keep = new Set(ordered.map((node) => node.id));
  const scopedIds = new Set(scoped.nodes.map((node) => node.id));
  const seq = new Map(scoped.nodes.map((node) => [node.id, node.logical_seq]));
  const visiblePairs = new Set(visible.edges.map((edge) => `${edge.parent}\0${edge.child}`));
  const links: ColumnLink[] = [];

  for (const child of ordered) {
    const declared = (parents.get(child.id) ?? []).filter((id) => scopedIds.has(id));
    const causalParents: string[] = [];
    const hiddenParents: string[] = [];
    for (const parent of declared) {
      if (keep.has(parent)) causalParents.push(parent);
      else hiddenParents.push(parent);
    }
    causalParents.sort((a, b) => compareIds(seq, a, b));
    for (const parent of causalParents) {
      if (!visiblePairs.has(`${parent}\0${child.id}`)) continue;
      links.push({ kind: "causal", parent, child: child.id });
    }
    if (hiddenParents.length === 0) continue;

    const found = hiddenUpstream(hiddenParents, parents, keep, scopedIds);
    const upstreamIds = [...found.upstreams.keys()].sort((a, b) => compareIds(seq, a, b));
    for (const upstream of upstreamIds) {
      const omitted = nonEmptySorted(found.upstreams.get(upstream) ?? new Set(), seq);
      if (!omitted) continue;
      const index = links.findIndex(
        (link) => link.kind === "causal" && link.parent === upstream && link.child === child.id,
      );
      const direct = links[index];
      if (direct?.kind === "causal") {
        // The direct edge already draws this pair. Keep the hidden count on
        // it instead of dropping it with a redundant overlapping gap.
        if (!direct.omitted) links[index] = { ...direct, omitted };
        continue;
      }
      links.push({
        kind: "filter-gap",
        upstream,
        downstream: child.id,
        omitted,
      });
    }
    const omittedDead = nonEmptySorted(found.dead, seq);
    if (omittedDead) {
      links.push({ kind: "filter-stub", downstream: child.id, omitted: omittedDead });
    }
  }

  const depth = causalDepth(
    ordered.map((node) => node.id),
    links,
  );
  const nodes: StoryNode[] = ordered.map((node, index) => ({
    node,
    labelText: truncateLabel(node.label),
    roleText: node.role ? node.role : null,
    x: X0 + index * X_PITCH,
    y: Y0 + (depth.get(node.id) ?? 0) * Y_PITCH,
  }));
  if (nodes.length === 0) return emptyStory();
  const maxX = nodes.reduce((max, placed) => Math.max(max, placed.x), 0);
  const maxY = nodes.reduce((max, placed) => Math.max(max, placed.y), 0);
  return {
    failureId,
    nodes,
    links,
    bounds: { w: maxX + LABEL_ROOM_X, h: maxY + LABEL_ROOM_Y },
  };
}

export function storyHighlight(story: FailureStory, selectedId: string | null): StoryHighlight {
  if (selectedId === null || !story.nodes.some((placed) => placed.node.id === selectedId)) {
    return { selectedId: null, lit: null };
  }
  const parents = new Map<string, string[]>();
  for (const link of story.links) {
    switch (link.kind) {
      case "causal": {
        const list = parents.get(link.child) ?? [];
        list.push(link.parent);
        parents.set(link.child, list);
        break;
      }
      case "filter-gap":
      case "filter-stub":
        break;
      default: {
        const unreachable: never = link;
        return unreachable;
      }
    }
  }
  const lit = new Set<string>([selectedId]);
  const stack = [...(parents.get(selectedId) ?? [])];
  while (stack.length > 0) {
    const cur = stack.pop();
    if (cur === undefined || lit.has(cur)) continue;
    lit.add(cur);
    for (const parent of parents.get(cur) ?? []) stack.push(parent);
  }
  return { selectedId, lit };
}
