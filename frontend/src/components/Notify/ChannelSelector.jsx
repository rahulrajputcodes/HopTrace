import { MessageSquare, PhoneCall } from 'lucide-react';

export default function ChannelSelector({ channel, onChange, disabled }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-slate-400">Channel:</span>
      <div className="inline-flex rounded-lg bg-slate-900 border border-slate-800 p-0.5">
        <button
          type="button"
          onClick={() => onChange('sms')}
          disabled={disabled}
          className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
            channel === 'sms'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          SMS
        </button>
        <button
          type="button"
          onClick={() => onChange('whatsapp')}
          disabled={disabled}
          className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
            channel === 'whatsapp'
              ? 'bg-emerald-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <PhoneCall className="w-3.5 h-3.5" />
          WhatsApp
        </button>
      </div>
    </div>
  );
}
