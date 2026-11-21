import { useEffect } from 'react';
import { useMap } from 'react-leaflet';

/**
 * Initializes custom Leaflet panes with explicit stacking order:
 * coverage (400) < links (450) < nodes (500) < incident ring (550) < tooltips (600).
 * Pointer events on incident rings and tooltips are disabled so they never intercept clicks.
 */
export default function MapPanes() {
  const map = useMap();

  useEffect(() => {
    if (!map) return;

    if (!map.getPane('coveragePane')) {
      const pane = map.createPane('coveragePane');
      pane.style.zIndex = '400';
    }

    if (!map.getPane('linksPane')) {
      const pane = map.createPane('linksPane');
      pane.style.zIndex = '450';
    }

    if (!map.getPane('nodesPane')) {
      const pane = map.createPane('nodesPane');
      pane.style.zIndex = '500';
    }

    if (!map.getPane('incidentRingPane')) {
      const pane = map.createPane('incidentRingPane');
      pane.style.zIndex = '550';
      pane.style.pointerEvents = 'none';
    }

    if (!map.getPane('tooltipsPane')) {
      const pane = map.createPane('tooltipsPane');
      pane.style.zIndex = '600';
      pane.style.pointerEvents = 'none';
    }
  }, [map]);

  return null;
}
