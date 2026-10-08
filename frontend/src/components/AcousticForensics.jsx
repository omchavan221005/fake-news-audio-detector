import React from 'react';

export default function AcousticForensics({ authenticityResult }) {
  if (!authenticityResult) return null;

  const humanProb = Math.round((authenticityResult.human_probability ?? 0.5) * 100);
  const aiProb = Math.round((authenticityResult.ai_probability ?? 0.5) * 100);
  const confidence = Math.round((authenticityResult.detection_confidence ?? 0.5) * 100);
  const modelUsed = authenticityResult.model_used || 'Acoustic-Forensics-v1';
  const features = authenticityResult.acoustic_features || {};

  const isLikelyAI = aiProb >= 70;
  const isManipulated = aiProb >= 40 && aiProb < 70;

  return (
    <div className="glass-card p-6 border-white/10 mt-8">
      <div className="flex flex-wrap items-center justify-between pb-4 mb-6 border-b border-white/10 gap-3">
        <div className="flex items-center space-x-2.5">
          <span className="text-xl">🔬</span>
          <div>
            <h3 className="text-lg font-bold text-white font-heading">
              Audio Deepfake & Synthetic Voice Forensics
            </h3>
            <p className="text-xs text-slate-400">
              Waveform frequency analysis, vocoder phase anomalies & vocal cord prosody
            </p>
          </div>
        </div>

        <span className="px-3 py-1 rounded-full text-xs font-mono font-semibold bg-slate-800 text-slate-300 border border-slate-700">
          Engine: {modelUsed}
        </span>
      </div>

      {/* Human vs. AI Probability Split Bar */}
      <div className="p-6 rounded-2xl bg-black/40 border border-white/10 mb-6">
        <div className="flex items-center justify-between text-sm font-bold mb-2">
          <span className="text-emerald-400 flex items-center space-x-1.5">
            <span>👤 Human Voice Probability:</span>
            <span className="text-lg">{humanProb}%</span>
          </span>
          <span className="text-rose-400 flex items-center space-x-1.5">
            <span>🤖 AI / Synthetic Probability:</span>
            <span className="text-lg">{aiProb}%</span>
          </span>
        </div>

        {/* Dual Progress Bar */}
        <div className="w-full h-4 rounded-full bg-slate-800 overflow-hidden flex p-0.5 border border-white/10">
          <div
            className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-l-full transition-all duration-700"
            style={{ width: `${humanProb}%` }}
          />
          <div
            className="h-full bg-gradient-to-r from-rose-500 to-red-600 rounded-r-full transition-all duration-700"
            style={{ width: `${aiProb}%` }}
          />
        </div>

        <div className="flex items-center justify-between text-xs text-slate-400 mt-3">
          <span>
            Forensic Verdict:{' '}
            <strong className={isLikelyAI ? 'text-rose-400' : isManipulated ? 'text-amber-400' : 'text-emerald-400'}>
              {isLikelyAI ? 'Synthetic / AI-Cloned Voice' : isManipulated ? 'Possible Audio Splice / Manipulation' : 'Natural Human Speech'}
            </strong>
          </span>
          <span>
            Confidence: <strong className="text-white">{confidence}%</strong>
          </span>
        </div>
      </div>

      {/* Acoustic Metric Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {/* 1. Spectral Centroid */}
        <div className="p-4 rounded-xl bg-black/20 border border-white/5 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block truncate">
            Spectral Centroid
          </span>
          <div className="text-lg font-bold text-white font-mono">
            {features.spectral_centroid_hz ? `${features.spectral_centroid_hz} Hz` : 'N/A'}
          </div>
          <span className="text-[10px] text-slate-500 leading-tight block">
            Vocal center of mass
          </span>
        </div>

        {/* 2. Spectral Rolloff */}
        <div className="p-4 rounded-xl bg-black/20 border border-white/5 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block truncate">
            Spectral Rolloff
          </span>
          <div className="text-lg font-bold text-white font-mono">
            {features.spectral_rolloff_hz ? `${features.spectral_rolloff_hz} Hz` : 'N/A'}
          </div>
          <span className="text-[10px] text-slate-500 leading-tight block">
            85% frequency cutoff
          </span>
        </div>

        {/* 3. Pitch Prosody (F0 std dev) */}
        <div className="p-4 rounded-xl bg-black/20 border border-white/5 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block truncate">
            Pitch Variance (F0)
          </span>
          <div className="text-lg font-bold text-white font-mono">
            {features.pitch_std_hz ? `±${features.pitch_std_hz} Hz` : 'N/A'}
          </div>
          <span className="text-[10px] text-slate-500 leading-tight block">
            Natural vocal tremor
          </span>
        </div>

        {/* 4. Zero-Crossing Rate */}
        <div className="p-4 rounded-xl bg-black/20 border border-white/5 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block truncate">
            Phoneme Texture
          </span>
          <div className="text-lg font-bold text-white font-mono">
            {features.zero_crossing_rate_var ? `${(features.zero_crossing_rate_var * 1000).toFixed(2)}m` : 'N/A'}
          </div>
          <span className="text-[10px] text-slate-500 leading-tight block">
            ZCR variability
          </span>
        </div>

        {/* 5. Vocoder Artifacts */}
        <div className="p-4 rounded-xl bg-black/20 border border-white/5 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block truncate">
            Vocoder Artifacts
          </span>
          <div className="text-lg font-bold text-cyan-400 font-mono">
            {features.high_frequency_artifact_ratio ? `${(features.high_frequency_artifact_ratio * 100).toFixed(1)}%` : '0.0%'}
          </div>
          <span className="text-[10px] text-slate-500 leading-tight block">
            High-frequency ratio
          </span>
        </div>
      </div>
    </div>
  );
}
