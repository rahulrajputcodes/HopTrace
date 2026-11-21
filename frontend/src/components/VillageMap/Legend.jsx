import { NODE_TYPES_META, VILLAGE_STATUS_COLORS } from './theme';

/**
 * Map legend popover displaying node types, risk tiers, link styles,
 * village coverage health statuses, and incident blast radius markers.
 */
export default function Legend({ onClose }) {
  return (
    <aside
      aria-label="Map legend"
      className="absolute bottom-12 left-3 z-[1000] bg-[#0b172a]/95 backdrop-blur-sm border border-slate-700/80 rounded-xl shadow-2xl text-xs text-slate-300 w-72 max-h-[55vh] overflow-y-auto flex flex-col"
      onMouseDown={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-slate-700/60 bg-slate-800/50 shrink-0">
        <div className="flex items-center gap-1.5 font-semibold text-slate-200 text-xs">
          <span>🗺️</span>
          <span>Map Legend</span>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 text-xs px-2 py-0.5 rounded hover:bg-slate-700/50 transition-colors cursor-pointer"
            aria-label="Close legend"
          >
            ✕
          </button>
        )}
      </div>

      <div className="p-3 space-y-3">
        {/* Node Types */}
        <div>
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            Node Types
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {Object.entries(NODE_TYPES_META).map(([key, meta]) => (
              <div key={key} className="flex items-center gap-1.5">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: meta.color }}
                />
                <span className="text-xs text-slate-200">{meta.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Link Risk Scale */}
        <div>
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            Link Risk Scale
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#10b981] shrink-0" />
              <span className="text-xs text-slate-300">&lt; 40 Normal</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#f59e0b] shrink-0" />
              <span className="text-xs text-slate-300">40–59 Med</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#f97316] shrink-0" />
              <span className="text-xs text-slate-300">60–79 High</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-[#ef4444] shrink-0" />
              <span className="text-xs text-slate-300">≥ 80 Critical</span>
            </div>
          </div>
        </div>

        {/* Village Coverage Health */}
        <div>
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            AP Coverage & Village Health
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full border shrink-0 inline-block"
                style={{
                  borderColor: VILLAGE_STATUS_COLORS.healthy,
                  backgroundColor: `${VILLAGE_STATUS_COLORS.healthy}33`,
                }}
              />
              <span className="text-xs text-slate-300">Healthy village coverage</span>
            </div>
            <div className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full border shrink-0 inline-block"
                style={{
                  borderColor: VILLAGE_STATUS_COLORS.degraded,
                  backgroundColor: `${VILLAGE_STATUS_COLORS.degraded}33`,
                }}
              />
              <span className="text-xs text-slate-300">Degraded village coverage</span>
            </div>
            <div className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full border shrink-0 inline-block"
                style={{
                  borderColor: VILLAGE_STATUS_COLORS.critical,
                  backgroundColor: `${VILLAGE_STATUS_COLORS.critical}33`,
                }}
              />
              <span className="text-xs text-slate-300">Critical village coverage</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full border border-dashed border-red-500 bg-red-500/40 shrink-0 inline-block" />
              <span className="text-xs text-slate-300">Blast radius AP (affected users)</span>
            </div>
          </div>
        </div>

        {/* Links & Overlays */}
        <div>
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            Links & Incidents
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="w-4 h-0.5 bg-emerald-400 inline-block" />
              <span className="text-xs text-slate-300">Healthy link (solid)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-4 h-0.5 border-t border-dashed border-red-500 inline-block" />
              <span className="text-xs text-slate-300">Dashed: Packet loss / down</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full border-2 border-red-500 inline-block shrink-0" />
              <span className="text-xs text-slate-300">Pulsing: Suspected root cause</span>
            </div>
          </div>
        </div>

        {/* Notice */}
        <div className="pt-2 border-t border-slate-700/50 space-y-1 text-xs text-slate-400 leading-tight">
          <div>Village health status updates on dashboard refresh.</div>
          <div className="text-slate-500">Illustrative placement, not surveyed.</div>
        </div>
      </div>
    </aside>
  );
}
