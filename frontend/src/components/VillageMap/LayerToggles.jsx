import { LABEL_MIN_ZOOM } from './layerPrefs.js';

/**
 * Floating layer visibility controls for VillageMap.
 * Allows toggling AP coverage circles, network links, and node labels.
 */
export default function LayerToggles({
  layers,
  onChange,
  currentZoom = 12,
}) {
  const handleToggle = (key) => {
    onChange({
      ...layers,
      [key]: !layers[key],
    });
  };

  const labelsActive = layers.labels && currentZoom >= LABEL_MIN_ZOOM;

  return (
    <aside
      aria-label="Map layer controls"
      className="absolute top-14 right-3 z-[1000] bg-[#0b172a]/95 backdrop-blur-sm border border-slate-700/70 rounded-md shadow-xl text-xs text-slate-300 px-3 py-2"
    >
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider hidden sm:inline">
          Layers
        </span>

        {/* Coverage Toggle */}
        <label className="flex items-center gap-1.5 cursor-pointer hover:text-slate-100 select-none">
          <input
            type="checkbox"
            checked={layers.coverage}
            onChange={() => handleToggle('coverage')}
            className="w-3.5 h-3.5 rounded border-slate-600 text-sky-500 bg-slate-800 focus:ring-1 focus:ring-sky-400 cursor-pointer"
          />
          <span className="text-xs">Coverage</span>
        </label>

        {/* Links Toggle */}
        <label className="flex items-center gap-1.5 cursor-pointer hover:text-slate-100 select-none">
          <input
            type="checkbox"
            checked={layers.links}
            onChange={() => handleToggle('links')}
            className="w-3.5 h-3.5 rounded border-slate-600 text-sky-500 bg-slate-800 focus:ring-1 focus:ring-sky-400 cursor-pointer"
          />
          <span className="text-xs">Links</span>
        </label>

        {/* Labels Toggle */}
        <label
          className="flex items-center gap-1.5 cursor-pointer hover:text-slate-100 select-none"
          title={
            currentZoom >= LABEL_MIN_ZOOM
              ? 'Node labels visible'
              : `Zoom in to level ${LABEL_MIN_ZOOM}+ to view labels (current: ${currentZoom})`
          }
        >
          <input
            type="checkbox"
            checked={layers.labels}
            onChange={() => handleToggle('labels')}
            className="w-3.5 h-3.5 rounded border-slate-600 text-sky-500 bg-slate-800 focus:ring-1 focus:ring-sky-400 cursor-pointer"
          />
          <span
            className={`text-xs ${
              labelsActive ? 'text-sky-300 font-medium' : 'text-slate-400'
            }`}
          >
            Labels
            <span className="text-xs text-slate-500 ml-1">
              (≥{LABEL_MIN_ZOOM})
            </span>
          </span>
        </label>
      </div>
    </aside>
  );
}
