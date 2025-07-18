import { useState, useEffect, useRef } from 'react';
import { socket } from "./services/socket.js";
import './App.css';
import { Moon, Sun } from 'lucide-react';

const App = () => {
    const [isConnected, setIsConnected] = useState(socket.connected);
    const [logs, setLogs] = useState([]);
    const [status, setStatus] = useState('Inactive');
    const [isListening, setIsListening] = useState(false);
    const [theme, setTheme] = useState('dark');
    const logBoxRef = useRef(null);

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

            <div className="controls">
                <button 
                    onClick={handleStart} 
                    disabled={isListening}
                    className={isListening ? 'disabled' : 'active'}
                >
                    Start Conversation
                </button>
                <button 
                    onClick={handleStop} 
                    disabled={!isListening}
                    className={!isListening ? 'disabled' : 'active'}
                >
                    Stop Conversation
                </button>
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