import { useState, useEffect, useRef } from 'react';
import { socket } from "./services/socket.js";
import { rescheduleEvent, cancelEvent, findMeetingSlots, setEventReminder } from './services/api.js';
import './App.css';
import { Moon, Sun, Calendar, X, Search, Bell, Send } from 'lucide-react';

const App = () => {
    const [isConnected, setIsConnected] = useState(socket.connected);
    const [logs, setLogs] = useState([]);
    const [status, setStatus] = useState('Inactive');
    const [isListening, setIsListening] = useState(false);
    const [theme, setTheme] = useState('dark');
    const logBoxRef = useRef(null);

    // State for new calendar features
    const [calendarActionFeedback, setCalendarActionFeedback] = useState({ message: '', type: '', data: null });
    const [rescheduleData, setRescheduleData] = useState({ eventId: '', newTime: '' });
    const [cancelData, setCancelData] = useState({ eventId: '' });
    const [findSlotsData, setFindSlotsData] = useState({ duration: '30', participants: 'primary', days: '7' });
    const [reminderData, setReminderData] = useState({ eventId: '', minutes: '30' });


    useEffect(() => {
        const onConnect = () => {
            setIsConnected(true);
            addLog('Connected to server', 'success');
        };

        const onDisconnect = () => {
            setIsConnected(false);
            addLog('Disconnected from server', 'error');
            setStatus('Error');
        };

        const onLog = (data) => {
            addLog(data.message, data.level);
        };

        const onStatusUpdate = (data) => {
            setStatus(data.status);
            if (data.status === 'Listening...') {
                setIsListening(true);
            } else if (data.status === 'Inactive' || data.status === 'Error') {
                setIsListening(false);
            }
        };
        
        const onVoiceError = (data) => {
            addLog(`Voice Error: ${data.error}`, 'error');
            setStatus('Error');
            setIsListening(false);
        };

        socket.on('connect', onConnect);
        socket.on('disconnect', onDisconnect);
        socket.on('log', onLog);
        socket.on('status_update', onStatusUpdate);
        socket.on('voice_error', onVoiceError);
        socket.on('voice_status', onStatusUpdate);

        // Initial status check
        fetch('/api/voice/status')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.text();
            })
            .then(text => {
                try {
                    const data = JSON.parse(text);
                    if (data.data) {
                        setIsListening(data.data.is_listening || false);
                        setStatus(data.data.status || 'Inactive');
                    }
                } catch (e) {
                    addLog(`Error parsing status: ${e.message}`, 'error');
                    console.error("Failed to parse JSON:", text);
                }
            })
            .catch(error => {
                addLog(`Error fetching status: ${error.message}`, 'error');
                console.error("Error:", error);
            });

        return () => {
            socket.off('connect', onConnect);
            socket.off('disconnect', onDisconnect);
            socket.off('log', onLog);
            socket.off('status_update', onStatusUpdate);
            socket.off('voice_error', onVoiceError);
            socket.off('voice_status', onStatusUpdate);
        };
    }, []);

    useEffect(() => {
        // Scroll to the bottom of the log box
        if (logBoxRef.current) {
            logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
        }
    }, [logs]);
    
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
    }, [theme]);

    const addLog = (message, level = 'info') => {
        const newLog = {
            timestamp: new Date().toLocaleTimeString(),
            message,
            level,
        };
        setLogs(prevLogs => [...prevLogs, newLog]);
    };

    const handleStart = async () => {
        if (isListening) return;
        try {
            addLog('Starting conversation...', 'status');
            
            const response = await fetch('/api/voice/start', { 
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            });
            
            // Check if response is JSON
            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                const text = await response.text();
                addLog(`Server returned non-JSON response: ${text.substring(0, 100)}...`, 'error');
                setStatus('Error');
                return;
            }
            
            const data = await response.json();
            
            if (response.ok) {
                addLog(data.message || 'Voice assistant started', 'success');
                setStatus('Listening...');
                setIsListening(true);
            } else {
                addLog(`Error: ${data.error || 'Unknown error'}`, 'error');
                setStatus('Error');
            }
        } catch (error) {
            addLog(`Network error: ${error.message}`, 'error');
            setStatus('Error');
        }
    };

    const handleStop = async () => {
        if (!isListening) return;
        try {
            addLog('Stopping conversation...', 'status');
            
            const response = await fetch('/api/voice/stop', { 
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                } 
            });
            
            // Check if response is JSON
            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                const text = await response.text();
                addLog(`Server returned non-JSON response: ${text.substring(0, 100)}...`, 'error');
                setStatus('Inactive');  // Set to inactive anyway
                setIsListening(false);
                return;
            }
            
            const data = await response.json();
            
            if (response.ok) {
                addLog(data.message || 'Voice assistant stopped', 'success');
                setStatus('Inactive');
                setIsListening(false);
            } else {
                addLog(`Error: ${data.error || 'Unknown error'}`, 'error');
                setStatus('Inactive');  // Set to inactive anyway
                setIsListening(false);
            }
        } catch (error) {
            addLog(`Network error: ${error.message}`, 'error');
            setStatus('Error');
            setIsListening(false);  // Set to inactive anyway
        }
    };
    
    const toggleTheme = () => {
        setTheme(prevTheme => (prevTheme === 'dark' ? 'light' : 'dark'));
    };

    // Handlers for new calendar features
    const handleCalendarInputChange = (setter) => (e) => {
        const { name, value } = e.target;
        setter(prev => ({ ...prev, [name]: value }));
    };

    const handleReschedule = async (e) => {
        e.preventDefault();
        setCalendarActionFeedback({ message: 'Rescheduling...', type: 'loading' });
        try {
            const response = await rescheduleEvent(rescheduleData.eventId, rescheduleData.newTime);
            setCalendarActionFeedback({ message: response.data.message || 'Event rescheduled!', type: 'success', data: response.data.data });
        } catch (error) {
            const errorMessage = error.response?.data?.error || error.message;
            setCalendarActionFeedback({ message: `Error: ${errorMessage}`, type: 'error' });
        }
    };

    const handleCancel = async (e) => {
        e.preventDefault();
        setCalendarActionFeedback({ message: 'Canceling...', type: 'loading' });
        try {
            const response = await cancelEvent(cancelData.eventId);
            setCalendarActionFeedback({ message: response.data.message || 'Event canceled!', type: 'success', data: response.data.data });
        } catch (error) {
            const errorMessage = error.response?.data?.error || error.message;
            setCalendarActionFeedback({ message: `Error: ${errorMessage}`, type: 'error' });
        }
    };

    const handleFindSlots = async (e) => {
        e.preventDefault();
        setCalendarActionFeedback({ message: 'Finding slots...', type: 'loading' });
        try {
            const response = await findMeetingSlots(findSlotsData.duration, findSlotsData.participants, findSlotsData.days);
            setCalendarActionFeedback({ message: response.data.message || 'Slots found!', type: 'success', data: response.data.data.slots });
        } catch (error) {
            const errorMessage = error.response?.data?.error || error.message;
            setCalendarActionFeedback({ message: `Error: ${errorMessage}`, type: 'error' });
        }
    };

    const handleSetReminder = async (e) => {
        e.preventDefault();
        setCalendarActionFeedback({ message: 'Setting reminder...', type: 'loading' });
        try {
            const response = await setEventReminder(reminderData.eventId, parseInt(reminderData.minutes, 10));
            setCalendarActionFeedback({ message: response.data.message || 'Reminder set!', type: 'success', data: response.data.data });
        } catch (error) {
            const errorMessage = error.response?.data?.error || error.message;
            setCalendarActionFeedback({ message: `Error: ${errorMessage}`, type: 'error' });
        }
    };


    const getStatusClass = () => {
        if (status === 'Listening...') return 'status-active';
        if (status === 'Error') return 'status-error';
        return 'status-inactive';
    };

    return (
        <div className="App">
            <header className="App-header">
                <h1>Voice Assistant Control Panel</h1>
                <p className={`status-indicator ${getStatusClass()}`}>
                    Status: {status}
                </p>
                <button onClick={toggleTheme} className="theme-toggle">
                    {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
                </button>
            </header>

            <main className="main-content">
                <div className="voice-controls-container">
                    <h2>Voice Controls</h2>
                    <div className="controls">
                        <button 
                            onClick={handleStart} 
                            disabled={isListening}
                            className={`control-button ${isListening ? 'disabled' : 'start'}`}
                        >
                            Start Conversation
                        </button>
                        <button 
                            onClick={handleStop} 
                            disabled={!isListening}
                            className={`control-button ${!isListening ? 'disabled' : 'stop'}`}
                        >
                            Stop Conversation
                        </button>
                    </div>
                </div>

                <div className="calendar-actions-container">
                    <h2>Calendar Actions</h2>
                    <div className="action-forms">
                        {/* Reschedule Event */}
                        <form onSubmit={handleReschedule} className="action-form">
                            <label><Calendar size={16} /> Reschedule Event</label>
                            <input type="text" name="eventId" placeholder="Event ID" value={rescheduleData.eventId} onChange={handleCalendarInputChange(setRescheduleData)} required />
                            <input type="text" name="newTime" placeholder="New ISO Start Time" value={rescheduleData.newTime} onChange={handleCalendarInputChange(setRescheduleData)} required />
                            <button type="submit"><Send size={14} /></button>
                        </form>

                        {/* Cancel Event */}
                        <form onSubmit={handleCancel} className="action-form">
                            <label><X size={16} /> Cancel Event</label>
                            <input type="text" name="eventId" placeholder="Event ID" value={cancelData.eventId} onChange={handleCalendarInputChange(setCancelData)} required />
                            <button type="submit"><Send size={14} /></button>
                        </form>

                        {/* Find Slots */}
                        <form onSubmit={handleFindSlots} className="action-form">
                            <label><Search size={16} /> Find Meeting Slots</label>
                            <input type="number" name="duration" placeholder="Duration (mins)" value={findSlotsData.duration} onChange={handleCalendarInputChange(setFindSlotsData)} required />
                            <input type="text" name="participants" placeholder="Participants (comma-sep)" value={findSlotsData.participants} onChange={handleCalendarInputChange(setFindSlotsData)} />
                            <button type="submit"><Send size={14} /></button>
                        </form>

                        {/* Set Reminder */}
                        <form onSubmit={handleSetReminder} className="action-form">
                            <label><Bell size={16} /> Set Reminder</label>
                            <input type="text" name="eventId" placeholder="Event ID" value={reminderData.eventId} onChange={handleCalendarInputChange(setReminderData)} required />
                            <input type="number" name="minutes" placeholder="Minutes Before" value={reminderData.minutes} onChange={handleCalendarInputChange(setReminderData)} required />
                            <button type="submit"><Send size={14} /></button>
                        </form>
                    </div>
                    {calendarActionFeedback.message && (
                        <div className={`feedback-box feedback-${calendarActionFeedback.type}`}>
                            <p>{calendarActionFeedback.message}</p>
                            {calendarActionFeedback.data && (
                                <pre>{JSON.stringify(calendarActionFeedback.data, null, 2)}</pre>
                            )}
                        </div>
                    )}
                </div>

                <div className="log-container">
                    <h2>Conversation Log</h2>
                    <div className="log-box" ref={logBoxRef}>
                        {logs.length > 0 ? logs.map((log, index) => (
                            <div key={index} className={`log-entry log-${log.level}`}>
                                <span className="log-timestamp">{log.timestamp}</span>
                                <span className="log-message">{log.message}</span>
                            </div>
                        )) : <p className="log-placeholder">No logs yet. Start a conversation!</p>}
                    </div>
                </div>
            </main>
            <footer className="App-footer">
                <p>Connection status: <span className={isConnected ? 'connected' : 'disconnected'}>
                    {isConnected ? 'Connected' : 'Disconnected'}
                </span></p>
                <p>© 2025 Chirag Gupta's Voice Assistant</p>
            </footer>
        </div>
    );
};

export default App;