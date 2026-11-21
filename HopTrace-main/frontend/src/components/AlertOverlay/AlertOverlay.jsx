import { useEffect, useState, useRef, useCallback, useSyncExternalStore } from 'react';
import { appStore } from '../../store/appStore';
import { parseFaultClass, buildHindiSpeechText, playHindiAlertAudio } from './alertVoice';
import './AlertOverlay.css';

export default function AlertOverlay() {
  const state = useSyncExternalStore(appStore.subscribe, appStore.getSnapshot);
  const { isArmed, isMuted, alertOpen, activeIncident, affectedSubscribers } = state;

  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isCollapsing, setIsCollapsing] = useState(false);
  const cardRef = useRef(null);

  const faultClass = parseFaultClass(activeIncident?.summary || '');
  const componentId = activeIncident?.suspected_component_id || 'Unknown Component';
  const confidence = Math.round((activeIncident?.confidence_score || 0.9) * 100);
  const subscriberCount = affectedSubscribers?.length || 0;
  const topSubscribers = (affectedSubscribers || []).slice(0, 3).map((s) => s.display_name || s.id);

  const hindiText = buildHindiSpeechText(faultClass, componentId, subscriberCount);

  // Collapse and scroll smoothly to the incident panel
  const handleDismiss = useCallback(() => {
    setIsCollapsing(true);
    setTimeout(() => {
      appStore.dismissAlert();
      setIsCollapsing(false);

      const panel = document.querySelector('.incident-card-body') || document.querySelector('.incident-banner');
      if (panel) {
        panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 320);
  }, []);

  // Voice playback & auto-dismiss timer on alert activation
  useEffect(() => {
    if (!alertOpen || !activeIncident) {
      return;
    }

    const startTime = Date.now();

    // Play Hindi voice alert
    playHindiAlertAudio({
      incidentId: activeIncident.id,
      text: hindiText,
      isMuted,
      getCachedAudio: appStore.getCachedAudio,
      setCachedAudio: appStore.setCachedAudio,
    });

    // Elapsed seconds ticker based on elapsed delta
    const timer = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    // Auto-collapse after ~8 seconds
    const autoDismiss = setTimeout(() => {
      handleDismiss();
    }, 8500);

    return () => {
      clearInterval(timer);
      clearTimeout(autoDismiss);
    };
  }, [alertOpen, activeIncident, hindiText, isMuted, handleDismiss]);

  // Accessibility: Focus management and Escape key dismissal
  useEffect(() => {
    if (!alertOpen) return;

    if (cardRef.current) {
      cardRef.current.focus();
    }

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        handleDismiss();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [alertOpen, handleDismiss]);

  const handleManualReplay = () => {
    playHindiAlertAudio({
      incidentId: activeIncident?.id,
      text: hindiText,
      isMuted: false,
      getCachedAudio: appStore.getCachedAudio,
      setCachedAudio: appStore.setCachedAudio,
    });
  };

  return (
    <>
      {/* TopBar-adjacent Arm Demo & Mute Controls */}
      <aside className="alert-demo-bar" aria-label="Demo Voice Controls">
        <button
          type="button"
          className={`demo-chip ${isArmed ? 'armed' : ''}`}
          onClick={() => appStore.armDemo()}
          title="Arm audio for immediate playback on fault"
        >
          <span>{isArmed ? '● Armed' : '○ Arm Audio Demo'}</span>
        </button>
        <button
          type="button"
          className="demo-chip"
          onClick={() => appStore.toggleMute()}
          title="Toggle Voice Mute"
        >
          <span>{isMuted ? '🔇 Muted' : '🔊 Voice On'}</span>
        </button>
        {activeIncident && !alertOpen && (
          <button
            type="button"
            className="demo-chip"
            onClick={() => appStore.reopenAlert()}
            title="Replay Alert Overlay"
          >
            <span>🚨 Replay Alert</span>
          </button>
        )}
      </aside>

      {/* Main Alert Dialog Overlay */}
      {alertOpen && activeIncident && (
        <div
          className="alert-overlay-root alert-overlay-pulse"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="alert-dialog-title"
          aria-describedby="alert-dialog-desc"
        >
          <div
            ref={cardRef}
            tabIndex={-1}
            className={`alert-card ${isCollapsing ? 'alert-card-collapsing' : ''}`}
          >
            <div className="alert-card-header">
              <span className="alert-tag-badge" id="alert-dialog-title">
                [{faultClass}] FAULT DETECTED
              </span>
              <span className="alert-timer">Active: {elapsedSeconds}s</span>
            </div>

            <div className="alert-card-grid">
              <div>
                <div className="alert-metric-label">Suspected Component</div>
                <div className="alert-metric-val">{componentId}</div>
              </div>
              <div>
                <div className="alert-metric-label">Confidence</div>
                <div className="alert-metric-val">{confidence}%</div>
              </div>
              <div>
                <div className="alert-metric-label">Affected Subscribers</div>
                <div className="alert-metric-val">{subscriberCount} Users</div>
              </div>
              <div>
                <div className="alert-metric-label">Impact Scope</div>
                <div className="alert-metric-val">{faultClass === 'CASCADE' ? 'Multi-Hop' : 'Localized'}</div>
              </div>
            </div>

            <div className="alert-voice-transcript" id="alert-dialog-desc">
              <strong>ध्वनि अलर्ट (Hindi Notice):</strong> {hindiText}
            </div>

            {topSubscribers.length > 0 && (
              <div className="alert-subscribers-list">
                <strong>Sample Affected:</strong> {topSubscribers.join(', ')}
                {subscriberCount > 3 ? ` and ${subscriberCount - 3} more` : ''}
              </div>
            )}

            {!isArmed && (
              <div style={{ fontSize: '11px', color: '#f59e0b' }}>
                💡 Tip: Click &quot;Arm Audio Demo&quot; at the top or &quot;Replay Voice&quot; if browser autoplay is restricted.
              </div>
            )}

            <div className="alert-card-actions">
              <button
                type="button"
                className="alert-btn alert-btn-secondary"
                onClick={handleManualReplay}
              >
                🔊 Replay Voice
              </button>
              <button
                type="button"
                className="alert-btn alert-btn-ack"
                onClick={handleDismiss}
              >
                Acknowledge (Dismiss)
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
