import React, { useEffect, useState, useCallback } from "react";
import { toast } from "react-toastify";
import { getJobs, retryJob } from "../api/client";

const STATUS_STYLES = {
  queued: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  running: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  completed: "bg-green-500/10 text-green-400 border-green-500/20",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
};

const STATUS_ICONS = {
  queued: "\u23F3",
  running: "\uD83D\uDD04",
  completed: "\u2705",
  failed: "\u274C",
};

const CATEGORY_COLORS = {
  horror:   "bg-red-500/20 text-red-400",
  funny:    "bg-yellow-500/20 text-yellow-400",
  crime:    "bg-orange-500/20 text-orange-400",
  thriller: "bg-purple-500/20 text-purple-400",
  history:  "bg-amber-500/20 text-amber-400",
  mystery:  "bg-indigo-500/20 text-indigo-400",
  adult:    "bg-pink-500/20 text-pink-400",
  custom:   "bg-teal-500/20 text-teal-400",
};

// Pipeline step labels and ordering - must match backend PipelineStep enum
const PIPELINE_STEPS = [
  "queued",
  "generating_story",
  "generating_images",
  "generating_narration",
  "generating_subtitles",
  "assembling_video",
  "uploading_blob",
  "cleanup",
  "done",
];

const STEP_LABELS = {
  queued: "Queued",
  generating_story: "Generating Story",
  generating_images: "Generating Images",
  generating_narration: "Generating Narration",
  generating_subtitles: "Generating Subtitles",
  assembling_video: "Assembling Video",
  uploading_blob: "Uploading to Cloud",
  cleanup: "Cleaning Up",
  done: "Done",
  failed: "Failed",
};

function getStepProgress(step) {
  if (!step) return 0;
  const idx = PIPELINE_STEPS.indexOf(step);
  if (idx < 0) return 0;
  return Math.round((idx / (PIPELINE_STEPS.length - 1)) * 100);
}

export default function JobProgressMonitor() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState({});

  const fetchJobs = useCallback(async () => {
    try {
      const data = await getJobs();
      setJobs(Array.isArray(data) ? data.slice(0, 10) : []);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const handleRetry = async (jobId) => {
    setRetrying((prev) => ({ ...prev, [jobId]: true }));
    try {
      await retryJob(jobId);
      toast.success("Job retry started - resuming from last checkpoint");
      fetchJobs();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to retry job");
    } finally {
      setRetrying((prev) => ({ ...prev, [jobId]: false }));
    }
  };

  return (
    <div className="bg-dark-900 rounded-xl border border-dark-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">📊 Job Progress</h2>
        <button
          onClick={fetchJobs}
          className="text-xs text-dark-400 hover:text-primary-400 transition-colors"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-dark-500 text-sm">Loading jobs...</p>
      ) : jobs.length === 0 ? (
        <p className="text-dark-500 text-sm">No jobs yet. Generate your first video!</p>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => {
            const catColor = CATEGORY_COLORS[job.category] || "bg-primary-600/20 text-primary-400";
            const pipelineStep = job.pipeline_step || "queued";
            const progress = job.status === "completed" ? 100
              : job.status === "failed" ? getStepProgress(pipelineStep)
              : getStepProgress(pipelineStep);
            const stepLabel = STEP_LABELS[pipelineStep] || pipelineStep;
            const isRunning = job.status === "running";
            const isFailed = job.status === "failed";

            return (
              <div
                key={job.id}
                className={`p-3 rounded-lg border ${
                  STATUS_STYLES[job.status] || STATUS_STYLES.queued
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-lg flex-shrink-0">{STATUS_ICONS[job.status] || "\u23F3"}</span>
                    <div className="min-w-0">
                      {job.title ? (
                        <p className="text-sm font-semibold text-white truncate" title={job.title}>
                          {job.title}
                        </p>
                      ) : null}
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className={`px-1.5 py-0.5 text-[10px] rounded-full capitalize font-medium ${catColor}`}>
                          {job.category}
                        </span>
                        <span className="text-xs opacity-70 capitalize">{job.language}</span>
                        <span className="text-xs opacity-50">{job.duration}s</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0 ml-2">
                    <span className="text-xs font-medium uppercase">{job.status}</span>
                    <p className="text-xs opacity-50">
                      {new Date(job.created_at).toLocaleTimeString()}
                    </p>
                  </div>
                </div>

                {/* Progress bar and step label for running/failed jobs */}
                {(isRunning || isFailed) && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-dark-300">
                        {isFailed ? `Failed at: ${stepLabel}` : stepLabel}
                      </span>
                      <span className="text-xs text-dark-400">{progress}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-dark-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          isFailed ? "bg-red-500" : "bg-blue-500"
                        } ${isRunning ? "animate-pulse" : ""}`}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Retry button for failed jobs */}
                {isFailed && (
                  <div className="mt-2 flex items-center gap-2">
                    <button
                      onClick={() => handleRetry(job.id)}
                      disabled={retrying[job.id]}
                      className="px-3 py-1 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-medium rounded-lg transition-colors"
                    >
                      {retrying[job.id] ? "Retrying..." : "Retry"}
                    </button>
                    {job.error && (
                      <span className="text-xs text-red-400/70 truncate" title={job.error}>
                        {job.error.split("\n")[0]?.slice(0, 60)}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
