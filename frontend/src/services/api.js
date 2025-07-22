import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.DEV ? 'http://localhost:5000' : '/',
  headers: {
    'Content-Type': 'application/json',
  },
});

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