import { useSyncExternalStore } from 'react';

/* --- AlertOverlay state --- */
let storeState = {
  alertOpen: false,
  isArmed: false,
  isMuted: false,
  activeIncident: null,
  affectedSubscribers: [],
  seenIncidentIds: new Set(),
  audioCache: new Map(),
};

const listeners = new Set();

function emitChange() {
  listeners.forEach((listener) => listener());
}

export const appStore = {
  getSnapshot: () => storeState,
  getState: () => storeState,

  subscribe: (listener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  emitChange: () => emitChange(),

  armDemo: () => {
    storeState = { ...storeState, isArmed: true };
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      const silentUtterance = new SpeechSynthesisUtterance('');
      window.speechSynthesis.speak(silentUtterance);
    }
    emitChange();
  },

  toggleMute: () => {
    storeState = { ...storeState, isMuted: !storeState.isMuted };
    emitChange();
  },

  dismissAlert: () => {
    storeState = { ...storeState, alertOpen: false };
    emitChange();
  },

  reopenAlert: () => {
    if (storeState.activeIncident?.id) {
      storeState = { ...storeState, alertOpen: true };
      emitChange();
    }
  },

  notifyIncident: (incident, subscribers = [], isInitialLoad = false) => {
    const incId = incident?.id;

    if (!incId) {
      storeState = {
        ...storeState,
        activeIncident: null,
        affectedSubscribers: [],
        alertOpen: false,
      };
      emitChange();
      return;
    }

    if (isInitialLoad) {
      const nextSeen = new Set(storeState.seenIncidentIds);
      nextSeen.add(incId);
      storeState = {
        ...storeState,
        activeIncident: incident,
        affectedSubscribers: subscribers,
        seenIncidentIds: nextSeen,
      };
      emitChange();
      return;
    }

    if (!storeState.seenIncidentIds.has(incId)) {
      const nextSeen = new Set(storeState.seenIncidentIds);
      nextSeen.add(incId);
      storeState = {
        ...storeState,
        activeIncident: incident,
        affectedSubscribers: subscribers,
        seenIncidentIds: nextSeen,
        alertOpen: true,
      };
      emitChange();
    } else {
      storeState = {
        ...storeState,
        activeIncident: incident,
        affectedSubscribers: subscribers,
      };
      emitChange();
    }
  },

  getCachedAudio: (key) => storeState.audioCache.get(key),
  setCachedAudio: (key, url) => storeState.audioCache.set(key, url),
};

export function useAppStore(selector = (s) => s) {
  return useSyncExternalStore(
    appStore.subscribe,
    () => selector(appStore.getSnapshot())
  );
}
