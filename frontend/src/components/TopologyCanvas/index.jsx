import { useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  MiniMap,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import useStore from '../../store/appStore';

const POSITIONS = {
  GW1: { x: 40,  y: 310 },
  R1:  { x: 200, y: 310 },
  WB1: { x: 370, y: 120 },
  WB2: { x: 520, y: 120 },
  AP1: { x: 670, y: 60  },
  AP2: { x: 670, y: 190 },
  WB3: { x: 370, y: 310 },
  WB4: { x: 520, y: 310 },
  AP3: { x: 670, y: 265 },
  AP4: { x: 670, y: 370 },
  R2:  { x: 520, y: 200 },
  WB5: { x: 370, y: 490 },
  WB6: { x: 520, y: 490 },
  AP5: { x: 670, y: 445 },
  AP6: { x: 670, y: 545 },
};

const NODE_TYPES_META = {
  gateway:         { color: '#8b5cf6', bg: '#2e1065', icon: '🌐', label: 'Gateway' },
  router:          { color: '#3b82f6', bg: '#1e3a8a', icon: '🔄', label: 'Router'  },
  wireless_bridge: { color: '#f59e0b', bg: '#451a03', icon: '📡', label: 'Bridge'  },
  access_point:    { color: '#10b981', bg: '#022c22', icon: '📶', label: 'AP'      },
};

const VILLAGE_COLORS = {
  Rampur:    '#3b82f6',
  Bhatpur:   '#10b981',
  Daulatpur: '#f59e0b',
};

function riskColor(score) {
  if (score >= 80) return '#ef4444';
  if (score >= 60) return '#f97316';
  if (score >= 40) return '#f59e0b';
  return '#10b981';
}

function NetworkNode({ data }) {
  const meta = NODE_TYPES_META[data.nodeType] || NODE_TYPES_META.access_point;
  const isSuspected = data.isSuspected;
  const vColor = VILLAGE_COLORS[data.village] || '#64748b';

  return (
    <div className="relative flex flex-col items-center" style={{ width: 72 }}>
      {isSuspected && (
        <div
          className="absolute rounded-xl animate-ping opacity-40"
          style={{ background: '#ef4444', inset: '-4px' }}
        />
      )}
      <div
        className="relative flex flex-col items-center gap-0.5 px-2 py-2 rounded-xl border-2 cursor-pointer transition-transform hover:scale-105"
        style={{
          background: meta.bg,
          borderColor: isSuspected ? '#ef4444' : meta.color,
          boxShadow: `0 0 12px ${isSuspected ? '#ef444455' : meta.color + '44'}`,
          minWidth: 64,
        }}
      >
        <span className="text-lg leading-none">{meta.icon}</span>
        <span className="text-white text-[10px] font-bold leading-tight text-center">{data.label}</span>
        <span
          className={`w-2 h-2 rounded-full ${
            data.status === 'healthy' ? 'bg-emerald-400' :
            data.status === 'degraded' ? 'bg-amber-400 animate-pulse' :
            'bg-red-500 animate-pulse'
          }`}
        />
      </div>
      {data.village && (
        <div
          className="mt-0.5 px-1.5 py-px rounded text-[8px] font-semibold"
          style={{ background: vColor + '22', color: vColor, border: `1px solid ${vColor}44` }}
        >
          {data.village}
        </div>
      )}
    </div>
  );
}

const nodeTypes = { networkNode: NetworkNode };

export default function TopologyCanvas() {
  const topology = useStore(s => s.topology);
  const riskSnapshot = useStore(s => s.riskSnapshot);
  const liveMeasurements = useStore(s => s.liveMeasurements);
  const activeIncident = useStore(s => s.activeIncident);
  const setSelectedElement = useStore(s => s.setSelectedElement);

  const suspectedId = activeIncident?.suspected_component_id;

  const rfNodes = useMemo(() => (topology.nodes || []).map(node => ({
    id: node.id,
    type: 'networkNode',
    position: POSITIONS[node.id] || { x: 400, y: 300 },
    data: {
      label: node.id,
      nodeType: node.type,
      status: node.status || 'healthy',
      village: node.village,
      isSuspected: suspectedId === node.id,
    },
    style: { background: 'transparent', border: 'none', padding: 0 },
  })), [topology.nodes, suspectedId]);

  const rfEdges = useMemo(() => {
    const liveMap = {};
    (liveMeasurements || []).forEach(m => { liveMap[m.link_id] = m; });

    return (topology.links || []).map(link => {
      const risk = riskSnapshot[link.id]?.risk_score ?? liveMap[link.id]?.risk_score ?? 0;
      const live = liveMap[link.id];
      const isSuspected = suspectedId === link.id;
      const color = isSuspected ? '#ef4444' : riskColor(risk);
      const strokeWidth = isSuspected ? 4 : Math.max(1.5, 1.5 + risk / 40);
      const isDown = live?.connectivity_ok === false;

      let label = '';
      if (live) {
        label = `${(live.latency_ms || 0).toFixed(0)}ms · ${(live.packet_loss_pct || 0).toFixed(0)}%`;
      } else if (link.latency_ms !== undefined) {
        label = `${link.latency_ms}ms`;
      }

      return {
        id: link.id,
        source: link.source,
        target: link.target,
        label,
        labelStyle: { fill: color, fontSize: 9, fontWeight: 600 },
        labelBgStyle: { fill: '#050d1a', fillOpacity: 0.85 },
        labelBgPadding: [3, 4],
        labelBgBorderRadius: 4,
        style: { stroke: color, strokeWidth, strokeDasharray: isDown ? '6 3' : undefined },
        animated: !isDown && risk < 60,
        markerEnd: { type: MarkerType.ArrowClosed, color },
        data: { ...link, risk_score: risk, data_source: live?.data_source || 'simulated' },
      };
    });
  }, [topology.links, riskSnapshot, liveMeasurements, suspectedId]);

  const [, , onNodesChange] = useNodesState(rfNodes);
  const [, , onEdgesChange] = useEdgesState(rfEdges);

  const onNodeClick = useCallback((_, node) => {
    setSelectedElement({ type: 'node', id: node.id, data: node.data });
  }, [setSelectedElement]);

  const onEdgeClick = useCallback((_, edge) => {
    setSelectedElement({ type: 'edge', id: edge.id, data: edge.data });
  }, [setSelectedElement]);

  return (
    <div className="w-full h-full rounded-xl overflow-hidden bg-[#050d1a] relative">
      {/* Legend */}
      <div className="absolute top-2 left-2 z-10 flex flex-col gap-1 bg-[#0a1628]/90 rounded-lg p-2 border border-slate-800 pointer-events-none">
        {Object.entries(NODE_TYPES_META).map(([type, m]) => (
          <div key={type} className="flex items-center gap-1.5 text-[9px] text-slate-400">
            <span className="text-xs">{m.icon}</span>
            <span>{m.label}</span>
          </div>
        ))}
        <div className="border-t border-slate-700 mt-1 pt-1 space-y-0.5">
          <div className="text-[9px] text-slate-500 font-medium uppercase">Risk</div>
          {[['Low','#10b981'],['Med','#f59e0b'],['High','#f97316'],['Crit','#ef4444']].map(([l,c]) => (
            <div key={l} className="flex items-center gap-1.5 text-[9px] text-slate-400">
              <span className="w-4 h-0.5 rounded" style={{ background: c }} />
              <span>{l}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Source badge */}
      <div className="absolute top-2 right-12 z-10 px-2 py-1 bg-[#0a1628]/90 rounded-lg border border-slate-700 text-[10px] text-slate-400 pointer-events-none flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${(liveMeasurements || []).some(m => m.data_source === 'live') || topology.data_source === 'live' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
        <span>{topology.nodes?.length ?? 0} nodes · {topology.links?.length ?? 0} links · {(liveMeasurements || []).some(m => m.data_source === 'live') || topology.data_source === 'live' ? 'live' : (topology.data_source || 'simulated')}</span>
      </div>

      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15, maxZoom: 1.2 }}
        minZoom={0.3}
        maxZoom={2.5}
        proOptions={{ hideAttribution: true }}
        style={{ background: '#050d1a' }}
      >
        <Background color="#1e293b" gap={24} size={1} />
        <Controls
          style={{ background: '#0a1628', border: '1px solid #334155', borderRadius: '8px' }}
          showInteractive={false}
        />
        <MiniMap
          style={{ background: '#0a1628', border: '1px solid #334155' }}
          nodeColor={n => NODE_TYPES_META[n.data?.nodeType]?.color || '#64748b'}
          maskColor="#050d1a88"
        />
      </ReactFlow>
    </div>
  );
}
