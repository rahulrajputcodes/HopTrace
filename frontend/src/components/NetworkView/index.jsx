import { useState, useRef } from 'react';
import VillageMap from '../VillageMap';
import TopologyCanvas from '../TopologyCanvas';
import { getViewPref, setViewPref } from './viewPref';

export default function NetworkView() {
  const [view, setView] = useState(getViewPref);
  const mapRef = useRef(null);
  const graphRef = useRef(null);

  const handleViewChange = (newView) => {
    setView(newView);
    setViewPref(newView);
  };

  const handleKeyDown = (e) => {
    let nextView = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextView = view === 'map' ? 'graph' : 'map';
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextView = view === 'graph' ? 'map' : 'graph';
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextView = 'map';
    } else if (e.key === 'End') {
      e.preventDefault();
      nextView = 'graph';
    }

    if (nextView && nextView !== view) {
      handleViewChange(nextView);
      if (nextView === 'map') {
        mapRef.current?.focus();
      } else {
        graphRef.current?.focus();
      }
    }
  };

  return (
    <div className="w-full h-full flex flex-col relative">
      {/* View Toggle Bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#081220] border-b border-slate-800/80 shrink-0 select-none">
        <div
          role="radiogroup"
          aria-label="Network visualization view"
          onKeyDown={handleKeyDown}
          className="inline-flex rounded-lg bg-slate-900/90 p-0.5 border border-slate-800"
        >
          <button
            ref={mapRef}
            type="button"
            role="radio"
            tabIndex={view === 'map' ? 0 : -1}
            aria-checked={view === 'map'}
            onClick={() => handleViewChange('map')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-all flex items-center gap-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 ${
              view === 'map'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <span aria-hidden="true">🗺️</span>
            <span>Map</span>
          </button>
          <button
            ref={graphRef}
            type="button"
            role="radio"
            tabIndex={view === 'graph' ? 0 : -1}
            aria-checked={view === 'graph'}
            onClick={() => handleViewChange('graph')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-all flex items-center gap-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 ${
              view === 'graph'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <span aria-hidden="true">🕸️</span>
            <span>Graph</span>
          </button>
        </div>
        <div className="text-[11px] text-slate-400 hidden sm:block">
          {view === 'map' ? 'Geographic layout' : 'Schematic topology'}
        </div>
      </div>

      {/* Active View Container */}
      <div className="flex-1 min-h-0 relative">
        {view === 'map' ? <VillageMap /> : <TopologyCanvas />}
      </div>
    </div>
  );
}
