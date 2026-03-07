import axios from "axios";

// In development, the proxy in package.json forwards /api calls to localhost:8000
// In production, use the full URL from the environment variable
const API_BASE = process.env.NODE_ENV === "production"
  ? (process.env.REACT_APP_API_URL || "http://localhost:8000")
  : "";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  timeout: 15000,
});

// Request interceptor to attach JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for debugging and 401 handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error(`[API] ${error.response.status} ${error.config?.url}:`, error.response.data);
      // If unauthorized, clear token and redirect to login
      if (error.response.status === 401) {
        localStorage.removeItem("access_token");
        window.location.reload();
      }
    } else if (error.request) {
      console.error(`[API] Network error on ${error.config?.url}:`, error.message);
    }
    return Promise.reject(error);
  }
);

// ?? Authentication ??????????????????????????????????????????????????????

export async function loginUser(email, password) {
  const { data } = await api.post("/auth/login", { email, password });
  return data;
}

export function logout() {
  localStorage.removeItem("access_token");
  window.location.reload();
}

export function getToken() {
  return localStorage.getItem("access_token");
}

// ?? Configurations ??????????????????????????????????????????????????????

export async function createConfiguration(config) {
  const { data } = await api.post("/configurations", config);
  return data;
}

export async function getConfigurations() {
  const { data } = await api.get("/configurations");
  return data;
}

export async function getConfiguration(id) {
  const { data } = await api.get(`/configurations/${id}`);
  return data;
}

// ?? Video Generation ????????????????????????????????????????????????????

export async function generateVideo(params) {
  const { data } = await api.post("/generate-video", params);
  return data;
}

// ?? Jobs ????????????????????????????????????????????????????????????????

export async function getJobs() {
  const { data } = await api.get("/jobs");
  return data;
}

export async function getJob(id) {
  const { data } = await api.get(`/jobs/${id}`);
  return data;
}

export async function retryJob(jobId) {
  const { data } = await api.post(`/jobs/${jobId}/retry`);
  return data;
}

// Upload files (watermark, splash screens)

export async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 30000,
  });
  return data;
}

// Videos

export async function getVideos() {
  const { data } = await api.get("/videos");
  return data;
}

// ?? YouTube ?????????????????????????????????????????????????????????????

export async function uploadToYouTube(videoId) {
  const { data } = await api.post("/youtube/upload", { video_id: videoId }, {
    timeout: 300000, // 5 minutes — download from blob + upload to YouTube takes time
  });
  return data;
}

export async function getYouTubeConnectUrl() {
  const { data } = await api.get("/youtube/connect");
  return data;
}

export async function getYouTubeStatus() {
  const { data } = await api.get("/youtube/status");
  return data;
}

// ?? Schedules ???????????????????????????????????????????????????????????

export async function scheduleJob(params) {
  const { data } = await api.post("/schedule-job", params);
  return data;
}

export async function getSchedules() {
  const { data } = await api.get("/schedules");
  return data;
}

export async function deleteSchedule(id) {
  const { data } = await api.delete(`/schedules/${id}`);
  return data;
}

export default api;
