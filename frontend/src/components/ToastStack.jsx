import useStore from '../store/appStore';

const COLORS = {
  info:    'border-blue-600 bg-blue-950 text-blue-200',
  success: 'border-emerald-600 bg-emerald-950 text-emerald-200',
  warning: 'border-amber-600 bg-amber-950 text-amber-200',
  error:   'border-red-600 bg-red-950 text-red-200',
};
const ICONS = { info: 'ℹ', success: '✓', warning: '⚠', error: '✕' };

export default function ToastStack() {
  const toasts = useStore(s => s.toasts);

  if (!toasts.length) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-xs">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`flex items-start gap-2 px-4 py-3 rounded-xl border text-sm shadow-2xl animate-in slide-in-from-right-4 fade-in ${COLORS[t.type] || COLORS.info}`}
        >
          <span className="text-base leading-none mt-0.5">{ICONS[t.type] || 'ℹ'}</span>
          <span className="leading-snug">{t.msg}</span>
        </div>
      ))}
    </div>
  );
}
