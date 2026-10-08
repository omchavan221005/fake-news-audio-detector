import React from 'react';

const RISK_CONFIG = {
  LOW: {
    bg: 'bg-emerald-950/40',
    border: 'border-emerald-500/50',
    text: 'text-emerald-400',
    badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
    glow: 'shadow-[0_0_30px_rgba(16,185,129,0.2)]',
    label: 'Low Risk',
  },
  MEDIUM: {
    bg: 'bg-amber-950/40',
    border: 'border-amber-500/50',
    text: 'text-amber-400',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    glow: 'shadow-[0_0_30px_rgba(245,158,11,0.2)]',
    label: 'Medium Risk',
  },
  HIGH: {
    bg: 'bg-orange-950/40',
    border: 'border-orange-500/50',
    text: 'text-orange-400',
    badge: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
    glow: 'shadow-[0_0_30px_rgba(249,115,22,0.25)]',
    label: 'High Risk',
  },
  CRITICAL: {
    bg: 'bg-rose-950/40',
    border: 'border-rose-500/60',
    text: 'text-rose-400',
    badge: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
    glow: 'shadow-[0_0_35px_rgba(239,68,68,0.3)]',
    label: 'Critical Risk',
  },
};

const CREDIBILITY_CONFIG = {
  LIKELY_TRUE: { text: 'Likely True', color: 'text-emerald-400', badge: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300' },
  LIKELY_FALSE: { text: 'Likely Misinformation', color: 'text-rose-400', badge: 'bg-rose-500/20 border-rose-500/40 text-rose-300' },
  MISLEADING: { text: 'Misleading / Partial Truth', color: 'text-amber-400', badge: 'bg-amber-500/20 border-amber-500/40 text-amber-300' },
  CONFLICTING: { text: 'Conflicting Evidence', color: 'text-purple-400', badge: 'bg-purple-500/20 border-purple-500/40 text-purple-300' },
  UNVERIFIED: { text: 'Unverified / Insufficient Evidence', color: 'text-slate-400', badge: 'bg-slate-700/40 border-slate-600 text-slate-300' },
};

const AUTHENTICITY_CONFIG = {
  LIKELY_HUMAN: { text: 'Human-Generated Audio', color: 'text-emerald-400', badge: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300' },
  POSSIBLY_MANIPULATED: { text: 'Possibly Manipulated', color: 'text-amber-400', badge: 'bg-amber-500/20 border-amber-500/40 text-amber-300' },
  LIKELY_AI: { text: 'AI-Generated / Synthetic Voice', color: 'text-rose-400', badge: 'bg-rose-500/20 border-rose-500/40 text-rose-300' },
  INCONCLUSIVE: { text: 'Inconclusive Authenticity', color: 'text-slate-400', badge: 'bg-slate-700/40 border-slate-600 text-slate-300' },
};

export default function VerdictBanner({ jobData, onReset }) {
  if (!jobData) return null;

  const riskLevel = jobData.overall_risk_level || 'MEDIUM';
  const riskConfig = RISK_CONFIG[riskLevel] || RISK_CONFIG.MEDIUM;
  const riskScore = jobData.overall_risk_score !== null && jobData.overall_risk_score !== undefined
    ? Math.round(jobData.overall_risk_score * 100)
    : 50;

  const credVerdict = jobData.overall_credibility || 'UNVERIFIED';
  const credConfig = CREDIBILITY_CONFIG[credVerdict] || CREDIBILITY_CONFIG.UNVERIFIED;

  const authVerdict = jobData.overall_authenticity || 'INCONCLUSIVE';
  const authConfig = AUTHENTICITY_CONFIG[authVerdict] || AUTHENTICITY_CONFIG.INCONCLUSIVE;

  const audioFile = jobData.audio_file || {};

  return (
    <div className={`w-full max-w-7xl mx-auto mb-8 glass-card p-6 md:p-8 border ${riskConfig.border} ${riskConfig.bg} ${riskConfig.glow} transition-all duration-300`}>
      {/* Top Header: File info & Reset Action */}
      <div className="flex flex-wrap items-center justify-between pb-6 border-b border-white/10 gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center text-indigo-300">
            🎙️
          </div>
          <div>
            <h2 className="text-xl font-bold text-white font-heading truncate max-w-md">
              {audioFile.original_filename || 'Audio Recording'}
            </h2>
            <div className="flex items-center space-x-3 text-xs text-slate-400 mt-0.5">
              <span>{audioFile.duration_seconds ? `${audioFile.duration_seconds.toFixed(1)}s` : 'Audio'}</span>
              <span>•</span>
              <span>{audioFile.sample_rate ? `${audioFile.sample_rate} Hz` : '16000 Hz'}</span>
              <span>•</span>
              <span className="uppercase">{audioFile.mime_type?.replace('audio/', '') || 'Audio'}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Export Dropdown / Buttons */}
          <div className="flex items-center space-x-1.5 bg-slate-800/80 p-1 rounded-xl border border-slate-700">
            <span className="text-[11px] font-semibold text-slate-400 px-2">Export:</span>
            <a
              href={`http://localhost:8000/api/analyze/${jobData.id || jobData.job_id}/export?format=markdown`}
              download
              target="_blank"
              rel="noreferrer"
              className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-700/60 hover:bg-indigo-600/60 text-slate-200 hover:text-white transition-colors"
              title="Export as Markdown Report"
            >
              📄 Markdown
            </a>
            <a
              href={`http://localhost:8000/api/analyze/${jobData.id || jobData.job_id}/export?format=json`}
              download
              target="_blank"
              rel="noreferrer"
              className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-700/60 hover:bg-cyan-600/60 text-slate-200 hover:text-white transition-colors"
              title="Export Full JSON"
            >
              📊 JSON
            </a>
            <a
              href={`http://localhost:8000/api/analyze/${jobData.id || jobData.job_id}/export?format=csv`}
              download
              target="_blank"
              rel="noreferrer"
              className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-700/60 hover:bg-emerald-600/60 text-slate-200 hover:text-white transition-colors"
              title="Export Claims CSV"
            >
              📑 CSV
            </a>
          </div>

          <button
            onClick={onReset}
            className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800/80 hover:bg-slate-700/80 text-slate-200 border border-slate-700 transition-colors flex items-center space-x-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            <span>Analyze Another</span>
          </button>
        </div>
      </div>

      {/* Main Dual-Verdict & Risk Matrix */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 mt-6 items-center">
        {/* Risk Level Gauge / Badge */}
        <div className="md:col-span-4 flex flex-col items-center justify-center p-6 rounded-2xl bg-black/30 border border-white/10 text-center">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            Composite Threat Assessment
          </span>

          <div className={`px-4 py-1.5 rounded-full text-sm font-bold border uppercase tracking-widest mb-4 ${riskConfig.badge}`}>
            {riskConfig.label}
          </div>

          {/* Radial score circle */}
          <div className="relative w-28 h-28 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
              <path
                className="text-slate-800"
                strokeWidth="3.5"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className={riskConfig.text}
                strokeDasharray={`${riskScore}, 100`}
                strokeWidth="3.5"
                strokeLinecap="round"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <div className="absolute flex flex-col items-center">
              <span className="text-2xl font-black text-white font-heading">
                {riskScore}
              </span>
              <span className="text-[10px] uppercase text-slate-400 font-semibold tracking-wider">
                Risk Score
              </span>
            </div>
          </div>
        </div>

        {/* Dual Verdicts Details */}
        <div className="md:col-span-8 flex flex-col justify-between space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* 1. Content Credibility Card */}
            <div className="p-5 rounded-2xl bg-black/20 border border-white/10 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  1. Content Credibility
                </span>
                <span className="text-base">📰</span>
              </div>
              <div>
                <div className={`text-lg font-bold ${credConfig.color} font-heading`}>
                  {credConfig.text}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Evaluated across factual assertions and corroborating sources.
                </div>
              </div>
            </div>

            {/* 2. Audio Authenticity Card */}
            <div className="p-5 rounded-2xl bg-black/20 border border-white/10 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  2. Audio Authenticity
                </span>
                <span className="text-base">🔊</span>
              </div>
              <div>
                <div className={`text-lg font-bold ${authConfig.color} font-heading`}>
                  {authConfig.text}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Acoustic forensics, vocoder signatures & prosodic naturalness.
                </div>
              </div>
            </div>
          </div>

          {/* Executive Synthesis Explanation */}
          <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 text-xs text-slate-300 leading-relaxed">
            <span className="font-semibold text-white mr-1.5">Executive Summary:</span>
            {jobData.synthesis_explanation || 'Full dual-signal analysis completed across spoken content and acoustic waveform properties.'}
          </div>
        </div>
      </div>
    </div>
  );
}
