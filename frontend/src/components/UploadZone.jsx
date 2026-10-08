import React, { useState, useRef } from 'react';

export default function UploadZone({ onStartAnalysis, isUploading }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [audioPreviewUrl, setAudioPreviewUrl] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const fileInputRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);

  const startRecording = async () => {
    setErrorMsg(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const recordedFile = new File([audioBlob], `mic_recording_${Date.now()}.wav`, { type: 'audio/wav' });
        validateAndSetFile(recordedFile);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Microphone access error:', err);
      setErrorMsg('Microphone access denied or not available in this browser.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const validateAndSetFile = (file) => {
    setErrorMsg(null);
    if (!file) return;

    const validExtensions = ['.mp3', '.wav', '.m4a', '.mp4'];
    const hasValidExt = validExtensions.some((ext) => file.name.toLowerCase().endsWith(ext));

    if (!hasValidExt) {
      setErrorMsg('Unsupported format. Please upload an .mp3, .wav, .m4a, or .mp4 file.');
      return;
    }

    if (file.size > 100 * 1024 * 1024) {
      setErrorMsg('File exceeds 100 MB limit.');
      return;
    }

    setSelectedFile(file);
    if (audioPreviewUrl) {
      URL.revokeObjectURL(audioPreviewUrl);
    }
    setAudioPreviewUrl(URL.createObjectURL(file));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleRunAnalysis = () => {
    if (!selectedFile) return;
    onStartAnalysis(selectedFile);
  };

  // Demo synthetic sample generator (creates a quick realistic test WAV in-browser)
  const handleLoadDemoSample = (type) => {
    setErrorMsg(null);
    const sampleRate = 16000;
    const duration = 3.5;
    const numSamples = sampleRate * duration;
    const buffer = new ArrayBuffer(44 + numSamples * 2);
    const view = new DataView(buffer);

    const writeString = (offset, string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };

    writeString(0, 'RIFF');
    view.setUint32(4, 36 + numSamples * 2, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(36, 'data');
    view.setUint32(40, numSamples * 2, true);

    for (let i = 0; i < numSamples; i++) {
      const t = i / sampleRate;
      let sample = 0;
      if (type === 'health_report') {
        const f0 = 175.0 + 25.0 * Math.sin(2.0 * Math.PI * 2.5 * t);
        sample = 0.35 * Math.sin(2.0 * Math.PI * f0 * t) + 0.15 * Math.sin(2.0 * Math.PI * 720.0 * t);
      } else {
        const f0 = 210.0 + 35.0 * Math.sin(2.0 * Math.PI * 3.2 * t);
        sample = 0.3 * Math.sin(2.0 * Math.PI * f0 * t) + 0.2 * Math.sin(2.0 * Math.PI * 1150.0 * t);
      }
      const intVal = Math.max(-32767, Math.min(32767, Math.floor(sample * 32767)));
      view.setInt16(44 + i * 2, intVal, true);
    }

    const blob = new Blob([buffer], { type: 'audio/wav' });
    const filename = type === 'health_report' ? 'sample_health_news_report.wav' : 'sample_official_briefing.wav';
    const demoFile = new File([blob], filename, { type: 'audio/wav' });
    validateAndSetFile(demoFile);
  };

  return (
    <div className="w-full max-w-4xl mx-auto mb-10">
      {/* Drag and Drop Zone */}
      <div
        className={`relative glass-card p-8 md:p-12 text-center border-2 border-dashed cursor-pointer transition-all duration-300 ${
          dragActive
            ? 'border-indigo-500 bg-indigo-950/30 shadow-[0_0_30px_rgba(99,102,241,0.25)]'
            : 'border-slate-700/60 hover:border-indigo-500/60'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp3,.wav,.m4a,.mp4,audio/mpeg,audio/wav,audio/x-m4a,video/mp4"
          className="hidden"
          onChange={handleChange}
        />

        <div className="flex flex-col items-center justify-center space-y-4">
          {/* Animated Wave Icon */}
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-indigo-600/30 to-cyan-500/30 border border-indigo-500/30 flex items-center justify-center shadow-lg shadow-indigo-500/10 group-hover:scale-105 transition-transform">
            <svg
              className="w-10 h-10 text-cyan-400 animate-pulse"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.75}
                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 100-6 3 3 0 000 6z"
              />
            </svg>
          </div>

          <div>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Upload Spoken Audio or News Clip
            </h2>
            <p className="text-slate-400 mt-1 max-w-md mx-auto text-sm">
              Drag and drop an audio recording here, or click to browse.
              Supports MP3, WAV, M4A, and MP4 containers up to 100MB.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
            {['.MP3', '.WAV', '.M4A', '.MP4'].map((fmt) => (
              <span
                key={fmt}
                className="px-3 py-1 text-xs font-semibold tracking-wider rounded-full bg-slate-800/80 text-slate-300 border border-slate-700/60"
              >
                {fmt}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Live Microphone Recording Action Bar */}
      <div className="mt-4 flex flex-wrap items-center justify-center gap-4">
        {!isRecording ? (
          <button
            type="button"
            onClick={startRecording}
            className="px-5 py-2.5 rounded-xl bg-slate-800/90 hover:bg-slate-700/90 text-red-400 hover:text-red-300 border border-red-500/30 hover:border-red-500/60 font-medium text-sm transition-all flex items-center space-x-2 shadow-lg shadow-red-950/20"
          >
            <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse"></span>
            <span>Record Live Audio from Microphone</span>
          </button>
        ) : (
          <div className="flex items-center space-x-4 p-2 px-4 rounded-xl bg-red-950/60 border border-red-600 animate-pulse">
            <span className="w-3.5 h-3.5 rounded-full bg-red-500 animate-ping"></span>
            <span className="text-red-200 font-semibold text-sm">
              Recording Live Speech: {Math.floor(recordingSeconds / 60)}:{(recordingSeconds % 60).toString().padStart(2, '0')}
            </span>
            <button
              type="button"
              onClick={stopRecording}
              className="px-4 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold text-xs shadow-md transition-colors"
            >
              Stop & Inspect Recording
            </button>
          </div>
        )}
      </div>

      {errorMsg && (
        <div className="mt-4 p-4 rounded-xl bg-red-950/50 border border-red-800/60 text-red-200 text-sm flex items-center space-x-3">
          <svg className="w-5 h-5 flex-shrink-0 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Selected File Card & Actions */}
      {selectedFile && (
        <div className="mt-6 glass-card p-6 border-indigo-500/30 bg-indigo-950/20 animate-fadeIn">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 rounded-xl bg-indigo-600/30 border border-indigo-400/30 flex items-center justify-center text-indigo-300">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                </svg>
              </div>
              <div>
                <div className="font-semibold text-white text-base truncate max-w-sm sm:max-w-md">
                  {selectedFile.name}
                </div>
                <div className="text-xs text-slate-400 mt-0.5">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • {selectedFile.type || 'audio file'}
                </div>
              </div>
            </div>

            {/* Audio Preview Player */}
            {audioPreviewUrl && (
              <div className="flex-1 max-w-xs">
                <audio controls src={audioPreviewUrl} className="w-full h-9 rounded-lg" />
              </div>
            )}

            {/* Run Button */}
            <button
              onClick={handleRunAnalysis}
              disabled={isUploading}
              className="px-6 py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 active:scale-[0.98] shadow-lg shadow-indigo-500/25 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isUploading ? (
                <>
                  <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <span>Run Full Intelligence Analysis</span>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Quick Test Demo Samples */}
      <div className="mt-6 flex flex-wrap items-center justify-between text-xs text-slate-400 px-2 gap-2">
        <span className="font-medium text-slate-300">Quick Test Samples:</span>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); handleLoadDemoSample('health_report'); }}
            className="px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-cyan-400 border border-slate-700/60 transition-colors flex items-center space-x-1.5"
          >
            <span>🎙️ Sample Health News Clip</span>
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); handleLoadDemoSample('official_briefing'); }}
            className="px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-indigo-300 border border-slate-700/60 transition-colors flex items-center space-x-1.5"
          >
            <span>🎙️ Sample Official Briefing</span>
          </button>
        </div>
      </div>
    </div>
  );
}
