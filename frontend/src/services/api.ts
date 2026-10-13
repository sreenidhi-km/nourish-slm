import axios from 'axios';

// Set VITE_API_URL at build time (e.g. VITE_API_URL=/api for a reverse proxy).
const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Attach Authorization Token header dynamically
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('food_slm_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token if expired or invalid
      localStorage.removeItem('food_slm_token');
      localStorage.removeItem('food_slm_user');
      window.dispatchEvent(new Event('auth_logout'));
    }
    return Promise.reject(error);
  }
);
