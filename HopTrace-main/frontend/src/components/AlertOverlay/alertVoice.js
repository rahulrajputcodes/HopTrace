const API_BASE = 'http://localhost:8000/api/v1';

export function parseFaultClass(summary = '') {
  const match = summary.match(/^\[(.*?)\]/);
  if (match) {
    return match[1].toUpperCase();
  }
  const lower = summary.toLowerCase();
  if (lower.includes('cascade')) return 'CASCADE';
  if (lower.includes('flapping')) return 'FLAPPING';
  if (lower.includes('upstream')) return 'UPSTREAM';
  return 'ISOLATED';
}

export function buildHindiSpeechText(faultClass, componentId, affectedCount) {
  const comp = componentId || 'घटक';
  const count = affectedCount || 0;

  switch (faultClass) {
    case 'CASCADE':
      return `चेतावनी! घटक ${comp} पर क्रमिक विफलता कैस्केड सक्रिय है। ${count} उपभोक्ता प्रभावित हैं।`;
    case 'FLAPPING':
      return `सूचना! घटक ${comp} पर संपर्क बार-बार अस्थिर हो रहा है। ${count} उपभोक्ता प्रभावित हैं।`;
    case 'UPSTREAM':
      return `गंभीर चेतावनी! अपस्ट्रीम घटक ${comp} पूरी तरह विफल हो गया है। ${count} उपभोक्ता प्रभावित हैं।`;
    case 'ISOLATED':
    default:
      return `सावधान! घटक ${comp} पर पृथक तकनीकी खराबी पाई गई है। ${count} उपभोक्ता प्रभावित हैं।`;
  }
}

export async function playHindiAlertAudio({ incidentId, text, isMuted, getCachedAudio, setCachedAudio }) {
  if (isMuted || !text) return;

  // 1. Check in-memory audio cache
  const cachedUrl = getCachedAudio(text);
  if (cachedUrl) {
    try {
      const audio = new Audio(cachedUrl);
      await audio.play();
      return;
    } catch {
      // Autoplay or audio error; fallback to synth
    }
  }

  // 2. Attempt backend neural TTS
  try {
    const res = await fetch(`${API_BASE}/incidents/${incidentId || 'incident-001'}/explain/audio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        language_code: 'hi-IN',
        text_override: text,
      }),
    });

    if (res.ok) {
      const blob = await res.blob();
      const audioUrl = URL.createObjectURL(blob);
      setCachedAudio(text, audioUrl);
      const audio = new Audio(audioUrl);
      await audio.play();
      return;
    }
  } catch {
    // Backend offline or error; proceed to client-side fallback
  }

  // 3. Fallback: Browser SpeechSynthesis
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'hi-IN';
    utterance.rate = 0.95;

    const voices = window.speechSynthesis.getVoices();
    const hindiVoice = voices.find((v) => v.lang === 'hi-IN' || v.lang.startsWith('hi'));
    if (hindiVoice) {
      utterance.voice = hindiVoice;
    }

    window.speechSynthesis.speak(utterance);
  }
}
