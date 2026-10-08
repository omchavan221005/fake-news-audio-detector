import React, { useState } from 'react';

const CLASSIFICATION_BADGES = {
  TRUE: { label: 'True', bg: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' },
  FALSE: { label: 'Misinformation / False', bg: 'bg-rose-500/20 text-rose-300 border-rose-500/40' },
  MISLEADING: { label: 'Misleading', bg: 'bg-amber-500/20 text-amber-300 border-amber-500/40' },
  CONFLICTING: { label: 'Conflicting', bg: 'bg-purple-500/20 text-purple-300 border-purple-500/40' },
  UNVERIFIED: { label: 'Unverified', bg: 'bg-slate-700/40 text-slate-300 border-slate-600' },
};

const STANCE_BADGES = {
  supports: { label: 'Supports', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' },
  contradicts: { label: 'Contradicts', color: 'bg-rose-500/20 text-rose-300 border-rose-500/40' },
  neutral: { label: 'Neutral', color: 'bg-slate-700/40 text-slate-300 border-slate-600' },
};

export default function ClaimsExplorer({ claims = [], onSeekTime }) {
  const [filter, setFilter] = useState('ALL');
  const [expandedClaimId, setExpandedClaimId] = useState(null);

  const filteredClaims = claims.filter((cl) => {
    if (filter === 'ALL') return true;
    const classification = cl.verification?.classification || 'UNVERIFIED';
    return classification === filter;
  });

  const toggleExpand = (id) => {
    setExpandedClaimId(expandedClaimId === id ? null : id);
  };

  const formatTime = (secs) => {
    if (secs === null || secs === undefined) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  return (
    <div className="glass-card p-6 border-white/10 flex flex-col h-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 mb-4 border-b border-white/10 gap-3">
        <div className="flex items-center space-x-2.5">
          <span className="text-xl">🔍</span>
          <h3 className="text-lg font-bold text-white font-heading">
            Extracted Claims & Fact-Checks ({claims.length})
          </h3>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap gap-1.5 text-xs">
          {['ALL', 'FALSE', 'TRUE', 'MISLEADING', 'UNVERIFIED'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                filter === f
                  ? 'bg-indigo-600 text-white shadow'
                  : 'bg-white/5 text-slate-400 hover:text-white'
              }`}
            >
              {f === 'ALL' ? 'All Claims' : f}
            </button>
          ))}
        </div>
      </div>

      {/* Claims List */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 max-h-[560px]">
        {filteredClaims.length === 0 ? (
          <div className="text-center py-16 text-slate-500 text-sm">
            No claims match the selected filter.
          </div>
        ) : (
          filteredClaims.map((claim, idx) => {
            const ver = claim.verification || {};
            const classification = ver.classification || 'UNVERIFIED';
            const badge = CLASSIFICATION_BADGES[classification] || CLASSIFICATION_BADGES.UNVERIFIED;
            const sources = ver.sources || [];
            const isExpanded = expandedClaimId === claim.id;
            const confPercent = ver.confidence ? Math.round(ver.confidence * 100) : 50;

            return (
              <div
                key={claim.id || idx}
                className="p-5 rounded-2xl bg-black/30 border border-white/10 hover:border-indigo-500/40 transition-all duration-200"
              >
                {/* Header: Timestamp pill and Verdict Badge */}
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <div className="flex items-center space-x-2">
                    {claim.start_time !== null && (
                      <button
                        type="button"
                        onClick={() => onSeekTime && onSeekTime(claim.start_time)}
                        className="px-2.5 py-1 rounded-md bg-indigo-950/60 hover:bg-indigo-600/80 text-cyan-300 text-xs font-mono font-bold border border-indigo-500/30 flex items-center space-x-1.5 transition-colors"
                        title="Seek audio to this statement"
                      >
                        <span>▶</span>
                        <span>{formatTime(claim.start_time)} – {formatTime(claim.end_time)}</span>
                      </button>
                    )}
                    <span className="text-xs text-slate-500">Claim #{idx + 1}</span>
                  </div>

                  <span className={`px-3 py-1 rounded-full text-xs font-bold border uppercase tracking-wider ${badge.bg}`}>
                    {badge.label}
                  </span>
                </div>

                {/* Claim Statement */}
                <h4 className="text-base font-semibold text-white leading-snug mb-3">
                  "{claim.claim_text}"
                </h4>

                {/* Verification Explanation */}
                {ver.explanation && (
                  <p className="text-xs text-slate-300 bg-white/[0.03] p-3 rounded-xl border border-white/5 mb-3 leading-relaxed">
                    <span className="font-semibold text-slate-200">Fact-Check Finding: </span>
                    {ver.explanation}
                  </p>
                )}

                {/* Confidence Meter */}
                <div className="flex items-center space-x-3 text-xs text-slate-400 mb-3">
                  <span>Confidence:</span>
                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden max-w-[120px]">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-cyan-400 rounded-full"
                      style={{ width: `${confPercent}%` }}
                    />
                  </div>
                  <span className="font-mono text-slate-300 font-medium">{confPercent}%</span>
                </div>

                {/* Evidence Sources Accordion */}
                {sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-white/5">
                    <button
                      onClick={() => toggleExpand(claim.id)}
                      className="w-full flex items-center justify-between text-xs font-semibold text-indigo-300 hover:text-indigo-200 transition-colors"
                    >
                      <span className="flex items-center space-x-1.5">
                        <span>📚</span>
                        <span>Cited Corroborating Evidence ({sources.length})</span>
                      </span>
                      <span>{isExpanded ? '▲ Hide' : '▼ View Sources'}</span>
                    </button>

                    {isExpanded && (
                      <div className="mt-3 space-y-2.5 pl-1 animate-fadeIn">
                        {sources.map((src, sIdx) => {
                          const stanceKey = src.stance || 'neutral';
                          const stanceBadge = STANCE_BADGES[stanceKey] || STANCE_BADGES.neutral;

                          return (
                            <div
                              key={sIdx}
                              className="p-3 rounded-xl bg-black/40 border border-white/5 text-xs space-y-1.5"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <a
                                  href={src.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="font-bold text-cyan-400 hover:underline truncate max-w-xs sm:max-w-md flex items-center space-x-1"
                                >
                                  <span>{src.source_title || src.source_domain || 'Evidence Link'}</span>
                                  <svg className="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                  </svg>
                                </a>

                                <div className="flex items-center space-x-2">
                                  <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 uppercase font-semibold">
                                    {src.source_type}
                                  </span>
                                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border uppercase ${stanceBadge.color}`}>
                                    {stanceBadge.label}
                                  </span>
                                </div>
                              </div>

                              {src.excerpt && (
                                <p className="text-slate-400 italic leading-relaxed text-[11px]">
                                  "{src.excerpt}"
                                </p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
