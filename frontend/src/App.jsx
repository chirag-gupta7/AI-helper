import { useState, useEffect, useRef } from 'react';
import { socket } from "./services/socket.js";
import { rescheduleEvent, cancelEvent, findMeetingSlots, setEventReminder } from './services/api.js';
import './App.css';
import { Moon, Sun, Calendar, X, Search, Bell, Send, User, LogOut } from 'lucide-react';
import axios from 'axios';
import AuthModal from './components/AuthModal.jsx';

const App = () => {
    const [isConnected, setIsConnected] = useState(socket.connected);
    const [logs, setLogs] = useState([]);
    const [status, setStatus] = useState('Inactive');
    const [isListening, setIsListening] = useState(false);
    const [theme, setTheme] = useState('dark');
    const logBoxRef = useRef(null);

    // Authentication state
    const [user, setUser] = useState(null);
    const [showAuthModal, setShowAuthModal] = useState(false);
    const [authChecked, setAuthChecked] = useState(false);

    // State for new calendar features
    const [calendarActionFeedback, setCalendarActionFeedback] = useState({ message: '', type: '', data: null });
    const [rescheduleData, setRescheduleData] = useState({ eventId: '', newTime: '' });
    const [cancelData, setCancelData] = useState({ eventId: '' });
    const [findSlotsData, setFindSlotsData] = useState({ duration: '30', participants: 'primary', days: '7' });
    const [reminderData, setReminderData] = useState({ eventId: '', minutes: '30' });
    
    // State for the new simulated voice input
    const [simulatedTranscript, setSimulatedTranscript] = useState('');

    useEffect(() => {
        // Check for existing session
        checkAuthStatus();
        
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

    // Authentication functions
    const checkAuthStatus = async () => {
        try {
            const token = localStorage.getItem('session_token');
            const response = await fetch('/api/auth/session', {
                headers: token ? { 'Authorization': `Bearer ${token}` } : {}
            });
            
            const data = await response.json();
            
            if (data.success && data.data.authenticated) {
                setUser(data.data.user);
                addLog(`Welcome back, ${data.data.user.username}!`, 'success');
                // Now check voice status
                checkVoiceStatus();
            } else {
                setUser(null);
                localStorage.removeItem('session_token');
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            setUser(null);
            localStorage.removeItem('session_token');
        } finally {
            setAuthChecked(true);
        }
    };

    const checkVoiceStatus = async () => {
        try {
            const response = await fetchWithAuth('/api/voice/status');
            if (response.ok) {
                const text = await response.text();
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
            }
        } catch (error) {
            addLog(`Error fetching status: ${error.message}`, 'error');
            console.error("Error:", error);
        }
    };

    const fetchWithAuth = (url, options = {}) => {
        const token = localStorage.getItem('session_token');
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        return fetch(url, {
            ...options,
            headers
        });
    };

    const handleLogin = (userData) => {
        setUser(userData);
        addLog(`Welcome, ${userData.username}!`, 'success');
        // Check voice status after login
        setTimeout(checkVoiceStatus, 500);
    };

    const handleLogout = async () => {
        try {
            await fetchWithAuth('/api/auth/logout', { method: 'POST' });
            localStorage.removeItem('session_token');
            setUser(null);
            addLog('Logged out successfully', 'info');
        } catch (error) {
            console.error('Logout error:', error);
            // Clear local storage anyway
            localStorage.removeItem('session_token');
            setUser(null);
        }
    };

    const handleStart = async () => {
        if (isListening) return;
        
        if (!user) {
            addLog('Please log in to use voice assistant', 'error');
            setShowAuthModal(true);
            return;
        }
        
        try {
            addLog('Starting conversation...', 'status');
            
            const response = await fetchWithAuth('/api/voice/start', { 
                method: 'POST'
            });
            
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
        
        if (!user) {
            addLog('Please log in to use voice assistant', 'error');
            return;
        }
        
        try {
            addLog('Stopping conversation...', 'status');
            
            const response = await fetchWithAuth('/api/voice/stop', { 
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (response.ok) {
                addLog(data.message || 'Voice assistant stopped', 'success');
                setStatus('Inactive');
                setIsListening(false);
            } else {
                addLog(`Error: ${data.error || 'Unknown error'}`, 'error');
                setStatus('Inactive');
                setIsListening(false);
            }
        } catch (error) {
            addLog(`Network error: ${error.message}`, 'error');
            setStatus('Error');
            setIsListening(false);
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
        
        if (!user) {
            setCalendarActionFeedback({ message: 'Please log in to use calendar features', type: 'error' });
            setShowAuthModal(true);
            return;
        }
        
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
        
        if (!user) {
            setCalendarActionFeedback({ message: 'Please log in to use calendar features', type: 'error' });
            setShowAuthModal(true);
            return;
        }
        
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
        
        if (!user) {
            setCalendarActionFeedback({ message: 'Please log in to use calendar features', type: 'error' });
            setShowAuthModal(true);
            return;
        }
        
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
        
        if (!user) {
            setCalendarActionFeedback({ message: 'Please log in to use calendar features', type: 'error' });
            setShowAuthModal(true);
            return;
        }
        
        setCalendarActionFeedback({ message: 'Setting reminder...', type: 'loading' });
        try {
            const response = await setEventReminder(reminderData.eventId, parseInt(reminderData.minutes, 10));
            setCalendarActionFeedback({ message: response.data.message || 'Reminder set!', type: 'success', data: response.data.data });
        } catch (error) {
            const errorMessage = error.response?.data?.error || error.message;
            setCalendarActionFeedback({ message: `Error: ${errorMessage}`, type: 'error' });
        }
    };

    const handleSimulateTranscript = async (e) => {
        e.preventDefault();
        
        if (!user) {
            addLog('Please log in to send voice input', 'error');
            setShowAuthModal(true);
            return;
        }
        
        addLog(`Sending voice input: "${simulatedTranscript}"`, 'info');
        try {
            const response = await fetchWithAuth('/api/voice/input', {
                method: 'POST',
                body: JSON.stringify({ text: simulatedTranscript })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                addLog(`Voice input sent: ${data.message}`, 'success');
            } else {
                addLog(`Error sending voice input: ${data.error}`, 'error');
            }
        } catch (error) {
            const errorMessage = error.message;
            addLog(`Error sending voice input: ${errorMessage}`, 'error');
        }
        setSimulatedTranscript('');
    };

    const getStatusClass = () => {
        if (status === 'Listening...') return 'status-active';
        if (status === 'Error') return 'status-error';
        return 'status-inactive';
    };

    // Show loading while checking auth
    if (!authChecked) {
        return (
            <div className="App">
                <div className="auth-loading">
                    <h2>Loading...</h2>
                    <p>Checking authentication status...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="App">
            <header className="App-header">
                <h1>Voice Assistant Control Panel</h1>
                <div className="header-info">
                    <p className={`status-indicator ${getStatusClass()}`}>
                        Status: {status}
                    </p>
                    <div className="auth-info">
                        {user ? (
                            <div className="user-info">
                                <span>Welcome, {user.username}!</span>
                                <button onClick={handleLogout} className="logout-btn">
                                    <LogOut size={16} />
                                    Logout
                                </button>
                            </div>
                        ) : (
                            <button onClick={() => setShowAuthModal(true)} className="login-btn">
                                <User size={16} />
                                Sign In
                            </button>
                        )}
                    </div>
                </div>
                <button onClick={toggleTheme} className="theme-toggle">
                    {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
                </button>
            </header>

            <main className="main-content">
                {!user ? (
                    <div className="auth-required">
                        <div className="auth-required-content">
                            <User size={48} />
                            <h2>Authentication Required</h2>
                            <p>Please sign in to use the Voice Assistant features.</p>
                            <button onClick={() => setShowAuthModal(true)} className="auth-cta-btn">
                                Sign In Now
                            </button>
                        </div>
                    </div>
                ) : (
                    <>
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
                            
                            <form onSubmit={handleSimulateTranscript} className="action-form" style={{ marginTop: '2rem' }}>
                                <label><Send size={16} /> Send Simulated Transcript</label>
                                <input
                                    type="text"
                                    placeholder={isListening ? "Type a command here..." : "Start the assistant first"}
                                    value={simulatedTranscript}
                                    onChange={(e) => setSimulatedTranscript(e.target.value)}
                                    disabled={!isListening}
                                    required
                                />
                                <button type="submit" disabled={!isListening}><Send size={14} /></button>
                            </form>
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
                    </>
                )}
            </main>
            
            <footer className="App-footer">
                <p>Connection status: <span className={isConnected ? 'connected' : 'disconnected'}>
                    {isConnected ? 'Connected' : 'Disconnected'}
                </span></p>
                <p>© 2025 Chirag Gupta's Voice Assistant</p>
            </footer>

            <AuthModal
                isOpen={showAuthModal}
                onClose={() => setShowAuthModal(false)}
                onLogin={handleLogin}
            />
        </div>
    );
};

export default App;
