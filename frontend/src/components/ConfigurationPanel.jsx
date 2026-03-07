import React, { useRef } from "react";
import { uploadFile } from "../api/client";

const CATEGORIES = [
  { value: "horror", label: "🧟 Horror" },
  { value: "funny", label: "😂 Funny" },
  { value: "crime", label: "🔪 Crime" },
  { value: "thriller", label: "😱 Thriller" },
  { value: "history", label: "📜 History" },
  { value: "mystery", label: "🔍 Mystery" },
  { value: "adult", label: "🔞 Adult" },
  { value: "custom", label: "✏️ Custom" },
];

const LANGUAGES = [
  { value: "english", label: "English" },
  { value: "hindi", label: "Hindi" },
];

const DURATIONS = [
  { value: "60-90", label: "60–90 sec (Short)" },
  { value: "90-120", label: "90–120 sec (Medium)" },
  { value: "120-180", label: "120–180 sec (Long)" },
];

const IMAGE_STYLES = [
  { value: "lego", label: "🧱 Lego" },
  { value: "comic_book", label: "💥 Comic Book" },
  { value: "disney_toon", label: "🏰 Disney Toon" },
  { value: "studio_ghibli", label: "🌿 Studio Ghibli" },
  { value: "pixelated", label: "👾 Pixelated" },
  { value: "creepy_toon", label: "🎃 Creepy Toon" },
  { value: "childrens_book", label: "📖 Children's Book" },
  { value: "photo_realism", label: "📷 Photo Realism" },
  { value: "minecraft", label: "⛏️ Minecraft" },
  { value: "watercolor", label: "🎨 Watercolor" },
  { value: "expressionism", label: "🖌️ Expressionism" },
  { value: "charcoal", label: "✏️ Charcoal" },
  { value: "gtav", label: "🚗 GTA V" },
  { value: "anime", label: "⚔️ Anime" },
  { value: "film_noir", label: "🎬 Film Noir" },
  { value: "3d_toon", label: "🫧 3D Toon" },
];

const SUBTITLE_STYLES = [
  { value: "default", label: "Default" },
  { value: "bold", label: "Bold" },
  { value: "minimal", label: "Minimal" },
];

const VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"];

export default function ConfigurationPanel({ config, onChange }) {
const update = (key, value) => onChange({ ...config, [key]: value });
const watermarkRef = useRef(null);
const splashStartRef = useRef(null);
const splashEndRef = useRef(null);

const handleUpload = async (file, configKey) => {
  if (!file) return;
  try {
    const result = await uploadFile(file);
    update(configKey, result.path);
  } catch (err) {
    console.error("Upload failed:", err);
  }
};

  return (
    <div className="bg-dark-900 rounded-xl border border-dark-700 p-6 space-y-5">
      <h2 className="text-lg font-semibold text-white">⚙️ Configuration</h2>

      {/* Category */}
      <div>
        <label className="block text-sm font-medium text-dark-300 mb-1">Story Category</label>
        <div className="grid grid-cols-4 gap-2">
          {CATEGORIES.map((c) => (
            <button
              key={c.value}
              onClick={() => update("category", c.value)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                config.category === c.value
                  ? "bg-primary-600 text-white shadow-lg shadow-primary-600/25"
                  : "bg-dark-800 text-dark-300 hover:bg-dark-700"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        {config.category === "custom" && (
          <input
            type="text"
            placeholder="Enter custom category..."
            value={config.custom_category || ""}
            onChange={(e) => update("custom_category", e.target.value)}
            className="mt-2 w-full px-3 py-2 bg-dark-800 border border-dark-600 rounded-lg text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        )}
      </div>

      {/* Language */}
      <div>
        <label className="block text-sm font-medium text-dark-300 mb-1">Language</label>
        <div className="flex gap-2">
          {LANGUAGES.map((l) => (
            <button
              key={l.value}
              onClick={() => update("language", l.value)}
              className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                config.language === l.value
                  ? "bg-primary-600 text-white"
                  : "bg-dark-800 text-dark-300 hover:bg-dark-700"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Duration */}
      <div>
        <label className="block text-sm font-medium text-dark-300 mb-1">Video Duration</label>
        <div className="flex flex-col gap-2">
          {DURATIONS.map((d) => (
            <button
              key={d.value}
              onClick={() => update("duration", d.value)}
              className={`px-3 py-2 rounded-lg text-sm font-medium text-left transition-all ${
                config.duration === d.value
                  ? "bg-primary-600 text-white"
                  : "bg-dark-800 text-dark-300 hover:bg-dark-700"
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>
      </div>

      {/* Image Style */}
      <div>
        <label className="block text-sm font-medium text-dark-300 mb-1">Image Style</label>
        <div className="grid grid-cols-4 gap-2 max-h-48 overflow-y-auto pr-1">
          {IMAGE_STYLES.map((s) => (
            <button
              key={s.value}
              onClick={() => update("image_style", s.value)}
              className={`px-2 py-2 rounded-lg text-xs font-medium transition-all ${
                config.image_style === s.value
                  ? "bg-primary-600 text-white shadow-lg shadow-primary-600/25"
                  : "bg-dark-800 text-dark-300 hover:bg-dark-700"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Voice Type */}
      <div>
        <label className="block text-sm font-medium text-dark-300 mb-1">Voice Type</label>
        <select
          value={config.voice_type || "alloy"}
          onChange={(e) => update("voice_type", e.target.value)}
          className="w-full px-3 py-2 bg-dark-800 border border-dark-600 rounded-lg text-white text-sm focus:ring-2 focus:ring-primary-500"
        >
          {VOICES.map((v) => (
            <option key={v} value={v}>
              {v.charAt(0).toUpperCase() + v.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Subtitle Style */}
      <div>
        <label className="block text-sm font-medium text-dark-300 mb-1">Subtitle Style</label>
        <div className="flex gap-2">
          {SUBTITLE_STYLES.map((s) => (
            <button
              key={s.value}
              onClick={() => update("subtitle_style", s.value)}
              className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                config.subtitle_style === s.value
                  ? "bg-primary-600 text-white"
                  : "bg-dark-800 text-dark-300 hover:bg-dark-700"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Number of Videos */}
      <div>
        <label className="block text-sm font-medium text-dark-300 mb-1">
          Number of Videos: {config.num_videos || 1}
        </label>
        <input
          type="range"
          min="1"
          max="10"
          value={config.num_videos || 1}
          onChange={(e) => update("num_videos", parseInt(e.target.value))}
          className="w-full accent-primary-500"
        />
      </div>

      {/* Watermark & Splash Screens */}
      <div className="space-y-3 border-t border-dark-700 pt-4">
        <p className="text-sm font-medium text-dark-300">Branding (Optional)</p>

        {/* Watermark */}
        <div>
          <label className="block text-xs text-dark-400 mb-1">Watermark Logo (top-left)</label>
          <input
            ref={watermarkRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => handleUpload(e.target.files[0], "watermark_path")}
          />
          <button
            onClick={() => watermarkRef.current?.click()}
            className={`w-full px-3 py-2 rounded-lg text-sm text-left transition-all ${
              config.watermark_path
                ? "bg-green-600/20 text-green-400 border border-green-600/30"
                : "bg-dark-800 text-dark-300 hover:bg-dark-700"
            }`}
          >
            {config.watermark_path ? "✅ Watermark uploaded" : "📤 Upload watermark image"}
          </button>
          {config.watermark_path && (
            <button onClick={() => update("watermark_path", null)} className="text-xs text-red-400 mt-1 hover:underline">Remove</button>
          )}
        </div>

        {/* Splash Start */}
        <div>
          <label className="block text-xs text-dark-400 mb-1">Intro Splash Screen (3s)</label>
          <input
            ref={splashStartRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => handleUpload(e.target.files[0], "splash_start_path")}
          />
          <button
            onClick={() => splashStartRef.current?.click()}
            className={`w-full px-3 py-2 rounded-lg text-sm text-left transition-all ${
              config.splash_start_path
                ? "bg-green-600/20 text-green-400 border border-green-600/30"
                : "bg-dark-800 text-dark-300 hover:bg-dark-700"
            }`}
          >
            {config.splash_start_path ? "✅ Intro image uploaded" : "📤 Upload intro image"}
          </button>
          {config.splash_start_path && (
            <button onClick={() => update("splash_start_path", null)} className="text-xs text-red-400 mt-1 hover:underline">Remove</button>
          )}
        </div>

        {/* Splash End */}
        <div>
          <label className="block text-xs text-dark-400 mb-1">Outro Splash Screen (3s)</label>
          <input
            ref={splashEndRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => handleUpload(e.target.files[0], "splash_end_path")}
          />
          <button
            onClick={() => splashEndRef.current?.click()}
            className={`w-full px-3 py-2 rounded-lg text-sm text-left transition-all ${
              config.splash_end_path
                ? "bg-green-600/20 text-green-400 border border-green-600/30"
                : "bg-dark-800 text-dark-300 hover:bg-dark-700"
            }`}
          >
            {config.splash_end_path ? "✅ Outro image uploaded" : "📤 Upload outro image"}
          </button>
          {config.splash_end_path && (
            <button onClick={() => update("splash_end_path", null)} className="text-xs text-red-400 mt-1 hover:underline">Remove</button>
          )}
        </div>
      </div>

      {/* Background Music */}
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-dark-300">Background Music</label>
        <button
          onClick={() => update("background_music", !config.background_music)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            config.background_music ? "bg-primary-600" : "bg-dark-600"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              config.background_music ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </div>
    </div>
  );
}
