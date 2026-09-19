import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import cytoscape, { Core, NodeSingular } from "cytoscape";
import PageShell from "../components/PageShell";
import api from "../lib/api";

type GraphNode = {
  data: {
    id: string;
    label: string;
    pagerank: number;
    betweenness: number;
    eigenvector: number;
    degree: number;
    influence_score: number;
    community: string;
  };
};
type GraphEdge = { data: { source: string; target: string; weight: number } };
type GraphPayload = { mode: string; nodes: GraphNode[]; edges: GraphEdge[] };

type CausalScore = { node: string; causal_impact_score: number };
type CausalPayload = { mode: string; run_id: string | null; scores: CausalScore[] };

type TopicRow = { id: string; label: string; velocity_score: number };
type ReplayFrame = {
  timestamp: string;
  node: string;
  platform: string;
  community: string;
  topic_match_score: number;
  sentiment: string | null;
  emotion_bucket: string | null;
  cumulative_reach: number;
  cumulative_communities_reached: number;
};
type ReplayPayload = { mode: string; topic_id: string; frames: ReplayFrame[] };

// Stable color per community label, so re-renders don't shuffle colors.
const COMMUNITY_PALETTE = ["#FF9933", "#138808", "#3B82F6", "#EC4899", "#A855F7", "#F59E0B", "#10B981", "#EF4444"];
function colorForCommunity(label: string): string {
  if (label === "unassigned") return "#64748B";
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  return COMMUNITY_PALETTE[hash % COMMUNITY_PALETTE.length];
}

const FRAME_INTERVAL_MS = 700;

export default function NetworkIntelligence() {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const playIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [payload, setPayload] = useState<GraphPayload | null>(null);
  const [selected, setSelected] = useState<GraphNode["data"] | null>(null);
  const [running, setRunning] = useState(false);
  const [canAnalyze, setCanAnalyze] = useState(false);

  const [causal, setCausal] = useState<CausalPayload | null>(null);
  const [computingCausal, setComputingCausal] = useState(false);

  const [topics, setTopics] = useState<TopicRow[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState<string>("");
  const [frames, setFrames] = useState<ReplayFrame[] | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  async function loadGraph() {
    const { data } = await api.get<GraphPayload>("/network/graph");
    setPayload(data);
  }
  async function loadCausal() {
    const { data } = await api.get<CausalPayload>("/network/causal-impact");
    setCausal(data);
  }
  async function loadTopics() {
    const { data } = await api.get<{ topics: TopicRow[] }>("/trends");
    setTopics(data.topics);
  }

  useEffect(() => {
    loadGraph();
    loadCausal();
    loadTopics();
    api.get("/auth/me").then(({ data }) => {
      setCanAnalyze(["admin", "analyst", "investigator"].includes(data.role));
    }).catch(() => {});
    return () => {
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    };
  }, []);

  useEffect(() => {
    if (!containerRef.current || !payload) return;
    cyRef.current?.destroy();

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...payload.nodes, ...payload.edges],
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele: NodeSingular) => colorForCommunity(ele.data("community")),
            width: (ele: NodeSingular) => 16 + ele.data("influence_score") * 40,
            height: (ele: NodeSingular) => 16 + ele.data("influence_score") * 40,
            label: "data(label)",
            "font-size": 8,
            color: "#E2E8F0",
            "text-valign": "bottom",
            "text-margin-y": 4,
          },
        },
        {
          selector: "edge",
          style: {
            width: (ele: any) => Math.max(1, Math.min(6, ele.data("weight"))),
            "line-color": "#475569",
            "target-arrow-color": "#475569",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            opacity: 0.5,
          },
        },
        {
          selector: "node:selected",
          style: { "border-width": 3, "border-color": "#FF9933" },
        },
        {
          selector: ".replay-active",
          style: { "border-width": 4, "border-color": "#FBBF24", "border-opacity": 1 },
        },
      ],
      layout: { name: "cose", animate: false },
    });

    cy.on("tap", "node", (evt) => setSelected(evt.target.data()));
    cy.on("tap", (evt) => {
      if (evt.target === cy) setSelected(null);
    });

    cyRef.current = cy;
    return () => cy.destroy();
  }, [payload]);

  // Highlight the current replay frame's node on the graph.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !frames) return;
    cy.nodes().removeClass("replay-active");
    const current = frames[frameIndex];
    if (current) {
      const node = cy.getElementById(current.node);
      if (node.nonempty()) node.addClass("replay-active");
    }
  }, [frameIndex, frames]);

  async function runAnalysis() {
    setRunning(true);
    try {
      await api.post("/network/analyze", {});
      await loadGraph();
    } finally {
      setRunning(false);
    }
  }

  async function computeCausalImpact() {
    setComputingCausal(true);
    try {
      await api.post("/network/causal-impact", null, { params: { top_n: 10 } });
      await loadCausal();
    } finally {
      setComputingCausal(false);
    }
  }

  function stopPlayback() {
    if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    playIntervalRef.current = null;
    setPlaying(false);
  }

  async function togglePlay() {
    if (playing) {
      stopPlayback();
      return;
    }
    let activeFrames = frames;
    if (!activeFrames && selectedTopicId) {
      const { data } = await api.get<ReplayPayload>(`/network/propagation-replay/${selectedTopicId}`);
      activeFrames = data.frames;
      setFrames(activeFrames);
      setFrameIndex(0);
    }
    if (!activeFrames || activeFrames.length === 0) return;

    setPlaying(true);
    playIntervalRef.current = setInterval(() => {
      setFrameIndex((prev) => {
        if (prev + 1 >= (activeFrames as ReplayFrame[]).length) {
          stopPlayback();
          return prev;
        }
        return prev + 1;
      });
    }, FRAME_INTERVAL_MS);
  }

  async function onSelectTopic(topicId: string) {
    stopPlayback();
    setSelectedTopicId(topicId);
    setFrames(null);
    setFrameIndex(0);
    if (!topicId) return;
    const { data } = await api.get<ReplayPayload>(`/network/propagation-replay/${topicId}`);
    setFrames(data.frames);
  }

  function resetReplay() {
    stopPlayback();
    setFrameIndex(0);
  }

  const currentFrame = frames?.[frameIndex];
  const maxCausalScore = Math.max(1, ...(causal?.scores ?? []).map((s) => Math.abs(s.causal_impact_score)));

  return (
    <PageShell title={t("nav.network")}>
      <div className="mb-3 flex items-center justify-between">
        <div className="inline-block rounded bg-amber-900/40 px-3 py-1 text-xs text-amber-300">
          {payload?.mode === "computed" ? t("network.modeComputed") : t("network.modeStatic")}
        </div>
        {canAnalyze && (
          <button
            onClick={runAnalysis}
            disabled={running}
            className="rounded bg-saffron px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
          >
            {running ? t("network.running") : t("network.runAnalysis")}
          </button>
        )}
      </div>

      {payload && payload.nodes.length === 0 ? (
        <p className="text-slate-400 text-sm">{t("network.emptyState")}</p>
      ) : (
        <div className="flex gap-4">
          <div ref={containerRef} className="h-[560px] flex-1 rounded bg-slate-900" />
          <div className="w-64 shrink-0 rounded bg-slate-900 p-4 text-sm">
            <h2 className="mb-3 font-semibold text-saffron">{t("network.nodeDetails.title")}</h2>
            {!selected && <p className="text-xs text-slate-500">{t("network.nodeDetails.selectHint")}</p>}
            {selected && (
              <dl className="space-y-2 text-xs">
                <div><dt className="text-slate-500">ID</dt><dd className="font-mono">{selected.label}</dd></div>
                <div><dt className="text-slate-500">{t("network.nodeDetails.community")}</dt><dd>{selected.community}</dd></div>
                <div><dt className="text-slate-500">{t("network.nodeDetails.influence")}</dt><dd>{selected.influence_score}</dd></div>
                <div><dt className="text-slate-500">{t("network.nodeDetails.pagerank")}</dt><dd>{selected.pagerank}</dd></div>
                <div><dt className="text-slate-500">{t("network.nodeDetails.betweenness")}</dt><dd>{selected.betweenness}</dd></div>
                <div><dt className="text-slate-500">{t("network.nodeDetails.eigenvector")}</dt><dd>{selected.eigenvector}</dd></div>
                <div><dt className="text-slate-500">{t("network.nodeDetails.degree")}</dt><dd>{selected.degree}</dd></div>
              </dl>
            )}
          </div>
        </div>
      )}

      <div className="mt-6 grid grid-cols-2 gap-4">
        {/* Causal Impact */}
        <div className="rounded bg-slate-900 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-saffron">{t("network.causalImpact.title")}</h2>
            {canAnalyze && (
              <button
                onClick={computeCausalImpact}
                disabled={computingCausal}
                className="rounded bg-saffron px-3 py-1 text-xs font-semibold text-slate-950 disabled:opacity-50"
              >
                {computingCausal ? t("network.causalImpact.computing") : t("network.causalImpact.compute")}
              </button>
            )}
          </div>
          {!causal || causal.scores.length === 0 ? (
            <p className="text-xs text-slate-500">{t("network.causalImpact.empty")}</p>
          ) : (
            <table className="w-full text-xs">
              <thead className="text-slate-500 text-left">
                <tr>
                  <th className="py-1 pr-2">{t("network.causalImpact.columns.node")}</th>
                  <th className="py-1">{t("network.causalImpact.columns.score")}</th>
                </tr>
              </thead>
              <tbody>
                {causal.scores.slice(0, 10).map((s) => (
                  <tr key={s.node} className="border-t border-slate-800">
                    <td className="py-1 pr-2 font-mono">{s.node}</td>
                    <td className="py-1">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-2 rounded bg-saffron"
                          style={{ width: `${Math.max(4, (Math.abs(s.causal_impact_score) / maxCausalScore) * 80)}px` }}
                        />
                        <span className="text-slate-400">{s.causal_impact_score}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Propagation Replay */}
        <div className="rounded bg-slate-900 p-4">
          <h2 className="mb-3 font-semibold text-saffron">{t("network.propagation.title")}</h2>
          {topics.length === 0 ? (
            <p className="text-xs text-slate-500">{t("network.propagation.noTopics")}</p>
          ) : (
            <>
              <select
                value={selectedTopicId}
                onChange={(e) => onSelectTopic(e.target.value)}
                className="mb-3 w-full rounded bg-slate-800 px-2 py-1 text-xs text-slate-200 outline-none focus:ring-1 focus:ring-saffron"
              >
                <option value="">{t("network.propagation.selectTopic")}</option>
                {topics.map((topic) => (
                  <option key={topic.id} value={topic.id}>{topic.label}</option>
                ))}
              </select>

              {selectedTopicId && frames && frames.length === 0 && (
                <p className="text-xs text-slate-500">{t("network.propagation.empty")}</p>
              )}

              {frames && frames.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={togglePlay}
                      className="rounded bg-saffron px-3 py-1 text-xs font-semibold text-slate-950"
                    >
                      {playing ? t("network.propagation.pause") : t("network.propagation.play")}
                    </button>
                    <button
                      onClick={resetReplay}
                      className="rounded bg-slate-800 px-3 py-1 text-xs text-slate-300"
                    >
                      {t("network.propagation.reset")}
                    </button>
                    <span className="text-xs text-slate-500">
                      {t("network.propagation.frame", { current: frameIndex + 1, total: frames.length })}
                    </span>
                  </div>
                  {currentFrame && (
                    <dl className="space-y-1 text-xs">
                      <div><dt className="inline text-slate-500">Node: </dt><dd className="inline font-mono">{currentFrame.node}</dd></div>
                      <div><dt className="inline text-slate-500">Community: </dt><dd className="inline">{currentFrame.community}</dd></div>
                      <div><dt className="inline text-slate-500">{t("network.propagation.communitiesReached")}: </dt><dd className="inline">{currentFrame.cumulative_communities_reached}</dd></div>
                      <div><dt className="inline text-slate-500">{t("network.propagation.reach")}: </dt><dd className="inline">{currentFrame.cumulative_reach}</dd></div>
                      {currentFrame.sentiment && (
                        <div><dt className="inline text-slate-500">{t("network.propagation.sentiment")}: </dt><dd className="inline capitalize">{currentFrame.sentiment}</dd></div>
                      )}
                    </dl>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </PageShell>
  );
}
