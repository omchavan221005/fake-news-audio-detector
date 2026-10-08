import React from 'react';

const STAGES = [
  { id: 'TRANSCRIBING', label: 'Speech-to-Text', desc: 'faster-whisper & Silero-VAD transcription' },
  { id: 'EXTRACTING_CLAIMS', label: 'Claim Extraction', desc: 'Isolating verifiable factual assertions' },
  { id: 'VERIFYING', label: 'Fact Verification', desc: 'External evidence retrieval & NLI reasoning' },
  { id: 'DETECTING_AUDIO', label: 'Audio Forensics', desc: 'Acoustic spectral & vocoder anomaly detection' },
  { id: 'COMPLETED', label: 'Synthesis', desc: 'Generating dual verdict & risk assessment' },
];

export default function PipelineProgress({ statusData }) {
  const currentStatus = statusData?.status || 'PENDING';
  const progressPercent = statusData?.progress_percent || 0;
  const currentStageDesc = statusData?.current_stage || 'Initializing analysis pipeline...';

  const getStepIndex = (status) => {
    switch (status) {
      case 'TRANSCRIBING': return 0;
      case 'EXTRACTING_CLAIMS': return 1;
      case 'VERIFYING': return 2;
      case 'DETECTING_AUDIO': return 3;
      case 'COMPLETED': return 4;
      default: return 0;
    }
  };

  const activeIdx = getStepIndex(currentStatus);

  return (
    <div className="w-full max-w-4xl mx-auto my-8 glass-card p-8 border-indigo-500/30 bg-slate-900/80 animate-fadeIn shadow-2xl">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center space-x-3">
            <span className="relative flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-indigo-500"></span>
            </span>
            <h3 className="text-xl font-bold text-white font-heading">
              Pipeline Processing in Progress
            </h3>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            {currentStageDesc}
          </p>
        </div>

        <div className="text-right">
          <span className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">
            {progressPercent}%
          </span>
        </div>
      </div>

      {/* Main Animated Progress Bar */}
      <div className="w-full h-3 rounded-full bg-slate-800 overflow-hidden mb-8 p-0.5 border border-slate-700/50">
        <div
          className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-cyan-500 to-indigo-400 transition-all duration-500 ease-out shadow-[0_0_15px_rgba(6,182,212,0.5)]"
          style={{ width: `${Math.max(5, progressPercent)}%` }}
        />
      </div>

      {/* Pipeline Stage Indicators */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {STAGES.map((stg, idx) => {
          const isDone = idx < activeIdx || currentStatus === 'COMPLETED';
          const isCurrent = idx === activeIdx && currentStatus !== 'COMPLETED';

          return (
            <div
              key={stg.id}
              className={`p-3.5 rounded-xl border transition-all ${
                isDone
                  ? 'bg-emerald-950/20 border-emerald-500/40 text-emerald-300'
                  : isCurrent
                  ? 'bg-indigo-950/40 border-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.2)] text-indigo-200'
                  : 'bg-slate-900/40 border-slate-800 text-slate-500'
              }`}
            >
              <div className="flex items-center space-x-2 mb-1">
                {isDone ? (
                  <svg className="w-4 h-4 text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : isCurrent ? (
                  <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping flex-shrink-0" />
                ) : (
                  <div className="w-2.5 h-2.5 rounded-full bg-slate-700 flex-shrink-0" />
                )}
                <span className="text-xs font-bold uppercase tracking-wider truncate">
                  {stg.label}
                </span>
              </div>
              <div className="text-[11px] leading-tight text-slate-400 truncate">
                {stg.desc}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
