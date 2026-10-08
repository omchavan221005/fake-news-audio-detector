import React, { useState, useRef, useEffect } from 'react';
import { getAudioStreamUrl } from '../services/api';

export default function AudioTranscriptPlayer({ audioFileId, transcription, onSeekTime, activeSeekTime }) {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [searchTerm, setSearchTerm] = useState('');

  const streamUrl = audioFileId ? getAudioStreamUrl(audioFileId) : null;
  const segments = transcription?.segments_json || [];

  // Listen for external seek requests (e.g. clicking a claim card)
  useEffect(() => {
    if (activeSeekTime !== null && activeSeekTime !== undefined && audioRef.current) {
      audioRef.current.currentTime = activeSeekTime;
      audioRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  }, [activeSeekTime]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration || 0);
    }
  };

  const handleSeek = (e) => {
    const newTime = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
      setCurrentTime(newTime);
    }
  };

  const handleRateChange = (rate) => {
    setPlaybackRate(rate);
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
  };

  const formatTime = (secs) => {
    if (isNaN(secs) || secs === null) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const handleSegmentClick = (start) => {
    if (audioRef.current) {
      audioRef.current.currentTime = start;
      audioRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
    if (onSeekTime) onSeekTime(start);
  };

  const filteredSegments = segments.filter((s) =>
    s.text.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="glass-card p-6 border-white/10 flex flex-col h-full">
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-white/10">
        <div className="flex items-center space-x-2.5">
          <span className="text-xl">🎙️</span>
          <h3 className="text-lg font-bold text-white font-heading">
            Synchronized Audio & Transcript
          </h3>
        </div>

        {transcription?.detected_language && (
          <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 uppercase tracking-wider">
            {transcription.detected_language} ({Math.round((transcription.detected_language_prob || 1) * 100)}%)
          </span>
        )}
      </div>

      {/* Hidden Native Audio Element */}
      {streamUrl && (
        <audio
          ref={audioRef}
          src={streamUrl}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onEnded={() => setIsPlaying(false)}
        />
      )}

      {/* Custom Audio Player Controls */}
      <div className="p-4 rounded-2xl bg-black/40 border border-white/10 mb-6">
        {/* Seek Bar */}
        <div className="flex items-center space-x-3 mb-3">
          <span className="text-xs font-mono text-slate-400 w-10 text-right">
            {formatTime(currentTime)}
          </span>
          <input
            type="range"
            min="0"
            max={duration || 100}
            step="0.1"
            value={currentTime}
            onChange={handleSeek}
            className="flex-1 h-2 rounded-lg bg-slate-800 accent-indigo-500 cursor-pointer"
          />
          <span className="text-xs font-mono text-slate-400 w-10">
            {formatTime(duration)}
          </span>
        </div>

        {/* Buttons and Speed Controls */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <button
              onClick={togglePlay}
              className="w-11 h-11 rounded-full bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white flex items-center justify-center shadow-lg shadow-indigo-500/25 active:scale-95 transition-all"
            >
              {isPlaying ? (
                <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24">
                  <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                </svg>
              ) : (
                <svg className="w-5 h-5 fill-current ml-0.5" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              )}
            </button>

            <button
              onClick={() => {
                if (audioRef.current) {
                  audioRef.current.currentTime = Math.max(0, audioRef.current.currentTime - 5);
                }
              }}
              className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs transition-colors"
              title="Rewind 5s"
            >
              -5s
            </button>

            <button
              onClick={() => {
                if (audioRef.current) {
                  audioRef.current.currentTime = Math.min(duration, audioRef.current.currentTime + 5);
                }
              }}
              className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs transition-colors"
              title="Fast Forward 5s"
            >
              +5s
            </button>
          </div>

          {/* Speed Selector */}
          <div className="flex items-center space-x-1 bg-black/40 p-1 rounded-xl border border-white/10 text-xs">
            {[0.75, 1.0, 1.25, 1.5].map((rate) => (
              <button
                key={rate}
                onClick={() => handleRateChange(rate)}
                className={`px-2 py-1 rounded-lg font-medium transition-all ${
                  playbackRate === rate
                    ? 'bg-indigo-600 text-white shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {rate}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Transcript Search Bar */}
      <div className="relative mb-3">
        <input
          type="text"
          placeholder="Filter transcript keywords..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-3.5 py-2 pl-9 text-xs rounded-xl bg-black/30 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
        />
        <svg className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      </div>

      {/* Synchronized Transcript Segments List */}
      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 max-h-[520px]">
        {filteredSegments.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-sm">
            {segments.length === 0 ? 'No transcript segments available.' : 'No matching phrases found.'}
          </div>
        ) : (
          filteredSegments.map((seg) => {
            const isActive = currentTime >= seg.start && currentTime <= seg.end;

            return (
              <div
                key={seg.id}
                onClick={() => handleSegmentClick(seg.start)}
                className={`group p-3.5 rounded-xl border cursor-pointer transition-all duration-200 ${
                  isActive
                    ? 'bg-indigo-950/50 border-indigo-500/80 shadow-[0_0_20px_rgba(99,102,241,0.25)]'
                    : 'bg-black/20 border-white/5 hover:border-indigo-500/40 hover:bg-white/[0.02]'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-[11px] font-mono font-medium px-2 py-0.5 rounded-md ${
                    isActive
                      ? 'bg-indigo-500 text-white font-bold'
                      : 'bg-white/5 text-slate-400 group-hover:text-indigo-300'
                  }`}>
                    {formatTime(seg.start)} – {formatTime(seg.end)}
                  </span>
                  {isActive && (
                    <span className="text-[10px] uppercase font-bold tracking-widest text-cyan-400 animate-pulse flex items-center space-x-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                      <span>Now Playing</span>
                    </span>
                  )}
                </div>

                <p className={`text-sm leading-relaxed transition-colors ${
                  isActive ? 'text-white font-medium' : 'text-slate-300'
                }`}>
                  {seg.text}
                </p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
