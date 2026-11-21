/**
 * M4 — Evaluator Walkthrough modal component.
 *
 * A lightweight, keyboard-navigable, step-by-step carousel that helps
 * evaluators discover HopTrace's core flows. Auto-shows once (persisted in
 * localStorage), and can be re-opened via the "?" button that App.jsx renders.
 *
 * Props:
 *   open    {boolean}   — controlled open state
 *   onClose {function}  — called when the user dismisses
 */

import { useEffect, useCallback, useRef, useState } from 'react';
import { STEPS } from './steps.js';
import { markWalkthroughSeen } from './walkthroughPrefs.js';

// ---------------------------------------------------------------------------
// Step indicator dots
// ---------------------------------------------------------------------------
function StepDots({ total, current, onGoto }) {
  return (
    <div className="flex items-center gap-1.5" role="tablist" aria-label="Walkthrough steps">
      {Array.from({ length: total }, (_, i) => (
        <button
          key={i}
          role="tab"
          aria-selected={i === current}
          aria-label={`Step ${i + 1}`}
          onClick={() => onGoto(i)}
          className={`rounded-full transition-all ${
            i === current
              ? 'w-5 h-2 bg-blue-400'
              : 'w-2 h-2 bg-slate-600 hover:bg-slate-400'
          }`}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Walkthrough component
// ---------------------------------------------------------------------------
export default function Walkthrough({ open, onClose }) {
  const [step, setStep] = useState(0);
  const modalRef = useRef(null);
  const closeRef = useRef(null);

  const total = STEPS.length;
  const current = STEPS[step];
  const isFirst = step === 0;
  const isLast = step === total - 1;

  const handleClose = useCallback(() => {
    markWalkthroughSeen();
    setStep(0);
    onClose();
  }, [onClose]);

  const handlePrev = useCallback(() => setStep(s => Math.max(0, s - 1)), []);
  const handleNext = useCallback(() => {
    if (isLast) {
      handleClose();
    } else {
      setStep(s => s + 1);
    }
  }, [isLast, handleClose]);

  // Keyboard navigation
  useEffect(() => {
    if (!open) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') { handleClose(); return; }
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); handleNext(); }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp')   { e.preventDefault(); handlePrev(); }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, handleNext, handlePrev, handleClose]);

  // Focus trap: move focus into modal when it opens
  useEffect(() => {
    if (open) {
      // Small delay so the DOM is painted before we try to focus
      const t = setTimeout(() => closeRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [open]);

  if (!open) return null;

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="HopTrace evaluator walkthrough"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
    >
      {/* Modal panel */}
      <div
        ref={modalRef}
        className="relative w-full max-w-md bg-[#0a1628] border border-slate-700 rounded-2xl shadow-2xl overflow-hidden"
        style={{ maxHeight: '90vh' }}
      >
        {/* Progress bar */}
        <div className="h-1 bg-slate-800">
          <div
            className="h-full bg-blue-500 transition-all duration-300"
            style={{ width: `${((step + 1) / total) * 100}%` }}
          />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
            Step {step + 1} of {total}
          </span>
          <button
            ref={closeRef}
            onClick={handleClose}
            className="text-slate-500 hover:text-slate-200 text-lg leading-none transition-colors focus:outline-none focus:ring-1 focus:ring-blue-400 rounded"
            aria-label="Close walkthrough"
          >
            ✕
          </button>
        </div>

        {/* Step content */}
        <div className="px-5 pb-2 min-h-[160px]">
          <div className="text-4xl mb-3" aria-hidden="true">{current.emoji}</div>
          <h2 className="text-white font-bold text-lg mb-2 leading-snug">
            {current.title}
          </h2>
          <p className="text-slate-300 text-sm leading-relaxed">
            {current.body}
          </p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-slate-800">
          <StepDots total={total} current={step} onGoto={setStep} />

          <div className="flex items-center gap-2">
            {!isFirst && (
              <button
                onClick={handlePrev}
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                ← Back
              </button>
            )}
            <button
              onClick={handleNext}
              className={`px-4 py-1.5 text-sm font-semibold rounded-lg transition-all focus:outline-none focus:ring-1 focus:ring-blue-300 ${
                isLast
                  ? 'bg-green-600 hover:bg-green-500 text-white'
                  : 'bg-blue-600 hover:bg-blue-500 text-white'
              }`}
            >
              {isLast ? 'Done ✓' : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
