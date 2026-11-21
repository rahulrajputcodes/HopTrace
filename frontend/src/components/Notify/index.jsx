import { useState, useEffect, useCallback } from 'react';
import {
  Bell,
  RefreshCw,
  Send,
  History,
  Sparkles,
  FileText,
  AlertTriangle,
  CheckCircle,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import useStore from '../../store/appStore';
import {
  fetchNotificationPreview,
  sendNotifications,
  fetchNotificationHistory,
  retryNotifications,
  fetchNotificationStatus,
} from './notifyApi';
import ChannelSelector from './ChannelSelector';
import SubscriberPreview from './SubscriberPreview';
import SendConfirmDialog from './SendConfirmDialog';
import DeliveryStatus from './DeliveryStatus';
import NotificationHistory from './NotificationHistory';

export default function NotifyPanel({ incident }) {

  const addToast = useStore((s) => s.addToast);
  const userRole = useStore((s) => s.userRole) || 'operator';
  const isViewer = userRole === 'viewer';

  // Component state
  const [activeTab, setActiveTab] = useState('dispatch'); // 'dispatch' | 'history' | 'status'
  const [channel, setChannel] = useState('sms');
  const [kind, setKind] = useState('outage'); // 'outage' | 'restored'
  const [useTranslation, setUseTranslation] = useState(false);

  // Previews & subscribers
  const [previews, setPreviews] = useState([]);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState(null);

  // Status & Provider info
  const [providerStatus, setProviderStatus] = useState(null);

  // History & Deliveries
  const [historyBatches, setHistoryBatches] = useState([]);
  const [latestDeliveryBatch, setLatestDeliveryBatch] = useState(null);
  const [isSending, setIsSending] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  // Confirmation Modal
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [activeIdempotencyKey, setActiveIdempotencyKey] = useState('');

  // Fetch provider status once
  useEffect(() => {
    fetchNotificationStatus()
      .then(setProviderStatus)
      .catch(() => null);
  }, []);

  // Load preview data
  useEffect(() => {
    if (!incident?.id) return;
    let active = true;

    fetchNotificationPreview(incident.id, {
      channel,
      kind,
      translate: useTranslation,
    })
      .then((res) => {
        if (!active) return;
        const items = res.previews || [];
        setPreviews(items);
        const eligible = items.filter((p) => p.eligible !== false && p.phone).map((p) => p.subscriber_id);
        setSelectedIds(new Set(eligible));
        setPreviewError(null);
      })
      .catch((err) => {
        if (!active) return;
        setPreviewError(err.message || 'Failed to load subscriber preview');
      })
      .finally(() => {
        if (active) setLoadingPreview(false);
      });

    return () => {
      active = false;
    };
  }, [incident, channel, kind, useTranslation]);

  // Load history data
  useEffect(() => {
    if (!incident?.id) return;
    let active = true;

    fetchNotificationHistory(incident.id)
      .then((res) => {
        if (active) setHistoryBatches(res.batches || []);
      })
      .catch((err) => {
        console.warn('Failed to load notification history:', err);
      });

    return () => {
      active = false;
    };
  }, [incident]);

  const refreshPreview = useCallback(() => {
    if (!incident?.id) return;
    setLoadingPreview(true);
    setPreviewError(null);
    fetchNotificationPreview(incident.id, { channel, kind, translate: useTranslation })
      .then((res) => {
        const items = res.previews || [];
        setPreviews(items);
        const eligible = items.filter((p) => p.eligible !== false && p.phone).map((p) => p.subscriber_id);
        setSelectedIds(new Set(eligible));
      })
      .catch((err) => setPreviewError(err.message || 'Failed to load subscriber preview'))
      .finally(() => setLoadingPreview(false));
  }, [incident, channel, kind, useTranslation]);

  const refreshHistory = useCallback(() => {
    if (!incident?.id) return;
    fetchNotificationHistory(incident.id)
      .then((res) => setHistoryBatches(res.batches || []))
      .catch((err) => console.warn('Failed to refresh history:', err));
  }, [incident]);

  // Selection handlers
  const handleToggleSelect = (subId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(subId)) next.delete(subId);
      else next.add(subId);
      return next;
    });
  };

  const handleSelectAll = () => {
    const eligible = previews.filter((p) => p.eligible !== false && p.phone).map((p) => p.subscriber_id);
    setSelectedIds(new Set(eligible));
  };

  const handleDeselectAll = () => {
    setSelectedIds(new Set());
  };

  // Dispatch confirmation
  const handleOpenConfirm = () => {
    if (selectedIds.size === 0) {
      addToast('Please select at least one eligible subscriber', 'warning');
      return;
    }
    // Set unique idempotency key for this send attempt
    setActiveIdempotencyKey(`ht-notify-${incident.id}-${Date.now()}`);
    setIsConfirmOpen(true);
  };

  // Perform dispatch
  const handleConfirmSend = async () => {
    setIsSending(true);
    try {
      const payload = {
        channel,
        kind,
        translate: useTranslation,
        subscriber_ids: Array.from(selectedIds),
      };

      const res = await sendNotifications(incident.id, payload, activeIdempotencyKey);
      setIsConfirmOpen(false);
      setLatestDeliveryBatch(res);
      setActiveTab('status');

      if (res.deduplicated) {
        addToast('Notification request deduplicated via idempotency key', 'info');
      } else {
        addToast(
          `Dispatched ${res.sent_count} notifications (${res.failed_count} failed)`,
          res.failed_count === 0 ? 'success' : 'warning'
        );
      }
      refreshHistory();
    } catch (err) {
      addToast(`Dispatch failed: ${err.message}`, 'error');
    } finally {
      setIsSending(false);
    }
  };

  // Retry handler
  const handleRetry = async (batchId) => {
    setIsRetrying(true);
    try {
      const res = await retryNotifications(incident.id, { batch_id: batchId });
      addToast(`Retried ${res.length} deliveries`, 'success');
      refreshHistory();
      if (latestDeliveryBatch) {
        // Update local latest view if matching
        setLatestDeliveryBatch((prev) => {
          if (!prev) return prev;
          const updatedMap = new Map(res.map((r) => [r.subscriber_id, r]));
          const nextDeliveries = prev.deliveries.map((d) => updatedMap.get(d.subscriber_id) || d);
          return { ...prev, deliveries: nextDeliveries };
        });
      }
    } catch (err) {
      addToast(`Retry error: ${err.message}`, 'error');
    } finally {
      setIsRetrying(false);
    }
  };

  const isRestored = incident?.status === 'closed' || incident?.status === 'restored';
  const sampleMsg = previews.length > 0 ? previews[0].message : '';

  return (
    <div className="bg-[#091424] border border-slate-800 rounded-xl overflow-hidden mt-3 shadow-xl">
      {/* Panel Header */}
      <div className="px-4 py-3 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-cyan-950/60 border border-cyan-800/40 text-cyan-400">
            <Bell className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-white tracking-wide">
                SUBSCRIBER NOTIFICATIONS
              </span>
              <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-slate-800 text-slate-300">
                {incident?.id || '—'}
              </span>
            </div>
            <div className="text-[11px] text-slate-400">
              Personalized outage alerts & multi-language subscriber delivery
            </div>
          </div>
        </div>

        {/* Tab buttons & Refresh */}
        <div className="flex items-center gap-1.5">
          {providerStatus && (
            <span
              className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${
                providerStatus.provider === 'twilio'
                  ? 'bg-emerald-950/60 border-emerald-700/50 text-emerald-300'
                  : 'bg-cyan-950/60 border-cyan-800/50 text-cyan-300'
              }`}
              title={
                providerStatus.provider === 'twilio'
                  ? `Twilio Provider (Allowlist: ${providerStatus.real_send_allowlist_count} numbers)`
                  : 'Console / Sandbox Provider'
              }
            >
              {providerStatus.provider === 'twilio' ? 'Live (Twilio)' : 'Sandbox Mode'}
            </span>
          )}

          <div className="inline-flex rounded-lg bg-slate-950 p-0.5 border border-slate-800 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab('dispatch')}
              className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${
                activeTab === 'dispatch'
                  ? 'bg-cyan-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Dispatch
            </button>
            {latestDeliveryBatch && (
              <button
                type="button"
                onClick={() => setActiveTab('status')}
                className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${
                  activeTab === 'status'
                    ? 'bg-cyan-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Status
              </button>
            )}
            <button
              type="button"
              onClick={() => setActiveTab('history')}
              className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${
                activeTab === 'history'
                  ? 'bg-cyan-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              History ({historyBatches.length})
            </button>
          </div>

          <button
            type="button"
            onClick={activeTab === 'history' ? refreshHistory : refreshPreview}
            disabled={loadingPreview}
            title="Refresh"
            className="p-1.5 rounded-lg border border-slate-800 bg-slate-950 text-slate-400 hover:text-white disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingPreview ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Body */}
      <div className="p-3.5 space-y-3">
        {/* DISPATCH TAB */}
        {activeTab === 'dispatch' && (
          <>
            {/* Options bar */}
            <div className="flex items-center justify-between flex-wrap gap-2 p-2 rounded-lg bg-slate-950/70 border border-slate-800/80">
              <ChannelSelector channel={channel} onChange={setChannel} disabled={isSending} />

              {/* Notification Kind (Outage vs Restored) */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-slate-400 font-medium">Kind:</span>
                <div className="inline-flex rounded-lg bg-slate-900 border border-slate-800 p-0.5">
                  <button
                    type="button"
                    onClick={() => setKind('outage')}
                    className={`px-2 py-0.5 text-xs font-semibold rounded ${
                      kind === 'outage'
                        ? 'bg-amber-600 text-white'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Outage Alert
                  </button>
                  <button
                    type="button"
                    onClick={() => setKind('restored')}
                    className={`px-2 py-0.5 text-xs font-semibold rounded ${
                      kind === 'restored'
                        ? 'bg-emerald-600 text-white'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Restoration
                  </button>
                </div>
              </div>

              {/* Sarvam AI Translation Toggle */}
              <button
                type="button"
                onClick={() => setUseTranslation(!useTranslation)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 border transition-colors ${
                  useTranslation
                    ? 'bg-purple-950/80 border-purple-700 text-purple-300'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-300'
                }`}
                title={
                  useTranslation
                    ? 'Using Sarvam AI translation with deterministic fallback'
                    : 'Using fast deterministic templates'
                }
              >
                {useTranslation ? (
                  <>
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    Sarvam AI Active
                  </>
                ) : (
                  <>
                    <FileText className="w-3.5 h-3.5 text-slate-400" />
                    Template Default
                  </>
                )}
              </button>
            </div>

            {/* Error banner if preview failed */}
            {previewError && (
              <div className="p-2.5 rounded-lg bg-red-950/40 border border-red-800 text-red-300 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
                <span>{previewError}</span>
              </div>
            )}

            {/* Subscriber Preview Table */}
            <SubscriberPreview
              previews={previews}
              selectedIds={selectedIds}
              onToggleSelect={handleToggleSelect}
              onSelectAll={handleSelectAll}
              onDeselectAll={handleDeselectAll}
            />

            {/* Restoration status prompt if incident is resolved */}
            {isRestored && kind !== 'restored' && (
              <div className="p-2 bg-emerald-950/30 border border-emerald-800/40 rounded-lg flex items-center justify-between text-xs">
                <span className="text-emerald-300 flex items-center gap-1.5">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  Network incident verified healthy. Ready to dispatch restoration notice?
                </span>
                <button
                  type="button"
                  onClick={() => setKind('restored')}
                  className="px-2 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white font-semibold text-[11px]"
                >
                  Switch to Restoration
                </button>
              </div>
            )}

            {/* Dispatch Action Button */}
            <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
              <div className="text-[11px] text-slate-400">
                {isViewer ? (
                  <span className="text-amber-400 flex items-center gap-1">
                    <ShieldAlert className="w-3.5 h-3.5" /> Viewer mode: read-only access
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-slate-400">
                    <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" /> Two-step explicit confirmation required
                  </span>
                )}
              </div>

              <button
                type="button"
                onClick={handleOpenConfirm}
                disabled={selectedIds.size === 0 || isSending || isViewer}
                title={isViewer ? 'Viewer role cannot dispatch notifications' : 'Prepare and confirm dispatch'}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-2 shadow-lg"
              >
                <Send className="w-3.5 h-3.5" />
                {isViewer
                  ? 'Dispatch (Viewer Restricted)'
                  : `Prepare Dispatch (${selectedIds.size})`}
              </button>
            </div>
          </>
        )}

        {/* STATUS TAB */}
        {activeTab === 'status' && latestDeliveryBatch && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <div className="font-semibold text-slate-200">
                Dispatch Batch: <span className="font-mono text-cyan-400">{latestDeliveryBatch.batch_id}</span>
              </div>
              <button
                type="button"
                onClick={() => setActiveTab('dispatch')}
                className="text-cyan-400 hover:text-cyan-300 text-xs font-medium"
              >
                ← Back to Dispatch
              </button>
            </div>
            <DeliveryStatus
              deliveries={latestDeliveryBatch.deliveries || []}
              onRetry={handleRetry}
              isRetrying={isRetrying}
              batchId={latestDeliveryBatch.batch_id}
            />
          </div>
        )}

        {/* HISTORY TAB */}
        {activeTab === 'history' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                <History className="w-4 h-4 text-cyan-400" /> Dispatch History
              </div>
              <span className="text-slate-400 text-[11px]">
                {historyBatches.length} past batch(es)
              </span>
            </div>
            <NotificationHistory
              batches={historyBatches}
              onRetry={handleRetry}
              isRetrying={isRetrying}
            />
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      <SendConfirmDialog
        isOpen={isConfirmOpen}
        onClose={() => setIsConfirmOpen(false)}
        onConfirm={handleConfirmSend}
        channel={channel}
        kind={kind}
        recipientCount={selectedIds.size}
        sampleMessage={sampleMsg}
        provider={providerStatus?.provider || 'console'}
        incidentId={incident?.id || '—'}
        isSending={isSending}
      />
    </div>
  );
}
