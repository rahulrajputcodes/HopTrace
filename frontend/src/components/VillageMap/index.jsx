import { useMemo, useState, useEffect, useRef, useCallback } from 'react';
import {
  MapContainer,
  TileLayer,
  ScaleControl,
  Circle,
  Polyline,
  Marker,
  Popup,
  Tooltip,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import useStore from '../../store/appStore';
import './leafletSetup';
import {
  computeBounds,
  parseGHz,
  fresnelF1Metres,
  clearance60,
  getLinkMidpoint,
  getPredictedEtaMinutes,
} from './geo';
import { telemetryLabel, riskColor, villageStatusColor } from './theme';
import { getLinkStrokeWidth, getLinkDashArray } from './risk';
import { buildMapModel } from './model';
import {
  createNodeIcon,
  createSuspectedRingIcon,
  createPredictionBadgeIcon,
  NODE_Z_INDEX,
} from './icons';
import { getStoredLayers, setStoredLayers, LABEL_MIN_ZOOM } from './layerPrefs';
import {
  getStoredPopoverPref,
  setStoredPopoverPref,
  STORAGE_KEY_MAP_LEGEND,
  STORAGE_KEY_MAP_VILLAGES,
} from './popoverPrefs';
import Legend from './Legend';
import MapPanes from './MapPanes';
import LayerToggles from './LayerToggles';
import VillageSummary from './VillageSummary';

const ERROR_TILE_URL =
  'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';

/**
 * Resizes the Leaflet map whenever its DOM container dimensions change.
 */
function MapResizer() {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    if (!container || typeof ResizeObserver === 'undefined') return;

    const observer = new ResizeObserver(() => {
      map.invalidateSize();
    });

    observer.observe(container);
    return () => {
      observer.disconnect();
    };
  }, [map]);

  return null;
}

/**
 * Fits the map view to the provided bounds once when coordinates become available,
 * without overriding manual pan/zoom on subsequent renders.
 */
function FitBoundsOnce({ bounds }) {
  const map = useMap();
  const hasFittedRef = useRef(false);

  useEffect(() => {
    if (bounds && !hasFittedRef.current) {
      hasFittedRef.current = true;
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
    }
  }, [bounds, map]);

  return null;
}

/**
 * Tracks current Leaflet map zoom level and informs parent state.
 */
function ZoomTracker({ onZoomChange }) {
  const map = useMap();

  useEffect(() => {
    const handleZoom = () => {
      onZoomChange(map.getZoom());
    };
    map.on('zoomend', handleZoom);
    return () => {
      map.off('zoomend', handleZoom);
    };
  }, [map, onZoomChange]);

  return null;
}

export default function VillageMap() {
  const topology = useStore((s) => s.topology);
  const villages = useStore((s) => s.villages);
  const riskSnapshot = useStore((s) => s.riskSnapshot);
  const liveMeasurements = useStore((s) => s.liveMeasurements);
  const activeIncident = useStore((s) => s.activeIncident);
  const affectedSubscribers = useStore((s) => s.affectedSubscribers);
  const setSelectedElement = useStore((s) => s.setSelectedElement);

  const model = useMemo(
    () =>
      buildMapModel({
        topology,
        villages,
        riskSnapshot,
        liveMeasurements,
        activeIncident,
        affectedSubscribers,
      }),
    [
      topology,
      villages,
      riskSnapshot,
      liveMeasurements,
      activeIncident,
      affectedSubscribers,
    ]
  );

  const bounds = useMemo(() => computeBounds(topology?.nodes), [topology?.nodes]);
  const dataSource = topology?.data_source ?? 'unknown';

  const [isOffline, setIsOffline] = useState(false);
  const [layers, setLayers] = useState(() => getStoredLayers());
  const [currentZoom, setCurrentZoom] = useState(12);
  const [legendOpen, setLegendOpen] = useState(() =>
    getStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, false)
  );
  const [villagesOpen, setVillagesOpen] = useState(() =>
    getStoredPopoverPref(STORAGE_KEY_MAP_VILLAGES, false)
  );
  const tileLayerRef = useRef(null);

  const toggleLegend = useCallback(() => {
    setLegendOpen((prev) => {
      const next = !prev;
      setStoredPopoverPref(STORAGE_KEY_MAP_LEGEND, next);
      return next;
    });
  }, []);

  const toggleVillages = useCallback(() => {
    setVillagesOpen((prev) => {
      const next = !prev;
      setStoredPopoverPref(STORAGE_KEY_MAP_VILLAGES, next);
      return next;
    });
  }, []);

  const handleLayersChange = useCallback((newLayers) => {
    setLayers(newLayers);
    setStoredLayers(newLayers);
  }, []);

  const handleZoomChange = useCallback((z) => {
    setCurrentZoom(z);
  }, []);

  useEffect(() => {
    const handleOffline = () => setIsOffline(true);
    const handleOnline = () => {
      setIsOffline(false);
      tileLayerRef.current?.redraw();
    };
    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);
    return () => {
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, []);

  if (dataSource === 'loading') {
    return (
      <div className="relative isolate w-full h-full min-h-[520px] bg-[#050d1a] flex flex-col items-center justify-center text-slate-400">
        <div className="w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full animate-spin mb-3" />
        <div className="text-sm font-medium">Loading topology…</div>
      </div>
    );
  }

  if (!bounds) {
    return (
      <div className="relative isolate w-full h-full min-h-[520px] bg-[#050d1a] flex flex-col items-center justify-center text-slate-400 p-6 text-center">
        <div className="text-3xl mb-2">🗺️</div>
        <div className="text-sm font-medium text-slate-200 mb-1">
          No geographic data from the backend
        </div>
        <div className="text-xs text-slate-500 max-w-sm">
          Topology is loaded, but no nodes have valid latitude and longitude coordinates.
        </div>
      </div>
    );
  }

  const defaultCenter = [
    (bounds[0][0] + bounds[1][0]) / 2,
    (bounds[0][1] + bounds[1][1]) / 2,
  ];

  const isAnyLive = dataSource === 'live' || model.links.some(l => l.live?.data_source === 'live');
  const label = isAnyLive ? 'Live telemetry' : telemetryLabel(dataSource);
  const activeSource = isAnyLive ? 'live' : dataSource;

  return (
    <div className="relative isolate w-full h-full min-h-[520px] bg-[#050d1a] overflow-hidden select-none">
      {/* Honesty Chip */}
      <div
        role="note"
        aria-label="Telemetry data source"
        className="absolute top-3 right-3 z-[1000] bg-slate-900/90 backdrop-blur-sm border border-slate-700/70 text-slate-300 text-xs px-2.5 py-1.5 rounded shadow pointer-events-none flex items-center gap-2 max-w-[calc(100%-1rem)] sm:max-w-max leading-tight"
      >
        <span className={`w-2 h-2 rounded-full shrink-0 ${isAnyLive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-400'}`} />
        <span>
          {label
            ? `${label} · illustrative placement · source: ${activeSource}`
            : `illustrative placement · source: ${activeSource}`}
        </span>
      </div>

      {/* Layer Toggles */}
      <LayerToggles
        layers={layers}
        onChange={handleLayersChange}
        currentZoom={currentZoom}
      />

      {/* Offline Status Chip */}
      {isOffline && (
        <div
          role="status"
          className="absolute top-20 left-3 z-[1000] bg-amber-950/90 backdrop-blur-sm border border-amber-600/70 text-amber-200 text-xs px-2.5 py-1.5 rounded shadow pointer-events-none flex items-center gap-1.5"
        >
          <span className="text-amber-400 font-bold">⚠</span>
          <span>Basemap offline: showing network only</span>
        </div>
      )}

      {/* Corner Toolbar Buttons: Legend & Villages (collapsed by default, remembering choice) */}
      <div
        className="absolute bottom-3 left-3 z-[1000] flex items-center gap-2"
        onMouseDown={(e) => e.stopPropagation()}
        onDoubleClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={toggleLegend}
          className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border shadow-md flex items-center gap-1.5 transition-colors cursor-pointer ${
            legendOpen
              ? 'bg-sky-600/90 text-white border-sky-400'
              : 'bg-[#0b172a]/90 text-slate-300 hover:text-white border-slate-700/80 hover:bg-slate-800'
          }`}
          aria-expanded={legendOpen}
          aria-label="Toggle map legend"
        >
          <span>🗺️</span>
          <span>Legend</span>
        </button>
        <button
          type="button"
          onClick={toggleVillages}
          className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border shadow-md flex items-center gap-1.5 transition-colors cursor-pointer ${
            villagesOpen
              ? 'bg-sky-600/90 text-white border-sky-400'
              : 'bg-[#0b172a]/90 text-slate-300 hover:text-white border-slate-700/80 hover:bg-slate-800'
          }`}
          aria-expanded={villagesOpen}
          aria-label="Toggle village summary"
        >
          <span>🏘️</span>
          <span>Villages</span>
        </button>
      </div>

      {/* Map Legend Popover */}
      {legendOpen && <Legend onClose={toggleLegend} />}

      <MapContainer
        center={defaultCenter}
        zoom={12}
        zoomControl={true}
        attributionControl={true}
        className="w-full h-full z-0"
        style={{ background: '#050d1a' }}
      >
        <MapPanes />
        <ZoomTracker onZoomChange={handleZoomChange} />
        <VillageSummary
          isOpen={villagesOpen}
          onClose={toggleVillages}
          legendOpen={legendOpen}
        />

        <TileLayer
          ref={tileLayerRef}
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          className="hoptrace-dark-tiles"
          maxZoom={19}
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          errorTileUrl={ERROR_TILE_URL}
          eventHandlers={{
            tileerror: () => setIsOffline(true),
            tileload: (e) => {
              const src = e?.tile?.src;
              if (src && src !== ERROR_TILE_URL) {
                setIsOffline(false);
              }
            },
          }}
        />

        <ScaleControl position="bottomright" imperial={false} />
        <MapResizer />
        <FitBoundsOnce bounds={bounds} />

        {/* Coverage Circles Layer */}
        {layers.coverage &&
          model.nodes
            .filter((node) => node.type === 'access_point')
            .map((node) => {
              const radius = node.coverage_radius_m || 800;
              const isBlast = node.isBlastAp;
              const vColor = villageStatusColor(node.villageStatus);
              return (
                <Circle
                  key={`coverage-${node.id}-${isBlast ? 'blast' : node.villageStatus}`}
                  center={[node.lat, node.lon]}
                  radius={radius}
                  pane="coveragePane"
                  interactive={false}
                  pathOptions={
                    isBlast
                      ? {
                          color: '#ef4444',
                          fillColor: '#ef4444',
                          fillOpacity: 0.28,
                          weight: 3,
                          dashArray: '4 4',
                        }
                      : {
                          color: vColor,
                          fillColor: vColor,
                          fillOpacity: 0.14,
                          weight: 1.5,
                        }
                  }
                />
              );
            })}

        {/* Links Layer */}
        {layers.links &&
          model.links.map((link) => {
            const p1 = [link.sourceNode.lat, link.sourceNode.lon];
            const p2 = [link.targetNode.lat, link.targetNode.lon];
            const strokeCol = link.isSuspected
              ? '#ef4444'
              : riskColor(link.risk_score);
            const strokeW = getLinkStrokeWidth(link.risk_score, link.isSuspected);
            const strokeDash = getLinkDashArray(link.live?.connectivity_ok);

            return (
              <Polyline
                key={`link-${link.id}-${link.isSuspected}-${link.isDown}-${Math.round(link.risk_score)}`}
                positions={[p1, p2]}
                pane="linksPane"
                pathOptions={{
                  color: strokeCol,
                  weight: strokeW,
                  dashArray: strokeDash,
                }}
                eventHandlers={{
                  click: () => {
                    setSelectedElement({
                      type: 'edge',
                      id: link.id,
                      data: {
                        id: link.id,
                        source: link.source,
                        target: link.target,
                        risk_score: link.risk_score,
                        distance_km: link.distance_km,
                        medium: link.medium,
                        frequency: link.frequency,
                        status: link.isDown ? 'down' : 'up',
                        data_source: link.live?.data_source || 'simulated',
                      },
                    });
                  },
                }}
              >
                <Popup className="hoptrace-popup">
                  <div className="space-y-1.5 text-xs text-slate-200">
                    <div className="flex items-center justify-between border-b border-slate-700/60 pb-1">
                      <span className="font-semibold text-white">Link: {link.id}</span>
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`px-1.5 py-0.5 rounded text-xs font-semibold ${
                            link.live?.data_source === 'live'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-700/60'
                              : 'bg-slate-800 text-slate-400 border border-slate-700'
                          }`}
                        >
                          {link.live?.data_source === 'live' ? '● Live' : '○ Simulated'}
                        </span>
                        <span
                          className="px-1.5 py-0.5 rounded text-xs font-medium"
                          style={{
                            backgroundColor: `${riskColor(link.risk_score)}22`,
                            color: riskColor(link.risk_score),
                          }}
                        >
                          Risk {link.risk_score}
                        </span>
                      </div>
                    </div>
                    <div className="text-xs text-slate-400">
                      {link.source} &rarr; {link.target}
                    </div>

                    {link.distance_km !== undefined && link.distance_km !== null && (
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Distance:</span>
                        <span className="font-mono">{link.distance_km} km</span>
                      </div>
                    )}
                    {link.medium && (
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-400">Medium:</span>
                        <span className="font-mono capitalize">
                          {link.medium.replace(/_/g, ' ')}
                        </span>
                      </div>
                    )}

                    {/* Fresnel Zone Section for Wireless PtP links */}
                    {link.medium === 'wireless_ptp' &&
                      Number.isFinite(link.distance_km) &&
                      (() => {
                        const band = parseGHz(link.frequency);
                        const f1 = band ? fresnelF1Metres(link.distance_km, band) : null;
                        const clearance = f1 !== null ? clearance60(f1) : null;

                        return (
                          <div className="pt-1.5 mt-1 border-t border-slate-700/60 text-xs space-y-1">
                            <div className="text-xs uppercase font-semibold text-sky-400 tracking-wider">
                              Fresnel Zone (Mid-Path)
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-400">Band:</span>
                              <span className="font-mono">
                                {band !== null ? `${band} GHz` : 'band unavailable'}
                              </span>
                            </div>
                            {f1 !== null && clearance !== null && (
                              <>
                                <div className="flex justify-between">
                                  <span className="text-slate-400">F1 Radius:</span>
                                  <span className="font-mono">{f1.toFixed(2)} m</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-slate-400">60% Clearance:</span>
                                  <span className="font-mono">{clearance.toFixed(2)} m</span>
                                </div>
                              </>
                            )}
                            <div className="text-xs text-slate-500 italic">
                              estimate, no terrain data
                            </div>
                          </div>
                        );
                      })()}

                    {link.live && (
                      <>
                        <div className="flex justify-between text-xs">
                          <span className="text-slate-400">Latency:</span>
                          <span className="font-mono">
                            {(link.live.latency_ms || 0).toFixed(1)} ms
                          </span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-slate-400">Packet Loss:</span>
                          <span className="font-mono">
                            {(link.live.packet_loss_pct || 0).toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-slate-400">Throughput:</span>
                          <span className="font-mono">
                            {(link.live.throughput_mbps || 0).toFixed(1)} Mbps
                          </span>
                        </div>
                      </>
                    )}
                    {link.isSuspected && (
                      <div className="pt-1 text-xs text-red-400 font-semibold flex items-center gap-1">
                        <span>⚠</span> Suspected root cause link
                      </div>
                    )}
                    <div className="pt-1 border-t border-slate-700/60 text-xs text-slate-400 flex items-center justify-between">
                      <span>{label || 'Telemetry'}</span>
                      <span className="capitalize">source: {link.live?.data_source || dataSource}</span>
                    </div>
                  </div>
                </Popup>
              </Polyline>
            );
          })}

        {/* Prediction Badges Layer */}
        {layers.links &&
          model.links.map((link) => {
            const eta = getPredictedEtaMinutes(link.live);
            if (eta === null) return null;
            const midpoint = getLinkMidpoint(link.sourceNode, link.targetNode);
            if (!midpoint) return null;

            const badgeIcon = createPredictionBadgeIcon(eta, L);
            return (
              <Marker
                key={`pred-${link.id}-${eta}`}
                position={midpoint}
                icon={badgeIcon}
                pane="incidentRingPane"
                interactive={false}
                zIndexOffset={1500}
              />
            );
          })}

        {/* Suspected Link Overlay */}
        {layers.links &&
          model.suspected?.type === 'link' &&
          (() => {
            const suspectedLink = model.links.find(
              (l) => l.id === model.suspected.id
            );
            if (!suspectedLink) return null;
            return (
              <Polyline
                key={`suspected-${suspectedLink.id}`}
                positions={[
                  [suspectedLink.sourceNode.lat, suspectedLink.sourceNode.lon],
                  [suspectedLink.targetNode.lat, suspectedLink.targetNode.lon],
                ]}
                pane="incidentRingPane"
                pathOptions={{
                  color: '#ef4444',
                  weight: 6,
                  className: 'hoptrace-suspected-link',
                }}
                interactive={false}
              />
            );
          })()}

        {/* Nodes Layer */}
        {model.nodes.map((node) => {
          const zIndex = node.isSuspected
            ? NODE_Z_INDEX.suspected
            : NODE_Z_INDEX[node.type] || 100;
          const icon = createNodeIcon(node, L);

          return (
            <Marker
              key={`node-${node.id}-${node.isSuspected}-${node.isBlastAp}`}
              position={[node.lat, node.lon]}
              icon={icon}
              pane="nodesPane"
              zIndexOffset={zIndex}
              title={`${node.id} (${node.label || node.id})`}
              alt={`${node.id} ${node.type}`}
              eventHandlers={{
                click: () => {
                  setSelectedElement({
                    type: 'node',
                    id: node.id,
                    data: {
                      id: node.id,
                      label: node.label || node.id,
                      nodeType: node.type,
                      status: node.status || 'healthy',
                      village: node.village,
                      isSuspected: node.isSuspected,
                    },
                  });
                },
              }}
            >
              <Popup className="hoptrace-popup">
                <div className="space-y-1.5 text-xs text-slate-200">
                  <div className="flex items-center justify-between border-b border-slate-700/60 pb-1">
                    <span className="font-semibold text-white">Node: {node.id}</span>
                    <span className="text-xs uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                      {node.type}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400">
                    Village:{' '}
                    <span className="text-slate-200 font-medium">
                      {node.village || 'None'}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400">
                    Village Status:{' '}
                    <span className="text-slate-200 font-medium capitalize">
                      {node.villageStatus || 'unknown'}
                    </span>
                  </div>
                  <div className="text-xs font-mono text-slate-400">
                    {node.lat.toFixed(5)}° N, {node.lon.toFixed(5)}° E
                  </div>
                  {node.isSuspected && (
                    <div className="pt-1 text-xs text-red-400 font-semibold flex items-center gap-1">
                      <span>⚠</span> Suspected root cause component
                    </div>
                  )}
                  {node.isBlastAp && (
                    <div className="pt-1 text-xs text-amber-400 font-medium flex items-center gap-1">
                      <span>⚡</span> Blast radius AP (affected subscribers)
                    </div>
                  )}
                  <div className="pt-1 border-t border-slate-700/60 text-xs text-slate-400">
                    {label || 'Telemetry'} · source: {dataSource}
                  </div>
                </div>
              </Popup>

              {layers.labels && currentZoom >= LABEL_MIN_ZOOM && (
                <Tooltip
                  permanent
                  direction="top"
                  offset={[0, -14]}
                  className="hoptrace-node-tooltip"
                  pane="tooltipsPane"
                >
                  {node.label || node.id}
                </Tooltip>
              )}
            </Marker>
          );
        })}

        {/* Suspected Node Ring Overlay */}
        {model.suspected?.type === 'node' &&
          (() => {
            const suspectedNode = model.nodes.find(
              (n) => n.id === model.suspected.id
            );
            if (!suspectedNode) return null;
            const ringIcon = createSuspectedRingIcon(L);
            return (
              <Marker
                key={`suspected-ring-${suspectedNode.id}`}
                position={[suspectedNode.lat, suspectedNode.lon]}
                icon={ringIcon}
                pane="incidentRingPane"
                interactive={false}
                zIndexOffset={2000}
              />
            );
          })()}
      </MapContainer>
    </div>
  );
}
