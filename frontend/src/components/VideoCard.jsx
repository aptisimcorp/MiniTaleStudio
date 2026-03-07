import React, { useState } from "react";

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

export default function VideoCard({ video, onPlay, onYouTubeUpload }) {
  const filename = video.filename || video.file_path?.split("/").pop() || "video.mp4";
  const catColor = CATEGORY_COLORS[video.category] || "bg-primary-600/20 text-primary-400";
  const [uploading, setUploading] = useState(false);

  const handleYouTubeUpload = async () => {
    if (!onYouTubeUpload) return;
    setUploading(true);
    try {
      await onYouTubeUpload(video.id);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-dark-800 rounded-xl border border-dark-700 overflow-hidden hover:border-dark-500 transition-all group">
      {/* Thumbnail with Play overlay */}
      <div
        className="aspect-[9/16] max-h-64 bg-dark-900 flex items-center justify-center overflow-hidden relative cursor-pointer"
        onClick={() => onPlay && onPlay(video)}
      >
        {video.thumbnail ? (
          <img
            src={video.thumbnail}
            alt={video.category}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="text-center">
            <span className="text-4xl">🎬</span>
            <p className="text-dark-500 text-xs mt-1">Video</p>
          </div>
        )}
        {/* Play button overlay */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="w-14 h-14 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
            <span className="text-2xl ml-1">▶</span>
          </div>
        </div>
      </div>

      {/* Info */}
      <div className="p-4 space-y-2">
        {/* Title */}
        {video.title && (
          <p className="text-sm font-semibold text-white truncate" title={video.title}>
            {video.title}
          </p>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 text-xs rounded-full capitalize font-medium ${catColor}`}>
            {video.category}
          </span>
          <span className="px-2 py-0.5 bg-dark-700 text-dark-300 text-xs rounded-full capitalize">
            {video.language}
          </span>
        </div>

        <div className="flex items-center justify-between text-xs text-dark-400">
          <span>{video.duration}s</span>
          <span>{new Date(video.created_at).toLocaleDateString()}</span>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 mt-2">
          <button
            onClick={() => onPlay && onPlay(video)}
            className="flex-1 text-center py-2 bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            ▶ Play
          </button>
          <button
            onClick={handleYouTubeUpload}
            disabled={uploading}
            className={`flex-1 text-center py-2 text-sm font-medium rounded-lg transition-colors ${
              video.youtube_url
                ? "bg-green-600/20 text-green-400 cursor-default"
                : uploading
                ? "bg-red-700 text-white opacity-70 cursor-not-allowed"
                : "bg-red-600 hover:bg-red-500 text-white"
            }`}
            title={video.youtube_url ? `Uploaded: ${video.youtube_url}` : "Upload to YouTube"}
          >
            {video.youtube_url ? "✓ YouTube" : uploading ? "Uploading..." : "▶ YouTube"}
          </button>
        </div>
      </div>
    </div>
  );
}
