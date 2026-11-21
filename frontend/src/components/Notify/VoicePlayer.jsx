import { useState, useRef } from 'react';
import { Volume2, Loader2, AlertCircle } from 'lucide-react';
import { useApi } from '../../hooks/useApi';

export default function VoicePlayer({ text, language = 'hi' }) {
  const { synthesizeVoice } = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef(null);

  const handlePlayVoice = async () => {
    if (audioUrl) {
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
        audioRef.current.play();
        setIsPlaying(true);
      }
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await synthesizeVoice(text, language, 'meera');
      if (res && res.audio_base64) {
        const url = `data:${res.mime || 'audio/wav'};base64,${res.audio_base64}`;
        setAudioUrl(url);
        setIsPlaying(true);
      } else {
        setError('Voice synthesis unavailable');
      }
    } catch (err) {
      setError(err.message || 'Voice service offline');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="inline-flex items-center gap-1.5">
      {audioUrl && (
        <audio
          ref={audioRef}
          src={audioUrl}
          autoPlay
          onEnded={() => setIsPlaying(false)}
          onError={() => setIsPlaying(false)}
        />
      )}
      <button
        type="button"
        onClick={handlePlayVoice}
        disabled={loading || isPlaying}
        title={error ? `Voice unavailable: ${error}` : 'Listen to message voice audio'}
        className="p-1 rounded bg-purple-950/40 hover:bg-purple-900/60 border border-purple-800/40 text-purple-300 disabled:opacity-50 text-xs transition-colors flex items-center gap-1"
      >
        {loading ? (
          <Loader2 className="w-3 h-3 animate-spin text-purple-400" />
        ) : (
          <Volume2 className={`w-3 h-3 ${isPlaying ? 'text-emerald-400 animate-pulse' : 'text-purple-400'}`} />
        )}
        <span className="text-[10px]">{isPlaying ? 'Playing...' : 'Voice'}</span>
      </button>
      {error && (
        <span className="text-[10px] text-slate-500 flex items-center gap-0.5" title={error}>
          <AlertCircle className="w-2.5 h-2.5 text-amber-500" />
          Offline
        </span>
      )}
    </div>
  );
}
