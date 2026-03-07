import React, { useState, useEffect } from "react";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import Dashboard from "./pages/Dashboard";
import LoginPage from "./pages/LoginPage";
import { getToken, logout, getYouTubeStatus, getYouTubeConnectUrl } from "./api/client";

function App() {
const [token, setToken] = useState(getToken());
const [ytConnected, setYtConnected] = useState(false);

useEffect(() => {
  // Listen for storage changes (e.g. token cleared on 401)
  const handleStorage = () => setToken(getToken());
  window.addEventListener("storage", handleStorage);
  return () => window.removeEventListener("storage", handleStorage);
}, []);

// Check YouTube connection status when logged in
useEffect(() => {
  if (!token) return;
  getYouTubeStatus()
    .then((res) => setYtConnected(res.connected))
    .catch(() => {});
}, [token]);

const handleLogin = (newToken) => {
  setToken(newToken);
};

const handleLogout = () => {
  logout();
};

const handleYouTubeConnect = async () => {
  try {
    const { auth_url } = await getYouTubeConnectUrl();
    window.open(auth_url, "_blank", "width=600,height=700");
  } catch (err) {
    console.error("Failed to get YouTube connect URL", err);
  }
};

  if (!token) {
    return (
      <>
        <LoginPage onLogin={handleLogin} />
        <ToastContainer
          position="bottom-right"
          autoClose={4000}
          hideProgressBar={false}
          theme="dark"
        />
      </>
    );
  }

  return (
    <div className="min-h-screen bg-dark-950">
      <header className="border-b border-dark-800 bg-dark-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🎬</span>
            <h1 className="text-xl font-bold bg-gradient-to-r from-primary-400 to-primary-600 bg-clip-text text-transparent">
                        MiniTaleStudio
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <p className="text-sm text-dark-400 hidden sm:block">
              AI Short Video Generation Platform
            </p>
            {ytConnected ? (
              <span className="px-3 py-1.5 bg-green-600/20 text-green-400 text-sm rounded-lg border border-green-600/30">
                YouTube Connected
              </span>
            ) : (
              <button
                onClick={handleYouTubeConnect}
                className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-sm rounded-lg transition-colors"
              >
                Connect YouTube
              </button>
            )}
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 bg-dark-800 hover:bg-dark-700 text-dark-300 hover:text-white text-sm rounded-lg border border-dark-600 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <main>
        <Dashboard />
      </main>

      <ToastContainer
        position="bottom-right"
        autoClose={4000}
        hideProgressBar={false}
        theme="dark"
      />
    </div>
  );
}

export default App;
