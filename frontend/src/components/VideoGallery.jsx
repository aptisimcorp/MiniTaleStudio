import React, { useEffect, useState, useCallback } from "react";
import { toast } from "react-toastify";
import { getVideos, uploadToYouTube } from "../api/client";
import VideoCard from "./VideoCard";
import VideoPlayerModal from "./VideoPlayerModal";

const API_BASE = process.env.NODE_ENV === "production"
  ? (process.env.REACT_APP_API_URL || "http://localhost:8000")
  : "";

export default function VideoGallery() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [playingVideo, setPlayingVideo] = useState(null);

  const fetchVideos = useCallback(async () => {
    try {
      const data = await getVideos();
      setVideos(Array.isArray(data) ? data : []);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchVideos();
    const interval = setInterval(fetchVideos, 10000);
    return () => clearInterval(interval);
  }, [fetchVideos]);

  const handlePlay = (video) => {
    // Use blob_url if available, otherwise fall back to static file path
    const videoUrl = video.blob_url
      ? video.blob_url
      : `${API_BASE}/static/videos/${video.filename || video.file_path?.split("/").pop() || "video.mp4"}`;
    const filename = video.filename || video.file_path?.split("/").pop() || "video.mp4";
    setPlayingVideo({ url: videoUrl, filename });
  };

  const handleYouTubeUpload = async (videoId) => {
    try {
      const result = await uploadToYouTube(videoId);
      toast.success(`Uploaded to YouTube: ${result.youtube_url}`);
      // Refresh videos to update the youtube_url status
      fetchVideos();
    } catch (err) {
      const detail = err.response?.data?.detail || "YouTube upload failed.";
      toast.error(detail);
    }
  };

  return (
    <div className="bg-dark-900 rounded-xl border border-dark-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">🎥 Generated Videos</h2>
        <button
          onClick={fetchVideos}
          className="text-xs text-dark-400 hover:text-primary-400 transition-colors"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-dark-500 text-sm">Loading videos...</p>
      ) : videos.length === 0 ? (
        <div className="text-center py-12">
          <span className="text-5xl">🎬</span>
          <p className="text-dark-400 mt-3">No videos generated yet.</p>
          <p className="text-dark-500 text-sm">Configure settings and click Generate!</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {videos.map((video) => (
            <VideoCard
              key={video.id}
              video={video}
              onPlay={handlePlay}
              onYouTubeUpload={handleYouTubeUpload}
            />
          ))}
        </div>
      )}

      {/* Video Player Modal */}
      {playingVideo && (
        <VideoPlayerModal
          videoUrl={playingVideo.url}
          filename={playingVideo.filename}
          onClose={() => setPlayingVideo(null)}
        />
      )}
    </div>
  );
}
