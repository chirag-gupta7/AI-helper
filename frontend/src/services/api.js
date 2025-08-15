import axios from 'axios';

// Create axios instance
export const api = axios.create({
  baseURL: import.meta.env.DEV ? 'http://localhost:5000' : '/',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('session_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear invalid token
      localStorage.removeItem('session_token');
      // Optionally redirect to login or trigger re-auth
      console.warn('Authentication failed, token cleared');
    }
    return Promise.reject(error);
  }
);

export const rescheduleEvent = (eventId, newStartTime) => {
  return api.post(`/api/calendar/reschedule/${eventId}`, { new_start_time: newStartTime });
};

export const cancelEvent = (eventId) => {
  return api.post(`/api/calendar/cancel/${eventId}`);
};

export const findMeetingSlots = (duration, participants, days) => {
  return api.get('/api/calendar/find-slots', { params: { duration, participants, days } });
};

export const setEventReminder = (eventId, minutesBefore) => {
  return api.post(`/api/calendar/reminders/${eventId}`, { minutes_before: minutesBefore });
};