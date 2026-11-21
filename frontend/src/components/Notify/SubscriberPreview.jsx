import { useState } from 'react';
import { CheckSquare, Square, ChevronDown, ChevronUp, AlertTriangle, Sparkles, FileText } from 'lucide-react';
import VoicePlayer from './VoicePlayer';

function maskPhoneNumber(phone) {
  if (!phone || phone.trim() === '') return '—';
  const clean = phone.trim();
  if (clean.length <= 6) return clean;
  const start = clean.slice(0, 5);
  const end = clean.slice(-2);
  return `${start}••••${end}`;
}

export default function SubscriberPreview({
  previews = [],
  selectedIds = new Set(),
  onToggleSelect,
  onSelectAll,
  onDeselectAll,
}) {
  const [expandedId, setExpandedId] = useState(null);

  const eligibleCount = previews.filter(p => p.eligible !== false && p.phone).length;
  const allSelected = eligibleCount > 0 && selectedIds.size === eligibleCount;

  return (
    <div className="space-y-2">
      {/* Header with selection controls */}
      <div className="flex items-center justify-between px-1">
        <div className="text-xs font-semibold text-slate-300">
          Target Subscribers ({selectedIds.size}/{previews.length} selected)
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={allSelected ? onDeselectAll : onSelectAll}
            className="text-xs font-medium text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            {allSelected ? 'Deselect All' : 'Select All Eligible'}
          </button>
        </div>
      </div>

      {/* Recipient Cards */}
      <div className="max-h-56 overflow-y-auto space-y-1.5 pr-1 border border-slate-800 rounded-lg bg-slate-950/60 p-2">
        {previews.length === 0 ? (
          <div className="text-xs text-slate-500 text-center py-4">
            No affected subscribers found for this incident.
          </div>
        ) : (
          previews.map((item) => {
            const isSelected = selectedIds.has(item.subscriber_id);
            const isEligible = item.eligible !== false && !!item.phone;
            const isExpanded = expandedId === item.subscriber_id;

            return (
              <div
                key={item.subscriber_id}
                className={`p-2 rounded-lg border transition-all text-xs ${
                  isSelected
                    ? 'bg-slate-900 border-slate-700'
                    : 'bg-slate-950 border-slate-900 opacity-75'
                }`}
              >
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={!isEligible}
                    onClick={() => onToggleSelect(item.subscriber_id)}
                    className="text-slate-400 hover:text-white disabled:opacity-40"
                  >
                    {isSelected ? (
                      <CheckSquare className="w-4 h-4 text-cyan-400" />
                    ) : (
                      <Square className="w-4 h-4 text-slate-600" />
                    )}
                  </button>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-semibold text-slate-200 truncate max-w-[140px]">
                        {item.subscriber_name || item.subscriber_id}
                      </span>
                      {item.village && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400">
                          {item.village}
                        </span>
                      )}
                      <span className="text-[10px] uppercase font-bold px-1 rounded bg-slate-800 text-slate-300">
                        {item.preferred_language || 'HI'}
                      </span>
                      {item.message_source === 'sarvam' ? (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-950 text-purple-300 border border-purple-800/40 flex items-center gap-1">
                          <Sparkles className="w-2.5 h-2.5 text-purple-400" /> Sarvam AI
                        </span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 flex items-center gap-1">
                          <FileText className="w-2.5 h-2.5 text-slate-400" /> Template
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500 mt-0.5">
                      Phone: <span className="font-mono text-slate-400">{maskPhoneNumber(item.phone)}</span>
                      {!isEligible && (
                        <span className="text-amber-500 ml-2 inline-flex items-center gap-0.5">
                          <AlertTriangle className="w-3 h-3" /> No phone on file
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <VoicePlayer text={item.message} language={item.preferred_language} />
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : item.subscriber_id)}
                      className="p-1 text-slate-400 hover:text-white"
                      title={isExpanded ? 'Hide message' : 'View message'}
                    >
                      {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-2 pt-2 border-t border-slate-800/80 text-slate-300 text-[11px] bg-slate-900/50 p-2 rounded">
                    <div className="text-[10px] text-slate-500 font-medium mb-1">Message Preview:</div>
                    <p className="leading-relaxed whitespace-pre-wrap">{item.message}</p>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
