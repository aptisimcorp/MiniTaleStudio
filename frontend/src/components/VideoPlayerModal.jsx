import React, { useEffect, useRef } from "react";

export default function VideoPlayerModal({ videoUrl, filename, onClose }) {
  const modalRef = useRef(null);
  const videoRef = useRef(null);

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  const handleBackdropClick = (e) => {
    if (e.target === modalRef.current) onClose();
  };

  return (
    <div
      ref={modalRef}
      onClick={handleBackdropClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
    >
      <div className="relative w-full max-w-sm mx-4">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute -top-10 right-0 text-white/70 hover:text-white text-2xl font-bold transition-colors z-10"
        >
          ?
        </button>

        {/* Video container - 9:16 aspect */}
        <div className="relative bg-black rounded-xl overflow-hidden shadow-2xl" style={{ aspectRatio: "9/16" }}>
          <video
            ref={videoRef}
            src={videoUrl}
            controls
            autoPlay
            playsInline
            className="w-full h-full object-contain"
          >
            Your browser does not support the video tag.
          </video>
        </div>

        {/* Filename + Download */}
        <div className="flex items-center justify-between mt-3 px-1">
          <span className="text-white/60 text-sm truncate mr-4">{filename}</span>
          <a
            href={videoUrl}
            download={filename}
            className="flex items-center gap-1 px-3 py-1.5 bg-primary-600 hover:bg-primary-500 text-white text-sm rounded-lg transition-colors whitespace-nowrap"
          >
            ? Download
          </a>
        </div>
      </div>
    </div>
  );
}
