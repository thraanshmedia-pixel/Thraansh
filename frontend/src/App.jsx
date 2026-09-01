import { useCallback, useEffect, useState } from "react";

import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";
import "./App.css";

const API = "http://127.0.0.1:8000";

const NODES_STORAGE_KEY = "thraansh-workflow-nodes-v3";
const EDGES_STORAGE_KEY = "thraansh-workflow-edges-v3";

const DEFAULT_NODES = [
  {
    id: "scheduler",
    type: "workflow",
    position: { x: 410, y: 15 },
    data: {
      label: "Scheduler",
      subtitle: "Daily trigger",
      icon: "⏰",
      executable: false,
      status: "ready",
      statusLabel: "Active",
    },
  },
  {
    id: "news",
    type: "workflow",
    position: { x: 410, y: 80 },
    data: {
      label: "News Collector",
      subtitle: "Latest articles",
      icon: "📰",
      executable: true,
      status: "ready",
      statusLabel: "Ready",
    },
  },
  {
    id: "processor",
    type: "workflow",
    position: { x: 410, y: 145 },
    data: {
      label: "Content Processor",
      subtitle: "Filter & duplicates",
      icon: "⚙️",
      executable: true,
      status: "ready",
      statusLabel: "Ready",
    },
  },
  {
    id: "queue",
    type: "workflow",
    position: { x: 210, y: 145 },
    data: {
      label: "Article Queue",
      subtitle: "Queue / Data",
      icon: "🗃️",
      executable: false,
      status: "ready",
      statusLabel: "Connected",
    },
  },
  {
    id: "script",
    type: "workflow",
    position: { x: 410, y: 210 },
    data: {
      label: "Script Generator",
      subtitle: "Narration script",
      icon: "✍️",
      executable: true,
      status: "ready",
      statusLabel: "Ready",
    },
  },
  {
    id: "voice",
    type: "workflow",
    position: { x: 610, y: 210 },
    data: {
      label: "Voice Generator",
      subtitle: "Narration audio",
      icon: "🎙️",
      executable: true,
      status: "ready",
      statusLabel: "Ready",
    },
  },
  {
    id: "logs",
    type: "workflow",
    position: { x: 210, y: 210 },
    data: {
      label: "Logs",
      subtitle: "Execution history",
      icon: "📜",
      executable: false,
      status: "ready",
      statusLabel: "Recording",
    },
  },
  {
    id: "sceneplanner",
    type: "workflow",
    position: { x: 410, y: 275 },
    data: {
      label: "Scene Planner",
      subtitle: "Visual planning",
      icon: "🎬",
      executable: true,
      status: "ready",
      statusLabel: "Ready",
    },
  },
  {
    id: "pexels",
    type: "workflow",
    position: { x: 610, y: 275 },
    data: {
      label: "Pexels API",
      subtitle: "Stock footage",
      icon: "🎞️",
      executable: false,
      status: "ready",
      statusLabel: "Connected",
    },
  },
  {
    id: "footage",
    type: "workflow",
    position: { x: 410, y: 340 },
    data: {
      label: "Smart Footage",
      subtitle: "Relevant clips",
      icon: "📥",
      executable: true,
      status: "ready",
      statusLabel: "Ready",
    },
  },
  {
    id: "ffmpeg",
    type: "workflow",
    position: { x: 210, y: 405 },
    data: {
      label: "FFmpeg Engine",
      subtitle: "Media engine",
      icon: "⚡",
      executable: false,
      status: "ready",
      statusLabel: "Available",
    },
  },
  {
    id: "renderer",
    type: "workflow",
    position: { x: 410, y: 405 },
    data: {
      label: "Video Renderer",
      subtitle: "Final MP4",
      icon: "🖥️",
      executable: true,
      status: "ready",
      statusLabel: "Ready",
    },
  },
  {
    id: "rights",
    type: "workflow",
    position: { x: 410, y: 470 },
    data: {
      label: "Rights Checker",
      subtitle: "Media validation",
      icon: "🛡️",
      executable: true,
      status: "ready",
      statusLabel: "Enabled",
    },
  },
  {
    id: "publish",
    type: "workflow",
    position: { x: 410, y: 535 },
    data: {
      label: "Publishing Hub",
      subtitle: "Distribution",
      icon: "🚀",
      executable: false,
      status: "ready",
      statusLabel: "Online",
    },
  },
  {
    id: "youtube",
    type: "workflow",
    position: { x: 210, y: 600 },
    data: {
      label: "YouTube",
      subtitle: "Public publishing",
      icon: "▶️",
      executable: true,
      status: "ready",
      statusLabel: "Active",
    },
  },
  {
    id: "x",
    type: "workflow",
    position: { x: 410, y: 600 },
    data: {
      label: "X",
      subtitle: "Social publishing",
      icon: "𝕏",
      executable: false,
      status: "waiting",
      statusLabel: "Not Connected",
    },
  },
  {
    id: "meta",
    type: "workflow",
    position: { x: 610, y: 600 },
    data: {
      label: "Meta API",
      subtitle: "Meta gateway",
      icon: "∞",
      executable: false,
      status: "warning",
      statusLabel: "Under Review",
    },
  },
  {
    id: "facebook",
    type: "workflow",
    position: { x: 540, y: 665 },
    data: {
      label: "Facebook",
      subtitle: "Video publishing",
      icon: "f",
      executable: false,
      status: "warning",
      statusLabel: "Under Review",
    },
  },
  {
    id: "instagram",
    type: "workflow",
    position: { x: 690, y: 665 },
    data: {
      label: "Instagram",
      subtitle: "Reels / video",
      icon: "◎",
      executable: false,
      status: "warning",
      statusLabel: "Under Review",
    },
  },
];

const DEFAULT_EDGES = [
  ["scheduler", "news"],
  ["news", "processor"],
  ["processor", "script"],
  ["processor", "queue"],
  ["script", "voice"],
  ["script", "sceneplanner"],
  ["script", "logs"],
  ["queue", "footage"],
  ["sceneplanner", "footage"],
  ["pexels", "footage"],
  ["footage", "renderer"],
  ["ffmpeg", "renderer"],
  ["renderer", "rights"],
  ["rights", "publish"],
  ["publish", "youtube"],
  ["publish", "x"],
  ["publish", "meta"],
  ["meta", "facebook"],
  ["meta", "instagram"],
].map(([source, target], index) => ({
  id: `edge-${index}`,
  source,
  target,
  type: "smoothstep",
  animated: true,
  markerEnd: {
    type: MarkerType.ArrowClosed,
  },
}));

function WorkflowNode({ data, selected }) {
  const state = data.running
    ? "running"
    : data.status || "ready";

  return (
    <div
      className={`workflow-node ${state} ${
        selected ? "selected-node" : ""
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="flow-handle"
      />

      <div className="node-top">
        <div className="node-icon">
          {data.icon || "⚙️"}
        </div>

        <div className="node-copy">
          <div className="node-title">
            {data.label}
          </div>

          <div className="node-subtitle">
            {data.subtitle}
          </div>
        </div>
      </div>

      <div className="node-footer">
        <span className={`status-dot ${state}`} />

        <span>
          {data.running
            ? "Running"
            : data.statusLabel || "Ready"}
        </span>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="flow-handle"
      />
    </div>
  );
}

const nodeTypes = {
  workflow: WorkflowNode,
};

function Metric({ label, value, sub }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-sub">{sub}</div>
    </div>
  );
}

function App() {
  function loadSavedNodes() {
    try {
      const saved = localStorage.getItem(
        NODES_STORAGE_KEY
      );

      return saved
        ? JSON.parse(saved)
        : DEFAULT_NODES;
    } catch {
      return DEFAULT_NODES;
    }
  }

  function loadSavedEdges() {
    try {
      const saved = localStorage.getItem(
        EDGES_STORAGE_KEY
      );

      return saved
        ? JSON.parse(saved)
        : DEFAULT_EDGES;
    } catch {
      return DEFAULT_EDGES;
    }
  }

  const [
    nodes,
    setNodes,
    onNodesChange,
  ] = useNodesState(loadSavedNodes());

  const [
    edges,
    setEdges,
    onEdgesChange,
  ] = useEdgesState(loadSavedEdges());

  const [status, setStatus] = useState({});
  const [executions, setExecutions] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [message, setMessage] = useState("");

  const onConnect = useCallback(
    (connection) => {
      setEdges((currentEdges) =>
        addEdge(
          {
            ...connection,
            id: `edge-${Date.now()}`,
            type: "smoothstep",
            animated: true,
            markerEnd: {
              type: MarkerType.ArrowClosed,
            },
          },
          currentEdges
        )
      );
    },
    [setEdges]
  );

  useEffect(() => {
    localStorage.setItem(
      NODES_STORAGE_KEY,
      JSON.stringify(nodes)
    );
  }, [nodes]);

  useEffect(() => {
    localStorage.setItem(
      EDGES_STORAGE_KEY,
      JSON.stringify(edges)
    );
  }, [edges]);

  async function loadBackend() {
    try {
      const [
        statusResponse,
        executionResponse,
        platformResponse,
      ] = await Promise.all([
        fetch(`${API}/status`),
        fetch(`${API}/executions`),
        fetch(`${API}/platforms`),
      ]);

      if (statusResponse.ok) {
        const data = await statusResponse.json();

        setStatus(data);

        setNodes((currentNodes) =>
          currentNodes.map((node) => ({
            ...node,
            data: {
              ...node.data,
              running:
                data.current_node === node.id,
            },
          }))
        );
      }

      if (executionResponse.ok) {
        setExecutions(
          await executionResponse.json()
        );
      }

      if (platformResponse.ok) {
        const platforms =
          await platformResponse.json();

        setNodes((currentNodes) =>
          currentNodes.map((node) => {
            if (node.id === "youtube") {
              return {
                ...node,
                data: {
                  ...node.data,
                  status:
                    platforms.youtube?.connected
                      ? "ready"
                      : "waiting",
                  statusLabel:
                    platforms.youtube?.status ||
                    "Unknown",
                },
              };
            }

            if (node.id === "x") {
              return {
                ...node,
                data: {
                  ...node.data,
                  status:
                    platforms.x?.connected
                      ? "ready"
                      : "waiting",
                  statusLabel:
                    platforms.x?.status ||
                    "Not Connected",
                },
              };
            }

            if (node.id === "facebook") {
              return {
                ...node,
                data: {
                  ...node.data,
                  status:
                    platforms.facebook?.connected
                      ? "ready"
                      : "warning",
                  statusLabel:
                    platforms.facebook?.status ||
                    "Under Review",
                },
              };
            }

            if (node.id === "instagram") {
              return {
                ...node,
                data: {
                  ...node.data,
                  status:
                    platforms.instagram?.connected
                      ? "ready"
                      : "warning",
                  statusLabel:
                    platforms.instagram?.status ||
                    "Under Review",
                },
              };
            }

            return node;
          })
        );
      }

      setMessage("");
    } catch {
      setMessage("Backend API is not running.");
    }
  }

  useEffect(() => {
    loadBackend();

    const timer = setInterval(
      loadBackend,
      3000
    );

    return () => clearInterval(timer);
  }, []);

  async function runAutomation() {
    try {
      const response = await fetch(
        `${API}/run`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail ||
            "Unable to start workflow."
        );
      }

      setMessage(
        "THRAANSH workflow started."
      );

      loadBackend();
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function runNode(nodeId) {
    try {
      const response = await fetch(
        `${API}/run-node/${nodeId}`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail ||
            "Unable to run node."
        );
      }

      setMessage(result.message);
      loadBackend();
    } catch (error) {
      setMessage(error.message);
    }
  }

  function resetLayout() {
    localStorage.removeItem(
      NODES_STORAGE_KEY
    );

    localStorage.removeItem(
      EDGES_STORAGE_KEY
    );

    setNodes(DEFAULT_NODES);
    setEdges(DEFAULT_EDGES);
    setSelectedNode(null);

    setMessage("Compact layout restored.");
  }

  function deleteSelectedNode() {
    if (!selectedNode) {
      return;
    }

    const id = selectedNode.id;

    setNodes((items) =>
      items.filter((node) => node.id !== id)
    );

    setEdges((items) =>
      items.filter(
        (edge) =>
          edge.source !== id &&
          edge.target !== id
      )
    );

    setSelectedNode(null);
  }

  const nodeExecution = selectedNode
    ? executions.find(
        (item) =>
          item.node_id === selectedNode.id
      )
    : null;

  return (
    <div className="studio-shell">
      <header className="studio-header">
        <div className="studio-brand">
          <div className="studio-logo">T</div>

          <div>
            <h1>THRAANSH</h1>
            <p>Agentic Workflow Studio</p>
          </div>

          <span className="header-live">● LIVE</span>
        </div>

        <div className="header-actions">
          <button
            className="secondary-button"
            onClick={resetLayout}
          >
            Reset Layout
          </button>

          <button
            className="secondary-button"
            onClick={loadBackend}
          >
            ↻ Refresh
          </button>

          <button
            className="primary-button"
            onClick={runAutomation}
            disabled={status.automation_running}
          >
            {status.automation_running
              ? "● Running"
              : "▶ Execute Workflow"}
          </button>
        </div>
      </header>

      <section className="studio-metrics">
        <Metric
          label="Engine Status"
          value={status.system_status || "READY"}
          sub="Backend"
        />

        <Metric
          label="Current Node"
          value={status.current_node || "--"}
          sub="Live execution"
        />

        <Metric
          label="Published Videos"
          value={status.published_videos ?? 0}
          sub="YouTube"
        />

        <Metric
          label="Pending Articles"
          value={status.pending_articles ?? 0}
          sub="Queue"
        />

        <Metric
          label="Failed Jobs"
          value={status.failed_jobs ?? 0}
          sub="Last runs"
        />
      </section>

      {message && (
        <div className="system-message">
          {message}
        </div>
      )}

      <section className="studio-workspace">
        <div className="canvas-panel">
          <div className="canvas-toolbar">
            <div>
              <strong>
                THRAANSH Main Workflow
              </strong>

              <span>
                Drag nodes • connect nodes • zoom • pan
              </span>
            </div>

            <div className="canvas-status">
              ● LIVE
            </div>
          </div>

          <div className="workflow-canvas-large">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={(_, node) =>
                setSelectedNode(node)
              }
              nodesDraggable
              nodesConnectable
              elementsSelectable
              zoomOnScroll
              zoomOnPinch
              panOnDrag
              selectionOnDrag
              minZoom={0.25}
              maxZoom={3}
              defaultViewport={{
                x: 120,
                y: 8,
                zoom: 0.86,
              }}
              snapToGrid
              snapGrid={[10, 10]}
              deleteKeyCode={[
                "Backspace",
                "Delete",
              ]}
              defaultEdgeOptions={{
                type: "smoothstep",
                animated: true,
                markerEnd: {
                  type: MarkerType.ArrowClosed,
                },
              }}
            >
              <Background
                gap={18}
                size={1}
              />

              <Controls
                showZoom
                showFitView
                showInteractive
              />
            </ReactFlow>
          </div>
        </div>

        <aside className="node-inspector">
          <div className="inspector-header">
            <span className="inspector-label">
              NODE INSPECTOR
            </span>

            <h2>
              {selectedNode
                ? selectedNode.data.label
                : "Select a node"}
            </h2>
          </div>

          {!selectedNode && (
            <div className="inspector-empty">
              Click any node on the workflow.
            </div>
          )}

          {selectedNode && (
            <div className="inspector-body">
              <div className="inspector-title-row">
                <div className="inspector-icon">
                  {selectedNode.data.icon}
                </div>

                <div>
                  <strong>
                    {selectedNode.data.label}
                  </strong>

                  <div className="inspector-node-id">
                    ID: {selectedNode.id}
                  </div>
                </div>
              </div>

              <p className="inspector-description">
                {selectedNode.data.subtitle}
              </p>

              <div className="inspector-property">
                <span>Status</span>
                <strong>
                  {selectedNode.data.running
                    ? "RUNNING"
                    : selectedNode.data.statusLabel ||
                      "Ready"}
                </strong>
              </div>

              <div className="inspector-property">
                <span>Position</span>
                <strong>
                  X {Math.round(selectedNode.position.x)}
                  {" · "}
                  Y {Math.round(selectedNode.position.y)}
                </strong>
              </div>

              {nodeExecution && (
                <>
                  <div className="inspector-property">
                    <span>Last Execution</span>
                    <strong>
                      {nodeExecution.status}
                    </strong>
                  </div>

                  <div className="inspector-property">
                    <span>Duration</span>
                    <strong>
                      {nodeExecution.duration_seconds ??
                        "--"}{" "}
                      sec
                    </strong>
                  </div>
                </>
              )}

              {selectedNode.data.executable && (
                <button
                  className="primary-button inspector-button"
                  onClick={() =>
                    runNode(selectedNode.id)
                  }
                >
                  ▶ Execute Node
                </button>
              )}

              <button
                className="danger-button inspector-button"
                onClick={deleteSelectedNode}
              >
                Delete Node
              </button>
            </div>
          )}
        </aside>
      </section>
    </div>
  );
}

export default App;