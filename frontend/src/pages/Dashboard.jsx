import React, { useState } from "react";
import { toast } from "react-toastify";
import ConfigurationPanel from "../components/ConfigurationPanel";
import SchedulerSettings from "../components/SchedulerSettings";
import GenerateButton from "../components/GenerateButton";
import JobProgressMonitor from "../components/JobProgressMonitor";
import JobHistory from "../components/JobHistory";
import VideoGallery from "../components/VideoGallery";
import {
  createConfiguration,
  generateVideo,
  scheduleJob,
} from "../api/client";

// Map character_style -> image_style so the backend gets a valid ImageStyle
const CHARACTER_TO_IMAGE_STYLE = {
  realistic: "photo_realism",
  "3dtoon": "3d_toon",
  ghibli: "studio_ghibli",
  lego: "lego",
};

const DEFAULT_CONFIG = {
category: "horror",
custom_category: "",
language: "hindi",
duration: "60-90",
voice_type: "alloy",
background_music: false,
auto_upload_youtube: false,
subtitle_style: "default",
image_style: "photo_realism",
  num_videos: 1,
  // Character pipeline
  ai_service: "openai",
  character_style: "realistic",
  characters: [],
};

const DEFAULT_SCHEDULE = {
  generation_mode: "instant",
  schedule_type: "daily",
  cron_expression: "",
};

export default function Dashboard() {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [schedule, setSchedule] = useState(DEFAULT_SCHEDULE);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("monitor");

  const handleGenerate = async () => {
    setLoading(true);
    try {
      // Save configuration first
      const savedConfig = await createConfiguration({
        ...config,
        generation_mode: schedule.generation_mode,
        schedule_type: schedule.generation_mode === "scheduled" ? schedule.schedule_type : null,
        cron_expression: schedule.schedule_type === "cron" ? schedule.cron_expression : null,
      });

      if (schedule.generation_mode === "scheduled") {
        // Create schedule
        await scheduleJob({
          configuration_id: savedConfig.id,
          schedule_type: schedule.schedule_type,
          cron_expression: schedule.schedule_type === "cron" ? schedule.cron_expression : null,
          enabled: true,
        });
        toast.success(`Scheduled ${config.category} video generation (${schedule.schedule_type})!`);
      } else {
        // Generate immediately (for each requested video)
        const count = config.num_videos || 1;
        for (let i = 0; i < count; i++) {
          await generateVideo({
            configuration_id: savedConfig.id,
            category: config.category,
            custom_category: config.custom_category,
            language: config.language,
            duration: config.duration,
            voice_type: config.voice_type,
            background_music: config.background_music,
            auto_upload_youtube: config.auto_upload_youtube,
            subtitle_style: config.subtitle_style,
            image_style: CHARACTER_TO_IMAGE_STYLE[config.character_style] || "photo_realism",
            watermark_path: config.watermark_path || null,
            splash_start_path: config.splash_start_path || null,
            splash_end_path: config.splash_end_path || null,
            ai_service: config.ai_service || "openai",
            character_style: config.character_style || "realistic",
            characters: config.characters || [],
          });
        }
        toast.success(
          count > 1
            ? `${count} video generation jobs queued!`
            : "Video generation started!"
        );
      }
    } catch (err) {
      console.error(err);
      toast.error(
        err.response?.data?.detail || "Failed to start generation. Check backend connection."
      );
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: "monitor", label: "📊 Progress" },
    { id: "history", label: "📋 History" },
    { id: "gallery", label: "🎥 Gallery" },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Configuration Panel */}
        <div className="lg:col-span-4 space-y-6">
          <ConfigurationPanel config={config} onChange={setConfig} />
          <SchedulerSettings schedule={schedule} onChange={setSchedule} />
          <GenerateButton onClick={handleGenerate} loading={loading} />
        </div>

        {/* Right: Monitor / History / Gallery */}
        <div className="lg:col-span-8 space-y-6">
          {/* Tab Bar */}
          <div className="flex gap-1 bg-dark-900 rounded-xl p-1 border border-dark-700">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
                  activeTab === tab.id
                    ? "bg-primary-600 text-white shadow"
                    : "text-dark-400 hover:text-white hover:bg-dark-800"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === "monitor" && <JobProgressMonitor />}
          {activeTab === "history" && <JobHistory />}
          {activeTab === "gallery" && <VideoGallery />}
        </div>
      </div>
    </div>
  );
}
