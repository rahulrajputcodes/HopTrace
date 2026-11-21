/**
 * M4 — PublicStatus UI label strings (en + hi).
 * These are static chrome labels only.
 * Village status *messages* come from the API response `message` field.
 */

export const STRINGS = {
  en: {
    title: 'Network Status',
    subtitle: 'Live connectivity status for all villages',
    lastUpdated: 'Updated',
    justNow: 'just now',
    ago: 'ago',
    retry: 'Retry',
    noData: 'No data',
    dataUnavailable: 'Data unavailable',
    loading: 'Loading…',
    staleWarning: 'Could not refresh — showing last known data',
    statusUp: 'Operational',
    statusDegraded: 'Degraded',
    statusDown: 'Down',
    statusNoData: 'No data',
    since: 'Since',
    playAudio: 'Play audio update',
    langToggle: 'हिन्दी',
  },
  hi: {
    title: 'नेटवर्क स्थिति',
    subtitle: 'सभी गाँवों की लाइव कनेक्टिविटी स्थिति',
    lastUpdated: 'अपडेट',
    justNow: 'अभी',
    ago: 'पहले',
    retry: 'पुनः प्रयास',
    noData: 'डेटा नहीं',
    dataUnavailable: 'डेटा अनुपलब्ध',
    loading: 'लोड हो रहा है…',
    staleWarning: 'रिफ्रेश नहीं हुआ — अंतिम ज्ञात डेटा दिखाया जा रहा है',
    statusUp: 'सक्रिय',
    statusDegraded: 'आंशिक',
    statusDown: 'बंद',
    statusNoData: 'डेटा नहीं',
    since: 'से',
    playAudio: 'ऑडियो अपडेट चलाएँ',
    langToggle: 'English',
  },
};

/** All keys that must be present in every language entry */
export const REQUIRED_KEYS = [
  'title', 'subtitle', 'lastUpdated', 'justNow', 'ago',
  'retry', 'noData', 'dataUnavailable', 'loading', 'staleWarning',
  'statusUp', 'statusDegraded', 'statusDown', 'statusNoData',
  'since', 'playAudio', 'langToggle',
];
