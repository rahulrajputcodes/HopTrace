import { useEffect, useRef } from 'react';
import useStore from '../store/appStore';

export function useLiveTelemetry() {
  const setWsConnected = useStore((s) => s.setWsConnected);
  const setLiveTelemetry = useStore((s) => s.setLiveTelemetry);
  const setRiskSnapshot = useStore((s) => s.setRiskSnapshot);
  const addToast = useStore((s) => s.addToast);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const watchdogTimer = useRef(null);
  const attempts = useRef(0);

  useEffect(() => {
    let alive = true;

    function resetWatchdog() {
      clearTimeout(watchdogTimer.current);
      // If no message arrives within 35 seconds, trigger a reconnect
      watchdogTimer.current = setTimeout(() => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          console.warn('[WS] Telemetry heartbeat timeout (35s) — reconnecting');
          wsRef.current.close();
        }
      }, 35000);
    }

    function connect() {
      if (!alive) return;
      try {
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${proto}://${window.location.host}/ws/telemetry`);
        wsRef.current = ws;

        ws.onopen = () => {
          attempts.current = 0;
          setWsConnected(true);
          resetWatchdog();
        };

        ws.onmessage = (evt) => {
          resetWatchdog();
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
          clearTimeout(watchdogTimer.current);
          if (!alive) return;
          // Exponential backoff with jitter: 1s, 1.5s, 2.25s ... capped at 15s
          const delay = Math.min(1000 * Math.pow(1.5, attempts.current), 15000) + Math.random() * 300;
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
      clearTimeout(watchdogTimer.current);
      if (wsRef.current) wsRef.current.close();
      setWsConnected(false);
    };
  }, [setWsConnected, setLiveTelemetry, setRiskSnapshot, addToast]);
}
