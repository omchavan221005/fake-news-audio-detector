import React, { useState, useEffect, useRef } from 'react';
import {
  checkBackendHealth,
  uploadAudioFile,
  startAnalysisJob,
  getAnalysisJobStatus,
  getAnalysisJobResults,
} from './services/api';
import UploadZone from './components/UploadZone';
import PipelineProgress from './components/PipelineProgress';
import VerdictBanner from './components/VerdictBanner';
import AudioTranscriptPlayer from './components/AudioTranscriptPlayer';
import ClaimsExplorer from './components/ClaimsExplorer';
import AcousticForensics from './components/AcousticForensics';

export default function App() {
  const [backendOnline, setBackendOnline] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [jobResults, setJobResults] = useState(null);
  const [activeSeekTime, setActiveSeekTime] = useState(null);
  const [error, setError] = useState(null);

  const pollIntervalRef = useRef(null);

  // Check backend connectivity on mount
  useEffect(() => {
    checkBackendHealth()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false));
  }, []);

  // Poll job status when a job is active
  useEffect(() => {
    if (!jobId || jobStatus?.status === 'COMPLETED' || jobStatus?.status === 'FAILED') {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      return;
    }

    const poll = async () => {
      try {
        const statusData = await getAnalysisJobStatus(jobId);
        setJobStatus(statusData);

        if (statusData.status === 'COMPLETED') {
          setIsProcessing(false);
          const fullResults = await getAnalysisJobResults(jobId);
          setJobResults(fullResults);
        } else if (statusData.status === 'FAILED') {
          setIsProcessing(false);
          setError(statusData.error_message || 'Pipeline analysis encountered an error.');
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    };

    poll(); // Initial check
    pollIntervalRef.current = setInterval(poll, 1500);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [jobId, jobStatus?.status]);

  const handleStartAnalysis = async (file) => {
    setError(null);
    setIsProcessing(true);
    setJobResults(null);
    setJobStatus(null);

    try {
      // 1. Upload audio file
      const uploadResp = await uploadAudioFile(file);
      const audioFileId = uploadResp.audio_file_id || uploadResp.id;

      // 2. Trigger pipeline job
      const jobResp = await startAnalysisJob(audioFileId);
      setJobId(jobResp.id);
      setJobStatus({
        id: jobResp.id,
        status: jobResp.status,
        progress_percent: jobResp.progress_percent,
        current_stage: jobResp.current_stage || 'Starting pipeline...',
      });
    } catch (err) {
      setIsProcessing(false);
      setError(err.message || 'Failed to initialize audio analysis.');
    }
  };

  const handleReset = () => {
    setJobId(null);
    setJobStatus(null);
    setJobResults(null);
    setActiveSeekTime(null);
    setError(null);
    setIsProcessing(false);
  };

  const handleSeekFromClaim = (startTime) => {
    setActiveSeekTime(startTime);
  };

  return (
    <div className="min-h-screen bg-[#080b11] text-slate-100 flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Navigation Header */}
      <header className="border-b border-white/10 bg-black/40 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3 cursor-pointer" onClick={handleReset}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-md shadow-indigo-500/20">
              <span className="text-xl">🎙️</span>
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-white font-heading block">
                FakeNews<span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">AudioDetector</span>
              </span>
              <span className="text-[10px] text-slate-400 block tracking-wider uppercase font-medium">
                Speech Intelligence & Verification System
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Backend status indicator */}
            <div className="flex items-center space-x-2 text-xs text-slate-400 bg-white/5 px-3 py-1.5 rounded-full border border-white/5">
              <span
                className={`w-2 h-2 rounded-full ${
                  backendOnline === true
                    ? 'bg-emerald-400 animate-pulse'
                    : backendOnline === false
                    ? 'bg-rose-500'
                    : 'bg-amber-400'
                }`}
              />
              <span className="hidden sm:inline">
                {backendOnline === true ? 'API Connected' : backendOnline === false ? 'API Offline' : 'Connecting...'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        {/* Error Alert */}
        {error && (
          <div className="max-w-4xl mx-auto mb-8 p-4 rounded-2xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-sm flex items-start space-x-3 shadow-xl">
            <svg className="w-5 h-5 flex-shrink-0 text-rose-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="flex-1">
              <div className="font-bold text-white mb-0.5">Analysis Failed</div>
              <div>{error}</div>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-rose-300 hover:text-white text-xs underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* View 1: Upload & Initial State */}
        {!jobResults && !isProcessing && (
          <div className="animate-fadeIn">
            <div className="text-center max-w-3xl mx-auto mb-10 space-y-3">
              <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight font-heading leading-tight">
                Verify News Authenticity from <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-cyan-400 to-indigo-300">Spoken Audio</span>
              </h1>
              <p className="text-slate-400 text-base sm:text-lg max-w-2xl mx-auto">
                Comprehensive multi-modal verification: speech-to-text transcription, factual claim extraction, web evidence cross-referencing, and synthetic deepfake voice detection.
              </p>
            </div>

            <UploadZone onStartAnalysis={handleStartAnalysis} isUploading={isProcessing} />
          </div>
        )}

        {/* View 2: Live Pipeline Processing */}
        {isProcessing && jobStatus && (
          <PipelineProgress statusData={jobStatus} />
        )}

        {/* View 3: Completed Intelligence Dashboard */}
        {jobResults && (
          <div className="animate-fadeIn space-y-8">
            {/* Executive Dual-Verdict Banner */}
            <VerdictBanner jobData={jobResults} onReset={handleReset} />

            {/* Main Interactive Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Left Column: Synchronized Audio & Transcript Player */}
              <div className="lg:col-span-6 flex flex-col">
                <AudioTranscriptPlayer
                  audioFileId={jobResults.audio_file?.id}
                  transcription={jobResults.transcription}
                  activeSeekTime={activeSeekTime}
                  onSeekTime={(t) => setActiveSeekTime(t)}
                />
              </div>

              {/* Right Column: Claim Verification Explorer */}
              <div className="lg:col-span-6 flex flex-col">
                <ClaimsExplorer
                  claims={jobResults.claims || []}
                  onSeekTime={handleSeekFromClaim}
                />
              </div>
            </div>

            {/* Bottom Row: Deepfake Audio Forensics */}
            {jobResults.audio_authenticity_result && (
              <AcousticForensics authenticityResult={jobResults.audio_authenticity_result} />
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 bg-black/40 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4">
          Fake News Audio Detector • Dual-Signal Audio & Fact-Checking Engine • Powered by faster-whisper, Silero-VAD & Forensic Forensics
        </div>
      </footer>
    </div>
  );
}
