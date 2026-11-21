import { useEffect, useRef } from 'react';
import useStore from '../store/appStore';

export function useLiveTelemetry() {
  const setWsConnected = useStore(s => s.setWsConnected);
  const setLiveTelemetry = useStore(s => s.setLiveTelemetry);
  const setRiskSnapshot = useStore(s => s.setRiskSnapshot);
  const addToast = useStore(s => s.addToast);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const attempts = useRef(0);

  useEffect(() => {
    let alive = true;

    function connect() {
      if (!alive) return;
      try {
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${proto}://${window.location.host}/ws/telemetry`);
        wsRef.current = ws;

        ws.onopen = () => {
          attempts.current = 0;
          setWsConnected(true);
        };

        ws.onmessage = (evt) => {
          try {
            const msg = JSON.parse(evt.data);
            if (msg.type === 'telemetry_batch') {
              setLiveTelemetry(msg);
              if (msg.measurements) {
                setRiskSnapshot(msg.measurements);
              }
            } else if (msg.type === 'connected') {
              if (msg.risk_snapshot) {
                setRiskSnapshot(msg.risk_snapshot);
              }
            }
          } catch (e) {
            console.warn('[WS] parse error', e);
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          if (!alive) return;
          const delay = Math.min(3000 * Math.pow(1.5, attempts.current), 30000);
          attempts.current += 1;
          reconnectTimer.current = setTimeout(connect, delay);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch (e) {
        console.warn('[WS] connect error', e);
      }
    }

    connect();

    return () => {
      alive = false;
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
      setWsConnected(false);
    };
  }, [setWsConnected, setLiveTelemetry, setRiskSnapshot, addToast]);
}
