// Voice Assistant Backend JavaScript
class VoiceAssistantAPI {
    constructor() {
        this.baseURL = window.location.origin;
        this.init();
    }

    init() {
        console.log('🎙️ Voice Assistant Backend Test Page - Loaded for Chirag');
        this.checkServerStatus();
        this.setupAutoRefresh();
        this.setupEventListeners();
    }

    // Server status management
    async checkServerStatus() {
        const statusDiv = document.getElementById('server-status');
        if (statusDiv) {
            statusDiv.classList.add('loading');
        }
        
        try {
            const response = await fetch(`${this.baseURL}/health`);
            const data = await response.json();
            
            if (statusDiv) {
                // Check for a successful HTTP response and the 'status' field in the JSON
                if (response.ok && data.status === 'healthy') { 
                    // Use the 'calendar_connected' value from the response
                    statusDiv.textContent = `🟢 Server Online - Calendar Connected: ${data.calendar_connected ? 'Yes' : 'No'}`;
                    statusDiv.className = 'status-indicator status-online';
                } else {
                    statusDiv.textContent = '🔴 Server Error';
                    statusDiv.className = 'status-indicator status-offline';
                }
            }
        } catch (error) {
            console.error('Server status check failed:', error);
            if (statusDiv) {
                statusDiv.textContent = '🔴 Server Offline';
                statusDiv.className = 'status-indicator status-offline';
            }
        } finally {
            if (statusDiv) {
                statusDiv.classList.remove('loading');
            }
        }
    }

    setupAutoRefresh() {
        // Auto-refresh server status every 30 seconds
        setInterval(() => {
            this.checkServerStatus();
        }, 30000);
    }

    setupEventListeners() {
        // Add keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                this.runAllTests();
            }
            if (e.ctrlKey && e.key === 'Delete') {
                this.clearAllResults();
            }
        });

        // Add enter key support for event creation
        const eventInput = document.getElementById('event-text');
        if (eventInput) {
            eventInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.testCreateEvent();
                }
            });
        }
    }

    // API testing methods
    async testEndpoint(url, method, resultId, data = null) {
        const resultDiv = document.getElementById(`result-${resultId}`);
        
        if (resultDiv) {
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = '⏳ Testing...';
            resultDiv.className = 'result loading';
        }

        try {
            const options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
            };

            if (data) {
                options.body = JSON.stringify(data);
            }

            const startTime = Date.now();
            const response = await fetch(`${this.baseURL}${url}`, options);
            const endTime = Date.now();
            const responseTime = endTime - startTime; // Fixed: Define responseTime here
            const result = await response.json();

            if (resultDiv) {
                const statusIcon = response.ok ? '✅' : '❌';
                
                resultDiv.innerHTML = `
                    <div><strong>${statusIcon} Status:</strong> ${response.status} (${responseTime}ms)</div>
                    <div><strong>Response:</strong></div>
                    <pre>${JSON.stringify(result, null, 2)}</pre>
                `;
                resultDiv.className = response.ok ? 'result success' : 'result error';
            }

            // Log API call
            console.log(`API Call: ${method} ${url}`, {
                status: response.status,
                responseTime: `${responseTime}ms`,
                data: result
            });

        } catch (error) {
            console.error(`API Error: ${method} ${url}`, error);
            
            if (resultDiv) {
                resultDiv.innerHTML = `<strong>❌ Error:</strong> ${error.message}`;
                resultDiv.className = 'result error';
            }
        } finally {
            if (resultDiv) {
                resultDiv.classList.remove('loading');
            }
        }
    }

    testCreateEvent() {
        const eventInput = document.getElementById('event-text');
        if (!eventInput) {
            console.error('Event input not found');
            return;
        }
        
        const eventText = eventInput.value.trim();
        
        if (!eventText) {
            alert('Please enter an event description');
            eventInput.focus();
            return;
        }

        this.testEndpoint('/api/calendar/create', 'POST', 'create-event', { event_text: eventText });
        
        // Clear input after submission
        eventInput.value = '';
    }

    testRescheduleEvent() {
        const eventId = document.getElementById('reschedule-event-id').value.trim();
        const newTime = document.getElementById('reschedule-new-time').value.trim();
        if (!eventId || !newTime) {
            alert('Please enter both an Event ID and a new start time');
            return;
        }
        this.testEndpoint(`/api/calendar/reschedule/${eventId}`, 'POST', 'reschedule-event', { new_start_time: newTime });
    }

    testCancelEvent() {
        const eventId = document.getElementById('cancel-event-id').value.trim();
        if (!eventId) {
            alert('Please enter an Event ID');
            return;
        }
        this.testEndpoint(`/api/calendar/cancel/${eventId}`, 'POST', 'cancel-event');
    }

    testFindMeetingSlots() {
        const duration = document.getElementById('find-slots-duration').value;
        const participants = document.getElementById('find-slots-participants').value;
        this.testEndpoint(`/api/calendar/find-slots?duration=${duration}&participants=${encodeURIComponent(participants)}`, 'GET', 'find-slots');
    }

    testSetEventReminder() {
        const eventId = document.getElementById('reminder-event-id').value.trim();
        const minutes = parseInt(document.getElementById('reminder-minutes').value, 10);
        if (!eventId || !minutes) {
            alert('Please enter an Event ID and the number of minutes');
            return;
        }
        this.testEndpoint(`/api/calendar/reminders/${eventId}`, 'POST', 'set-reminder', { minutes_before: minutes });
    }

    // Voice Input Test
    testVoiceInput() {
        const textInput = document.getElementById('voice-input-text');
        if (!textInput) {
            console.error('Voice input field not found');
            return;
        }
        
        const text = textInput.value.trim();
        
        if (!text) {
            alert('Please enter some text to send to the voice assistant');
            textInput.focus();
            return;
        }
        
        this.testEndpoint('/api/voice/input', 'POST', 'voice-input', { text: text });
        
        // Clear input after submission
        textInput.value = '';
    }
    
    showError(resultId, message) {
        const resultDiv = document.getElementById(`result-${resultId}`);
        if (resultDiv) {
            resultDiv.innerHTML = `<strong>❌ Error:</strong> ${message}`;
            resultDiv.className = 'result error';
            resultDiv.style.display = 'block';
        }
    }
    
    
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        // Style the notification
        Object.assign(notification.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '12px 24px',
            borderRadius: '8px',
            color: 'white',
            fontWeight: 'bold',
            zIndex: '1000',
            opacity: '0',
            transition: 'opacity 0.3s ease'
        });

        // Set background color based on type
        const colors = {
            success: '#28a745',
            error: '#dc3545',
            info: '#17a2b8',
            warning: '#ffc107'
        };
        notification.style.backgroundColor = colors[type] || colors.info;

        // Add to page
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.style.opacity = '1';
        }, 100);

        // Remove after 3 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                if (notification.parentNode) {
                    document.body.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }
}

// Global variables
let apiClient;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    apiClient = new VoiceAssistantAPI();
});

// Also handle the window.onload event (for backward compatibility)
window.onload = function() {
    if (!apiClient) {
        apiClient = new VoiceAssistantAPI();
    }
};

// Global functions for onclick handlers
function testEndpoint(url, method, resultId, data = null) {
    if (apiClient) {
        apiClient.testEndpoint(url, method, resultId, data);
    } else {
        console.error('API client not initialized');
    }
}

function testCreateEvent() {
    if (apiClient) {
        apiClient.testCreateEvent();
    } else {
        console.error('API client not initialized');
    }
}

function runAllTests() {
    if (apiClient) {
        apiClient.runAllTests();
    } else {
        console.error('API client not initialized');
    }
}

function clearAllResults() {
    if (apiClient) {
        apiClient.clearAllResults();
    } else {
        console.error('API client not initialized');
    }
}

// Voice input helper functions
function fillVoiceInput(text) {
    const textInput = document.getElementById('voice-input-text');
    if (textInput) {
        textInput.value = text;
        textInput.focus();
    }
}

function testVoiceInput() {
    if (apiClient) {
        apiClient.testVoiceInput();
    } else {
        console.error('API client not initialized');
    }
}

// WebSocket connection for real-time updates (optional enhancement)
class WebSocketClient {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
    }

    connect() {
        try {
            // Check if Socket.IO is available
            if (typeof io === 'undefined') {
                console.log('Socket.IO not available, skipping WebSocket connection');
                return;
            }

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/socket.io/`;
            
            this.socket = io(wsUrl);
            
            this.socket.on('connect', () => {
                console.log('🔌 WebSocket connected');
                this.reconnectAttempts = 0;
            });

            this.socket.on('disconnect', () => {
                console.log('🔌 WebSocket disconnected');
                this.attemptReconnect();
            });

            this.socket.on('calendar_update', (data) => {
                console.log('📅 Calendar update received:', data);
                if (apiClient) {
                    apiClient.showNotification('Calendar updated!', 'success');
                }
            });

            this.socket.on('voice_status', (data) => {
                console.log('🎙️ Voice status update:', data);
                if (apiClient) {
                    apiClient.showNotification(`Voice: ${data.status}`, 'info');
                }
            });

        } catch (error) {
            console.error('WebSocket connection failed:', error);
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            setTimeout(() => {
                console.log(`🔄 Attempting to reconnect... (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);
                this.reconnectAttempts++;
                this.connect();
            }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts));
        }
    }
}

// Initialize WebSocket connection after DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize WebSocket connection if Socket.IO is available
    if (typeof io !== 'undefined') {
        const wsClient = new WebSocketClient();
        wsClient.connect();
    }
});