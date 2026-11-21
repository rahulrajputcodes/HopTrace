import { useState } from 'react';
import { NODE_TYPES_META, VILLAGE_STATUS_COLORS } from './theme';

/**
 * Collapsible map legend displaying node types, risk tiers, link styles,
 * village coverage health statuses, and incident blast radius markers.
 * Theme tokens cited from TopologyCanvas (commit f46157e).
 */
export default function Legend() {
  const [isOpen, setIsOpen] = useState(() => {
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      return window.matchMedia('(min-width: 640px)').matches;
    }
    return true;
  });

  return (
    <aside
      aria-label="Map legend"
      className="absolute bottom-6 left-3 z-[1000] bg-[#0b172a]/95 backdrop-blur-sm border border-slate-700/70 rounded-md shadow-xl text-xs text-slate-300 w-64 max-h-[60vh] sm:max-h-[85vh] overflow-y-auto"
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700/60 bg-slate-800/40">
        <span className="font-semibold text-slate-200">Map Legend</span>
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className="text-slate-400 hover:text-slate-200 text-xs px-1.5 py-0.5 rounded hover:bg-slate-700/50 transition-colors"
          aria-expanded={isOpen}
          aria-label={isOpen ? 'Collapse legend' : 'Expand legend'}
        >
          {isOpen ? 'Hide ▲' : 'Show ▼'}
        </button>
      </div>

      {isOpen && (
        <div className="p-3 space-y-3">
          {/* Node Types */}
          <div>
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Node Types
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {Object.entries(NODE_TYPES_META).map(([key, meta]) => (
                <div key={key} className="flex items-center gap-1.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: meta.color }}
                  />
                  <span className="text-[11px] text-slate-200">{meta.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Link Risk Scale */}
          <div>
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Link Risk Scale
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#10b981] shrink-0" />
                <span className="text-[11px]">&lt; 40 Normal</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#f59e0b] shrink-0" />
                <span className="text-[11px]">40–59 Med</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#f97316] shrink-0" />
                <span className="text-[11px]">60–79 High</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-[#ef4444] shrink-0" />
                <span className="text-[11px]">≥ 80 Critical</span>
              </div>
            </div>
          </div>

          {/* Village Coverage Health */}
          <div>
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
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
                <span className="text-[11px]">Healthy village coverage</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full border shrink-0 inline-block"
                  style={{
                    borderColor: VILLAGE_STATUS_COLORS.degraded,
                    backgroundColor: `${VILLAGE_STATUS_COLORS.degraded}33`,
                  }}
                />
                <span className="text-[11px]">Degraded village coverage</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full border shrink-0 inline-block"
                  style={{
                    borderColor: VILLAGE_STATUS_COLORS.critical,
                    backgroundColor: `${VILLAGE_STATUS_COLORS.critical}33`,
                  }}
                />
                <span className="text-[11px]">Critical village coverage</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full border border-dashed border-red-500 bg-red-500/40 shrink-0 inline-block" />
                <span className="text-[11px]">Blast radius AP (affected users)</span>
              </div>
            </div>
          </div>

          {/* Links & Overlays */}
          <div>
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
              Links & Incidents
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-4 h-0.5 bg-emerald-400 inline-block" />
                <span className="text-[11px]">Healthy link (solid)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-0.5 border-t border-dashed border-red-500 inline-block" />
                <span className="text-[11px]">Dashed: Packet loss / down</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full border-2 border-red-500 inline-block shrink-0" />
                <span className="text-[11px]">Pulsing: Suspected root cause</span>
              </div>
            </div>
          </div>

          {/* Notice */}
          <div className="pt-2 border-t border-slate-700/50 space-y-1 text-[10px] text-slate-400 leading-tight">
            <div>Village health status updates on dashboard refresh.</div>
            <div className="text-slate-500">Illustrative placement, not surveyed.</div>
          </div>
        </div>
      )}
    </aside>
  );
}
