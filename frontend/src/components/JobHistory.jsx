import React, { useEffect, useState, useCallback } from "react";
import { getJobs } from "../api/client";

const STATUS_COLORS = {
  queued: "text-yellow-400",
  running: "text-blue-400",
  completed: "text-green-400",
  failed: "text-red-400",
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

export default function JobHistory() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchJobs = useCallback(async () => {
    try {
      const data = await getJobs();
      setJobs(Array.isArray(data) ? data : []);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  return (
    <div className="bg-dark-900 rounded-xl border border-dark-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">📋 Job History</h2>
        <button
          onClick={fetchJobs}
          className="text-xs text-dark-400 hover:text-primary-400 transition-colors"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-dark-500 text-sm">Loading...</p>
      ) : jobs.length === 0 ? (
        <p className="text-dark-500 text-sm">No jobs found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-dark-400 uppercase border-b border-dark-700">
              <tr>
                <th className="pb-2">Title</th>
                <th className="pb-2">Category</th>
                <th className="pb-2">Language</th>
                <th className="pb-2">Duration</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-800">
              {jobs.map((job) => {
                const catColor = CATEGORY_COLORS[job.category] || "bg-primary-600/20 text-primary-400";
                return (
                  <tr key={job.id} className="hover:bg-dark-800/50">
                    <td className="py-2 text-white font-medium max-w-[200px] truncate" title={job.title || ""}>
                      {job.title || <span className="text-dark-500 italic">Generating...</span>}
                    </td>
                    <td className="py-2">
                      <span className={`px-2 py-0.5 text-xs rounded-full capitalize font-medium ${catColor}`}>
                        {job.category}
                      </span>
                    </td>
                    <td className="py-2 capitalize">{job.language}</td>
                    <td className="py-2">{job.duration}s</td>
                    <td className={`py-2 font-medium capitalize ${STATUS_COLORS[job.status] || ""}`}>
                      {job.status}
                    </td>
                    <td className="py-2 text-dark-400 whitespace-nowrap">
                      {new Date(job.created_at).toLocaleDateString()}{" "}
                      {new Date(job.created_at).toLocaleTimeString()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
