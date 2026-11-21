import { AlertCircle, ShieldAlert, X, Send } from 'lucide-react';

export default function SendConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  channel,
  kind,
  recipientCount,
  sampleMessage,
  provider,
  incidentId,
  isSending,
}) {
  if (!isOpen) return null;

  const isTwilio = provider === 'twilio';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
      <div className="bg-[#0b172b] border border-slate-700 rounded-xl max-w-md w-full shadow-2xl p-5 space-y-4">
        {/* Title */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-amber-400" />
            <h3 className="text-sm font-bold text-white">
              Confirm Notification Dispatch
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSending}
            className="text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Dispatch Summary */}
        <div className="space-y-2 text-xs">
          <div className="grid grid-cols-2 gap-2 bg-slate-900/80 p-3 rounded-lg border border-slate-800">
            <div>
              <span className="text-slate-500 block text-[10px]">Incident</span>
              <span className="font-mono font-semibold text-slate-200">{incidentId}</span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px]">Notification Kind</span>
              <span className="font-semibold text-cyan-400 capitalize">{kind} Alert</span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px]">Target Channel</span>
              <span className="font-semibold text-white uppercase">{channel}</span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px]">Target Recipients</span>
              <span className="font-bold text-amber-300">{recipientCount} Subscribers</span>
            </div>
          </div>

          {/* Provider badge */}
          <div className="p-2.5 rounded-lg border flex items-start gap-2 bg-slate-900/60 border-slate-800">
            <AlertCircle className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
            <div className="text-[11px]">
              <span className="text-slate-300 font-medium">Delivery Provider: </span>
              <span className={`font-bold ${isTwilio ? 'text-emerald-400' : 'text-cyan-400'}`}>
                {isTwilio ? 'Twilio Live (Allowlist Enforced)' : 'Console / In-Memory Sandbox'}
              </span>
              <p className="text-slate-500 text-[10px] mt-0.5">
                {isTwilio
                  ? 'Numbers not on REAL_SEND_ALLOWLIST are routed safely through sandbox.'
                  : 'Safe simulation: messages are logged and recorded without carrier fees.'}
              </p>
            </div>
          </div>

          {/* Sample message preview */}
          {sampleMessage && (
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 block text-[10px] mb-1 font-medium">Message Sample:</span>
              <p className="text-slate-300 text-[11px] leading-relaxed line-clamp-3">
                {sampleMessage}
              </p>
            </div>
          )}

          <p className="text-[11px] text-amber-400/90 font-medium">
            ⚠ Outage notifications cannot be cancelled once dispatched. Ensure recipient list is verified.
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            disabled={isSending}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-300 hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSending || recipientCount === 0}
            className="px-4 py-1.5 rounded-lg text-xs font-bold bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white flex items-center gap-1.5 transition-colors shadow-md"
          >
            {isSending ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Dispatching...
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5" />
                Confirm & Send ({recipientCount})
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
