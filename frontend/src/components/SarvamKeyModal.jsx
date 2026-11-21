import { useState } from 'react';
import useStore from '../store/appStore';

const SPEAKERS = ['meera', 'arvind', 'arjun'];
const LANG_OPTIONS = [
  { code: 'hi', label: 'हिंदी', speaker: 'meera' },
  { code: 'en', label: 'English', speaker: 'meera' },
  { code: 'ta', label: 'தமிழ்', speaker: 'arjun' },
  { code: 'mr', label: 'मराठी', speaker: 'meera' },
  { code: 'te', label: 'తెలుగు', speaker: 'arjun' },
  { code: 'kn', label: 'ಕನ್ನಡ', speaker: 'meera' },
  { code: 'bn', label: 'বাংলা', speaker: 'arjun' },
];

export default function SarvamKeyModal({ onClose }) {
  const sarvamApiKey = useStore(s => s.sarvamApiKey);
  const setSarvamKey = useStore(s => s.setSarvamKey);
  const sarvamLanguage = useStore(s => s.sarvamLanguage);
  const setSarvamLanguage = useStore(s => s.setSarvamLanguage);
  const sarvamSpeaker = useStore(s => s.sarvamSpeaker);
  const setSarvamSpeaker = useStore(s => s.setSarvamSpeaker);
  const addToast = useStore(s => s.addToast);

  const [tempKey, setTempKey] = useState(sarvamApiKey);
  const [testing, setTesting] = useState(false);

  const handleSave = () => {
    setSarvamKey(tempKey.trim());
    addToast('Sarvam AI key saved', 'success');
    onClose();
  };

  const handleTest = async () => {
    if (!tempKey.trim()) { addToast('Enter an API key first', 'warning'); return; }
    setTesting(true);
    try {
      const res = await fetch('/api/v1/explanations/audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: 'नमस्ते', language_code: 'hi-IN', speaker: 'meera', api_key: tempKey.trim() }),
      });
      if (res.ok) addToast('✓ Sarvam AI connection verified!', 'success');
      else addToast('Key may be invalid — check Sarvam dashboard', 'warning');
    } catch (e) {
      addToast(`Test failed: ${e.message}`, 'error');
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-[#0d1829] border border-slate-700 rounded-2xl p-6 w-full max-w-md shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-white font-bold text-lg">Sarvam AI Configuration</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl leading-none">✕</button>
        </div>

        <label className="block text-xs text-slate-400 mb-1 font-medium">API Key</label>
        <div className="flex gap-2 mb-4">
          <input
            type="password"
            value={tempKey}
            onChange={e => setTempKey(e.target.value)}
            placeholder="sk-xxxxxxxx..."
            className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
          />
          <button
            onClick={handleTest}
            disabled={testing}
            className="px-3 py-2 bg-purple-700 hover:bg-purple-600 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
          >
            {testing ? '...' : 'Test'}
          </button>
        </div>

        <label className="block text-xs text-slate-400 mb-1 font-medium">Language</label>
        <div className="grid grid-cols-4 gap-1.5 mb-4">
          {LANG_OPTIONS.map(l => (
            <button
              key={l.code}
              onClick={() => { setSarvamLanguage(l.code); setSarvamSpeaker(l.speaker); }}
              className={`px-2 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                sarvamLanguage === l.code
                  ? 'bg-purple-700 border-purple-500 text-white'
                  : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-500'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>

        <label className="block text-xs text-slate-400 mb-1 font-medium">Speaker Voice</label>
        <div className="flex gap-2 mb-6">
          {SPEAKERS.map(s => (
            <button
              key={s}
              onClick={() => setSarvamSpeaker(s)}
              className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors capitalize ${
                sarvamSpeaker === s
                  ? 'bg-purple-700 border-purple-500 text-white'
                  : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-500'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-lg border border-slate-600 transition-colors">Cancel</button>
          <button onClick={handleSave} className="flex-1 py-2 bg-purple-700 hover:bg-purple-600 text-white text-sm rounded-lg transition-colors font-medium">Save</button>
        </div>
      </div>
    </div>
  );
}
