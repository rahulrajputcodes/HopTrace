import { useState, useRef } from 'react';
import useStore from '../../store/appStore';
import { useApi } from '../../hooks/useApi';

const LANG_OPTIONS = [
  { code: 'hi', label: 'हिंदी',   speaker: 'meera' },
  { code: 'en', label: 'English', speaker: 'meera' },
  { code: 'ta', label: 'தமிழ்',   speaker: 'arjun' },
  { code: 'mr', label: 'मराठी',   speaker: 'meera' },
  { code: 'te', label: 'తెలుగు',  speaker: 'arjun' },
  { code: 'kn', label: 'ಕನ್ನಡ',   speaker: 'meera' },
  { code: 'bn', label: 'বাংলা',   speaker: 'arjun' },
];

function WaveformBars({ playing }) {
  const heights = [3, 5, 8, 5, 3, 7, 4, 6, 3, 5];
  return (
    <div className={`flex items-end gap-0.5 h-5 ${playing ? '' : 'opacity-30'}`}>
      {heights.map((h, i) => (
        <span
          key={i}
          className="w-0.5 rounded-full bg-purple-400 transition-all"
          style={{
            height: playing ? `${h * 2}px` : '4px',
            animation: playing ? `wave ${0.5 + i * 0.07}s ease-in-out ${i * 0.04}s infinite alternate` : 'none',
          }}
        />
      ))}
      <style>{`@keyframes wave { from { transform: scaleY(0.3); } to { transform: scaleY(1.5); } }`}</style>
    </div>
  );
}

export default function AIExplanationCard() {
  const aiReport = useStore(s => s.aiReport);
  const aiLoading = useStore(s => s.aiLoading);
  const activeIncident = useStore(s => s.activeIncident);
  const sarvamLanguage = useStore(s => s.sarvamLanguage);
  const setSarvamLanguage = useStore(s => s.setSarvamLanguage);
  const sarvamApiKey = useStore(s => s.sarvamApiKey);
  const sarvamSpeaker = useStore(s => s.sarvamSpeaker);
  const isPlayingAudio = useStore(s => s.isPlayingAudio);
  const setIsPlayingAudio = useStore(s => s.setIsPlayingAudio);
  const addToast = useStore(s => s.addToast);
  const { explainIncident, synthesizeAudio } = useApi();

  const audioRef = useRef(null);

  if (!aiReport && !aiLoading) return null;

  const isObj = typeof aiReport === 'object' && aiReport !== null;

  const handleLanguageChange = (code) => {
    setSarvamLanguage(code);
    if (activeIncident?.id) {
      explainIncident(activeIncident.id, code, sarvamApiKey);
    }
  };

  const fallback = (text) => {
    if (!window.speechSynthesis) { setIsPlayingAudio(false); return; }
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = sarvamLanguage === 'en' ? 'en-IN' : 'hi-IN';
    utt.rate = 0.92;
    utt.onend = () => setIsPlayingAudio(false);
    utt.onerror = () => setIsPlayingAudio(false);
    window.speechSynthesis.speak(utt);
    addToast('Playing via device TTS', 'info');
  };

  const handleVoice = async () => {
    if (isPlayingAudio) {
      audioRef.current?.pause();
      audioRef.current = null;
      window.speechSynthesis?.cancel();
      setIsPlayingAudio(false);
      return;
    }
    const text = isObj
      ? (aiReport.executive_summary || aiReport.subscriber_impact_brief || '')
      : String(aiReport || '');
    if (!text) return;

    setIsPlayingAudio(true);
    const langCode = sarvamLanguage === 'en' ? 'en-IN' : `${sarvamLanguage}-IN`;
    const speaker = LANG_OPTIONS.find(l => l.code === sarvamLanguage)?.speaker || sarvamSpeaker;

    try {
      const b64 = await synthesizeAudio(text.slice(0, 500), langCode, speaker, sarvamApiKey);
      if (b64) {
        const snd = new Audio(`data:audio/mp3;base64,${b64}`);
        audioRef.current = snd;
        snd.onended = () => { setIsPlayingAudio(false); audioRef.current = null; };
        snd.onerror = () => fallback(text);
        await snd.play();
        addToast(`Playing Sarvam voice (${speaker})`, 'success');
        return;
      }
    } catch (_) {}
    fallback(text);
  };

  return (
    <div className="bg-[#0a1628] border border-purple-800/50 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-purple-800/40 bg-purple-950/20 flex-wrap">
        <span className="text-purple-400">🤖</span>
        <span className="text-white font-semibold text-sm">Sarvam AI Analysis</span>
        <div className="flex-1"/>
        <div className="flex items-center gap-0.5 bg-slate-900 rounded-lg p-0.5 border border-slate-700">
          {LANG_OPTIONS.map(l => (
            <button
              key={l.code}
              onClick={() => handleLanguageChange(l.code)}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                sarvamLanguage === l.code ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-3 max-h-[420px] overflow-y-auto">
        {aiLoading ? (
          <div className="flex items-center gap-3 py-8 justify-center">
            <span className="w-5 h-5 border-2 border-purple-400/30 border-t-purple-400 rounded-full animate-spin"/>
            <span className="text-slate-400 text-sm">Generating analysis via Sarvam AI 105B...</span>
          </div>
        ) : isObj ? (
          <>
            {aiReport.executive_summary && (
              <div>
                <div className="text-[10px] text-purple-400 font-medium uppercase mb-1">Executive Summary</div>
                <p className="text-slate-200 text-sm leading-relaxed">{aiReport.executive_summary}</p>
              </div>
            )}
            {aiReport.technical_diagnosis && (
              <div>
                <div className="text-[10px] text-blue-400 font-medium uppercase mb-1">Technical Diagnosis</div>
                <pre className="text-slate-300 text-xs font-mono bg-slate-900 p-3 rounded-lg whitespace-pre-wrap leading-relaxed">{aiReport.technical_diagnosis}</pre>
              </div>
            )}
            {aiReport.field_operator_steps && (
              <div>
                <div className="text-[10px] text-amber-400 font-medium uppercase mb-1">Field Operator Steps</div>
                <ol className="space-y-1.5">
                  {(Array.isArray(aiReport.field_operator_steps)
                    ? aiReport.field_operator_steps
                    : [aiReport.field_operator_steps]
                  ).map((step, i) => (
                    <li key={i} className="flex gap-2 text-xs text-slate-300">
                      <span className="shrink-0 w-5 h-5 rounded-full bg-amber-900 text-amber-300 flex items-center justify-center text-[10px] font-bold">
                        {i + 1}
                      </span>
                      <span className="leading-relaxed">{step}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
            {aiReport.subscriber_impact_brief && (
              <div>
                <div className="text-[10px] text-emerald-400 font-medium uppercase mb-1">Subscriber Impact Brief</div>
                <div className="bg-emerald-950/30 border border-emerald-800/40 rounded-xl p-3">
                  <div className="text-[10px] text-emerald-600 mb-1">📱 WhatsApp-style brief</div>
                  <p className="text-emerald-100 text-xs leading-relaxed">{aiReport.subscriber_impact_brief}</p>
                </div>
              </div>
            )}
            <div className="flex items-center gap-3 flex-wrap">
              {aiReport.escalation_required !== undefined && (
                <div className={`px-3 py-1.5 rounded-lg border text-xs font-semibold ${
                  aiReport.escalation_required
                    ? 'bg-red-950 border-red-700 text-red-300'
                    : 'bg-emerald-950 border-emerald-700 text-emerald-300'
                }`}>
                  {aiReport.escalation_required ? '🔴 Escalation Required' : '✅ No Escalation'}
                </div>
              )}
              {aiReport.eta && (
                <div className="px-3 py-1.5 bg-blue-950 border border-blue-700 rounded-lg text-xs font-semibold text-blue-300">
                  ⏱ ETA: {aiReport.eta}
                </div>
              )}
            </div>
          </>
        ) : (
          <pre className="text-slate-300 text-xs whitespace-pre-wrap leading-relaxed">{String(aiReport)}</pre>
        )}
      </div>

      {/* Voice brief footer */}
      {aiReport && !aiLoading && (
        <div className="px-4 py-3 border-t border-purple-800/30 flex items-center gap-3">
          <button
            onClick={handleVoice}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors ${
              isPlayingAudio
                ? 'bg-purple-800 hover:bg-purple-700 text-purple-200'
                : 'bg-purple-700 hover:bg-purple-600 text-white'
            }`}
          >
            {isPlayingAudio ? '⏹ Stop' : '▶ Voice Brief'}
          </button>
          <WaveformBars playing={isPlayingAudio}/>
          <span className="text-[10px] text-slate-500 ml-auto">
            {LANG_OPTIONS.find(l => l.code === sarvamLanguage)?.speaker || 'meera'} · Sarvam Bulbul
          </span>
        </div>
      )}
    </div>
  );
}
