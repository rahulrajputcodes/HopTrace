import { useState } from 'react';
import { useMap } from 'react-leaflet';
import useStore from '../../store/appStore';
import { computeBounds } from './geo';
import { villageStatusColor } from './theme';

/**
 * Summary panel displaying village demographics, network health status,
 * AP counts, and registered subscriber counts.
 * Clicking a row flies the map to that village's node bounding box.
 */
export default function VillageSummary() {
  const map = useMap();
  const villages = useStore((s) => s.villages);
  const allSubscribers = useStore((s) => s.allSubscribers);
  const topology = useStore((s) => s.topology);

  const [isOpen, setIsOpen] = useState(() => {
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      return window.matchMedia('(min-width: 768px)').matches;
    }
    return true;
  });

  // Filter out non-village administrative sites (e.g. block_hq / GW1)
  const villageList = (villages || []).filter(
    (v) => v && v.village_id !== 'block_hq' && v.village_id !== 'gw1'
  );

  const handleRowClick = (v) => {
    if (!v) return;
    const vId = (v.village_id || '').toLowerCase();
    const vName = (v.name || '').toLowerCase();
    const vNodes = (topology?.nodes || []).filter((n) => {
      const nv = (n?.village || '').toLowerCase();
      return nv === vId || nv === vName;
    });

    const bounds = computeBounds(vNodes);
    if (bounds) {
      map.flyToBounds(bounds, { padding: [50, 50], maxZoom: 16, duration: 1.2 });
    }
  };

  return (
    <aside
      aria-label="Village network summary"
      className="absolute bottom-8 right-3 z-[1000] bg-[#0b172a]/95 backdrop-blur-sm border border-slate-700/70 rounded-md shadow-xl text-xs text-slate-300 w-80 max-w-[calc(100%-1.5rem)] max-h-[50vh] overflow-hidden flex flex-col"
      onMouseDown={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700/60 bg-slate-800/40 shrink-0">
        <span className="font-semibold text-slate-200">
          Villages ({villageList.length})
        </span>
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className="text-slate-400 hover:text-slate-200 text-xs px-1.5 py-0.5 rounded hover:bg-slate-700/50 transition-colors"
          aria-expanded={isOpen}
          aria-label={isOpen ? 'Collapse village summary' : 'Expand village summary'}
        >
          {isOpen ? 'Hide ▲' : 'Show ▼'}
        </button>
      </div>

      {isOpen && (
        <div className="p-2.5 overflow-y-auto space-y-2">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-700/60 text-[10px] text-slate-400 uppercase tracking-wider">
                <th className="pb-1.5 font-medium">Village</th>
                <th className="pb-1.5 font-medium">Pop.</th>
                <th className="pb-1.5 font-medium">Status</th>
                <th className="pb-1.5 font-medium text-right">APs</th>
                <th className="pb-1.5 font-medium text-right">Subs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {villageList.map((v) => {
                const status = v.status || 'unknown';
                const statusColor = villageStatusColor(status);
                const apCount = Array.isArray(v.access_points)
                  ? v.access_points.length
                  : 0;

                const apSet = new Set(v.access_points || []);
                const subCount = Array.isArray(allSubscribers)
                  ? allSubscribers.filter((s) => s && apSet.has(s.access_point_id))
                      .length
                  : 0;

                return (
                  <tr
                    key={v.village_id}
                    onClick={() => handleRowClick(v)}
                    className="hover:bg-slate-800/70 cursor-pointer transition-colors group"
                    title={`Click to fly map to ${v.name || v.village_id}`}
                  >
                    <td className="py-1.5 text-slate-200 font-medium group-hover:text-sky-300">
                      {v.name || v.village_id}
                    </td>
                    <td className="py-1.5 text-slate-400 font-mono text-[11px]">
                      {(v.population || 0).toLocaleString()}
                    </td>
                    <td className="py-1.5">
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ backgroundColor: statusColor }}
                        />
                        <span className="capitalize text-[11px] text-slate-300">
                          {status}
                        </span>
                      </span>
                    </td>
                    <td className="py-1.5 text-right font-mono text-slate-400 text-[11px]">
                      {apCount}
                    </td>
                    <td className="py-1.5 text-right font-mono text-slate-200 text-[11px]">
                      {subCount}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="pt-1.5 border-t border-slate-700/50 text-[10px] text-slate-400 leading-tight">
            Simulated demographic data · click row to fly
          </div>
        </div>
      )}
    </aside>
  );
}
