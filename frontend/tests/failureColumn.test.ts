// The graph's failure story: visible declared ancestors, filter gaps, and
// highlight that walks causal links only.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_HIDDEN_TYPES } from "../lib/filter.ts";
import {
  causalAsEdge,
  failureColumn,
  isCausalLink,
  isFilterGap,
  isFilterStub,
  storyHighlight,
} from "../lib/failureColumn.ts";
import type { GraphOverview, OverviewEdge, OverviewNode } from "../lib/types.ts";

function node(
  id: string,
  event_type: string,
  logical_seq: number,
  label: string,
  role: string | null = null,
): OverviewNode {
  return {
    id,
    event_type,
    opencode_kind: "",
    agent_id: "opencode:ses_demo",
    logical_seq,
    wall_time: "",
    label,
    role,
    in_failure_slice: true,
  };
}

const NODES = [
  node("run", "run_start", 1, "run start"),
  node("part1", "context_update", 2, "part update"),
  node("model1", "model_call", 3, "model turn"),
  node("read", "tool_call", 4, "read file"),
  node("read-out", "tool_result", 5, "read result"),
  node("part2", "context_update", 6, "part update 2"),
  node("model2", "model_call", 7, "model turn 2"),
  node("edit", "tool_call", 8, "edit file"),
  node("edit-out", "tool_result", 9, "edit result"),
  node("bash", "tool_call", 10, "bash pytest"),
  node("bash-out", "tool_result", 11, "bash python test_app.py", "retry_success"),
  node("stray", "tool_call", 12, "orphan tool"),
];

const EDGES = [
  { parent: "run", child: "part1" },
  { parent: "part1", child: "model1" },
  { parent: "model1", child: "read" },
  { parent: "read", child: "read-out" },
  { parent: "read-out", child: "part2" },
  { parent: "part2", child: "model2" },
  { parent: "model2", child: "edit" },
  { parent: "edit", child: "edit-out" },
  { parent: "edit-out", child: "bash" },
  { parent: "bash", child: "bash-out" },
];

function overview(): GraphOverview {
  return {
    source: "test",
    event_count: NODES.length,
    edge_count: EDGES.length,
    failure_event_id: "bash-out",
    failure_status: "fallback_last_event",
    failure_method: "fallback",
    nodes: NODES,
    edges: EDGES,
  };
}

function at(story: ReturnType<typeof failureColumn>, id: string) {
  const found = story.nodes.find((placed) => placed.node.id === id);
  assert.ok(found, id);
  return found;
}

describe("failure story", () => {
  it("draws declared tool links and counts hidden stretches as gaps", () => {
    const source = overview();
    const before = JSON.stringify(source);
    const story = failureColumn(source, "opencode:ses_demo", DEFAULT_HIDDEN_TYPES, "bash-out");
    assert.equal(JSON.stringify(source), before);

    const causal = story.links.filter(isCausalLink).map(causalAsEdge);
    assert.deepEqual(causal, [
      { parent: "read", child: "read-out" },
      { parent: "edit", child: "edit-out" },
      { parent: "edit-out", child: "bash" },
      { parent: "bash", child: "bash-out" },
    ]);

    const gaps = story.links.filter(isFilterGap);
    assert.deepEqual(
      gaps.map((gap) => [gap.upstream, gap.downstream, gap.omitted.length]),
      [
        ["run", "read", 2],
        ["read-out", "edit", 2],
      ],
    );
    assert.deepEqual(gaps[0]?.omitted, ["part1", "model1"]);
    assert.deepEqual(gaps[1]?.omitted, ["part2", "model2"]);
    for (const gap of gaps) {
      assert.equal("parent" in gap, false);
      assert.equal("child" in gap, false);
    }
    assert.equal(story.links.some(isFilterStub), false);

    const bashOut = at(story, "bash-out");
    assert.ok(bashOut.labelText.includes("bash python test_app.py"));
    assert.equal(bashOut.roleText, "retry_success");
    assert.equal(story.nodes.some((placed) => placed.node.id === "stray"), false);

    assert.ok(story.nodes.length >= 2);
    for (let i = 1; i < story.nodes.length; i += 1) {
      const prev = story.nodes[i - 1];
      const cur = story.nodes[i];
      assert.ok(prev);
      assert.ok(cur);
      assert.ok(
        prev.node.logical_seq < cur.node.logical_seq ||
          (prev.node.logical_seq === cur.node.logical_seq && prev.node.id < cur.node.id),
      );
      assert.ok(cur.x > prev.x);
    }
    const first = story.nodes[0];
    const second = story.nodes[1];
    assert.ok(first);
    assert.ok(second);
    assert.equal(first.x, 40);
    assert.equal(second.x - first.x, 260);

    const read = at(story, "read");
    const readOut = at(story, "read-out");
    const run = at(story, "run");
    assert.ok(readOut.y > read.y);
    assert.equal(read.y, run.y);
    assert.equal(read.y, 48);
    assert.equal(readOut.y - read.y, 72);

    const sample = gaps[0];
    assert.ok(sample);
    const takesEdge = (_edge: OverviewEdge): void => undefined;
    // @ts-expect-error a filter gap has no parent or child and is not an OverviewEdge
    takesEdge(sample);
  });

  it("keeps a pinned context update and the visible ancestors above it", () => {
    const story = failureColumn(overview(), "opencode:ses_demo", DEFAULT_HIDDEN_TYPES, "part2");
    assert.deepEqual(
      story.nodes.map((placed) => placed.node.id),
      ["run", "read", "read-out", "part2"],
    );
    assert.equal(
      story.nodes.some((placed) => placed.node.id === "edit"),
      false,
    );
    assert.deepEqual(story.links.filter(isCausalLink).map(causalAsEdge), [
      { parent: "read", child: "read-out" },
      { parent: "read-out", child: "part2" },
    ]);
    const gaps = story.links.filter(isFilterGap);
    assert.deepEqual(
      gaps.map((gap) => [gap.upstream, gap.downstream, gap.omitted.length]),
      [["run", "read", 2]],
    );
    assert.equal(story.links.some(isFilterStub), false);
  });

  it("shows a pinned hidden failure with a stub when no visible ancestor exists", () => {
    const pinned: GraphOverview = {
      source: "test",
      event_count: 2,
      edge_count: 1,
      failure_event_id: "part2",
      failure_status: "fallback_last_event",
      failure_method: "fallback",
      nodes: [
        node("model1", "model_call", 1, "hidden model"),
        node("part2", "context_update", 2, "pinned part"),
      ],
      edges: [{ parent: "model1", child: "part2" }],
    };
    const story = failureColumn(pinned, "opencode:ses_demo", DEFAULT_HIDDEN_TYPES, "part2");
    assert.deepEqual(
      story.nodes.map((placed) => placed.node.id),
      ["part2"],
    );
    assert.equal(story.links.some(isCausalLink), false);
    const stubs = story.links.filter(isFilterStub);
    assert.equal(stubs.length, 1);
    const stub = stubs[0];
    assert.ok(stub);
    assert.equal(stub.downstream, "part2");
    assert.deepEqual(stub.omitted, ["model1"]);
    assert.equal("parent" in stub, false);
    assert.equal("child" in stub, false);
  });

  it("lights causal ancestors and stops at a filter gap", () => {
    const story = failureColumn(overview(), "opencode:ses_demo", DEFAULT_HIDDEN_TYPES, "bash-out");
    const fromFailure = storyHighlight(story, "bash-out");
    assert.equal(fromFailure.selectedId, "bash-out");
    assert.deepEqual(fromFailure.lit, new Set(["bash-out", "bash", "edit-out", "edit"]));
    assert.equal(fromFailure.lit?.has("run"), false);
    assert.equal(fromFailure.lit?.has("read-out"), false);

    const fromEdit = storyHighlight(story, "edit");
    assert.deepEqual(fromEdit.lit, new Set(["edit"]));
    assert.equal(fromEdit.lit?.has("read-out"), false);

    const fromBash = storyHighlight(story, "bash");
    assert.deepEqual(fromBash.lit, new Set(["bash", "edit-out", "edit"]));
    assert.equal(fromBash.lit?.has("read-out"), false);
    assert.equal(fromBash.lit?.has("run"), false);

    const pinned = failureColumn(overview(), "opencode:ses_demo", DEFAULT_HIDDEN_TYPES, "part2");
    const fromPart = storyHighlight(pinned, "part2");
    assert.equal(fromPart.lit?.has("read-out"), true);
    assert.equal(fromPart.lit?.has("read"), true);
    assert.equal(fromPart.lit?.has("run"), false);

    assert.deepEqual(storyHighlight(story, null), { selectedId: null, lit: null });
    assert.deepEqual(storyHighlight(story, "part2"), { selectedId: null, lit: null });
    assert.deepEqual(storyHighlight(story, "stray"), { selectedId: null, lit: null });
  });

  it("truncates a long label to 28 characters and leaves a short one whole", () => {
    const long = "abcdefghijklmnopqrstuvwxyz0123456789";
    const exact = "1234567890123456789012345678";
    assert.equal(exact.length, 28);
    const source: GraphOverview = {
      source: "test",
      event_count: 2,
      edge_count: 1,
      failure_event_id: "long",
      failure_status: null,
      failure_method: null,
      nodes: [
        node("exact", "tool_call", 1, exact),
        node("long", "tool_result", 2, long, "kept-role"),
      ],
      edges: [{ parent: "exact", child: "long" }],
    };
    const story = failureColumn(source, "opencode:ses_demo", DEFAULT_HIDDEN_TYPES, "long");
    assert.equal(at(story, "exact").labelText, exact);
    assert.equal(at(story, "exact").roleText, null);
    const truncated = at(story, "long");
    assert.equal(truncated.labelText.length, 28);
    assert.equal(truncated.labelText, `${long.slice(0, 27)}…`);
    assert.equal(truncated.roleText, "kept-role");
  });

  it("returns an empty story when the failure is missing from the session", () => {
    const missing = failureColumn(overview(), "opencode:ses_demo", DEFAULT_HIDDEN_TYPES, null);
    assert.equal(missing.failureId, null);
    assert.deepEqual(missing.nodes, []);
    assert.deepEqual(missing.links, []);
    assert.deepEqual(missing.bounds, { w: 320, h: 160 });

    const otherSession = failureColumn(
      overview(),
      "opencode:ses_other",
      DEFAULT_HIDDEN_TYPES,
      "bash-out",
    );
    assert.equal(otherSession.failureId, null);
    assert.deepEqual(otherSession.nodes, []);
    assert.deepEqual(otherSession.links, []);
  });
});
