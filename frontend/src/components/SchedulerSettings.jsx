import React from "react";

const SCHEDULE_TYPES = [
  { value: "hourly", label: "Every Hour" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "cron", label: "Cron Expression" },
];

export default function SchedulerSettings({ schedule, onChange }) {
  const update = (key, value) => onChange({ ...schedule, [key]: value });

  return (
    <div className="bg-dark-900 rounded-xl border border-dark-700 p-6 space-y-4">
      <h2 className="text-lg font-semibold text-white">📅 Scheduler</h2>

      {/* Mode Toggle */}
      <div>
        <label className="block text-sm font-medium text-dark-300 mb-1">Generation Mode</label>
        <div className="flex gap-2">
          <button
            onClick={() => update("generation_mode", "instant")}
            className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              schedule.generation_mode === "instant"
                ? "bg-primary-600 text-white"
                : "bg-dark-800 text-dark-300 hover:bg-dark-700"
            }`}
          >
            ⚡ Run Instantly
          </button>
          <button
            onClick={() => update("generation_mode", "scheduled")}
            className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              schedule.generation_mode === "scheduled"
                ? "bg-primary-600 text-white"
                : "bg-dark-800 text-dark-300 hover:bg-dark-700"
            }`}
          >
            🕐 Schedule
          </button>
        </div>
      </div>

      {/* Schedule Options */}
      {schedule.generation_mode === "scheduled" && (
        <>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-1">Frequency</label>
            <div className="grid grid-cols-2 gap-2">
              {SCHEDULE_TYPES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => update("schedule_type", t.value)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    schedule.schedule_type === t.value
                      ? "bg-primary-600 text-white"
                      : "bg-dark-800 text-dark-300 hover:bg-dark-700"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {schedule.schedule_type === "cron" && (
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-1">
                Cron Expression
              </label>
              <input
                type="text"
                placeholder="*/30 * * * *"
                value={schedule.cron_expression || ""}
                onChange={(e) => update("cron_expression", e.target.value)}
                className="w-full px-3 py-2 bg-dark-800 border border-dark-600 rounded-lg text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent font-mono"
              />
              <p className="text-xs text-dark-500 mt-1">
                Format: minute hour day month weekday
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
