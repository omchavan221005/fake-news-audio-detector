/**
 * API client service for communicating with the FastAPI backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function checkBackendHealth() {
  const resp = await fetch(`${API_BASE_URL}/api/health`);
  if (!resp.ok) {
    throw new Error(`Health check failed: ${resp.statusText}`);
  }
  return resp.json();
}

export async function uploadAudioFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  const resp = await fetch(`${API_BASE_URL}/api/audio/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!resp.ok) {
    const errData = await resp.json().catch(() => ({}));
    throw new Error(errData.detail || `Upload failed with status ${resp.status}`);
  }

  return resp.json();
}

export async function startAnalysisJob(audioFileId) {
  const resp = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ audio_file_id: audioFileId }),
  });

  if (!resp.ok) {
    const errData = await resp.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to create analysis job: ${resp.status}`);
  }

  return resp.json();
}

export async function getAnalysisJobStatus(jobId) {
  const resp = await fetch(`${API_BASE_URL}/api/analyze/${jobId}/status`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch job status: ${resp.status}`);
  }
  return resp.json();
}

export async function getAnalysisJobResults(jobId) {
  const resp = await fetch(`${API_BASE_URL}/api/analyze/${jobId}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch job results: ${resp.status}`);
  }
  return resp.json();
}

export function getAudioStreamUrl(audioFileId) {
  return `${API_BASE_URL}/api/audio/${audioFileId}/stream`;
}
