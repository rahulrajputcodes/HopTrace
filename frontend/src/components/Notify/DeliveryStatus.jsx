import { CheckCircle2, XCircle, RotateCcw, AlertTriangle, ShieldX } from 'lucide-react';
import useStore from '../../store/appStore';

function maskPhone(phone) {
  if (!phone) return '—';
  if (phone.length <= 6) return phone;
  return `${phone.slice(0, 5)}••••${phone.slice(-2)}`;
}

export default function DeliveryStatus({
  deliveries = [],
  onRetry,
  isRetrying,
  batchId,
}) {
  const userRole = useStore(s => s.userRole) || 'operator';
  const isViewer = userRole === 'viewer';

  const failedCount = deliveries.filter(d => d.status === 'failed').length;
  const sentCount = deliveries.filter(d => d.status === 'sent' || d.status === 'delivered').length;

  return (
    <div className="space-y-3">
      {/* Summary Header */}
      <div className="flex items-center justify-between bg-slate-900/60 border border-slate-800 p-2.5 rounded-lg text-xs">
        <div className="flex items-center gap-3">
          <span className="text-slate-400">
            Total: <strong className="text-white">{deliveries.length}</strong>
          </span>
          <span className="text-emerald-400 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" /> Sent: {sentCount}
          </span>
          {failedCount > 0 && (
            <span className="text-red-400 flex items-center gap-1">
              <XCircle className="w-3.5 h-3.5" /> Failed: {failedCount}
            </span>
          )}
        </div>

        {failedCount > 0 && (
          <button
            type="button"
            onClick={() => onRetry(batchId)}
            disabled={isRetrying || isViewer}
            title={isViewer ? 'Viewer role: Read-only access (cannot retry)' : 'Retry failed deliveries'}
            className="px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-semibold text-[11px] flex items-center gap-1 transition-colors"
          >
            {isRetrying ? (
              <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : isViewer ? (
              <ShieldX className="w-3 h-3" />
            ) : (
              <RotateCcw className="w-3 h-3" />
            )}
            {isViewer ? 'Retry (Disabled for Viewer)' : `Retry Failed (${failedCount})`}
          </button>
        )}
      </div>

      {/* Deliveries List */}
      <div className="max-h-60 overflow-y-auto border border-slate-800 rounded-lg bg-slate-950/80 divide-y divide-slate-800/60">
        {deliveries.length === 0 ? (
          <div className="text-xs text-slate-500 text-center py-4">
            No deliveries in this batch.
          </div>
        ) : (
          deliveries.map((deliv, idx) => {
            const isFailed = deliv.status === 'failed';
            return (
              <div key={deliv.id || idx} className="p-2.5 text-xs hover:bg-slate-900/40 transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-slate-200">
                        {deliv.subscriber_name || deliv.subscriber_id}
                      </span>
                      <span className="font-mono text-[10px] text-slate-500">
                        {maskPhone(deliv.recipient)}
                      </span>
                      <span className="text-[10px] px-1 rounded bg-slate-800 text-slate-400 uppercase font-bold">
                        {deliv.channel || 'sms'}
                      </span>
                      <span className="text-[10px] px-1 rounded bg-slate-800 text-slate-400">
                        {deliv.provider || 'console'}
                      </span>
                      {deliv.message_source === 'sarvam' && (
                        <span className="text-[10px] px-1 rounded bg-purple-950 text-purple-400 border border-purple-800/40">
                          Sarvam
                        </span>
                      )}
                    </div>

                    <p className="text-slate-400 text-[11px] mt-1 line-clamp-2">
                      {deliv.message}
                    </p>

                    {isFailed && deliv.error && (
                      <div className="text-red-400 text-[10px] mt-1 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 shrink-0" />
                        <span>Error: {deliv.error}</span>
                      </div>
                    )}
                  </div>

                  <div className="shrink-0 text-right">
                    <span
                      className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${
                        isFailed
                          ? 'bg-red-950 text-red-400 border-red-800/60'
                          : 'bg-emerald-950 text-emerald-400 border-emerald-800/60'
                      }`}
                    >
                      {isFailed ? <XCircle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                      {deliv.status}
                    </span>
                    {deliv.updated_at && (
                      <div className="text-[10px] text-slate-500 mt-1">
                        {new Date(deliv.updated_at).toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
