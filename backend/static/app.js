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

// Global variables removed (moved to end of file)

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (!apiClient) {
        apiClient = new VoiceAssistantAPI();
    }
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

// Voice Assistant Manager
class VoiceAssistantManager {
    constructor() {
        this.isActive = false;
        this.isLoading = false;
        this.baseURL = window.location.origin;
        this.init();
    }

    init() {
        this.updateUI();
        this.checkInitialStatus();
    }

    async checkInitialStatus() {
        try {
            const response = await fetch(`${this.baseURL}/api/voice/status`);
            const data = await response.json();
            if (data.success && data.data) {
                this.isActive = data.data.is_listening;
                this.updateUI();
            }
        } catch (error) {
            console.error('Failed to check voice assistant status:', error);
        }
    }

    updateUI() {
        const statusIndicator = document.getElementById('voice-status-indicator');
        const statusIcon = statusIndicator?.querySelector('.status-icon');
        const statusText = statusIndicator?.querySelector('.status-text');
        const startBtn = document.getElementById('start-voice-btn');
        const stopBtn = document.getElementById('stop-voice-btn');
        const voiceInputSection = document.getElementById('voice-input-section');
        const voiceInputStatusText = document.getElementById('voice-input-status-text');
        const voiceInputText = document.getElementById('voice-input-text');
        const sendVoiceBtn = document.getElementById('send-voice-btn');
        const exampleBtns = document.querySelectorAll('.example-btn');

        if (this.isLoading) {
            // Loading state
            statusIndicator?.setAttribute('class', 'voice-status-indicator status-starting');
            if (statusIcon) statusIcon.textContent = '🟡';
            if (statusText) statusText.textContent = 'Voice Assistant: Starting...';
            if (startBtn) startBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = true;
        } else if (this.isActive) {
            // Active state
            statusIndicator?.setAttribute('class', 'voice-status-indicator status-active');
            if (statusIcon) statusIcon.textContent = '🟢';
            if (statusText) statusText.textContent = 'Voice Assistant: Active & Listening';
            if (startBtn) startBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = false;
            
            // Enable voice input section
            voiceInputSection?.setAttribute('class', 'voice-input-section');
            if (voiceInputStatusText) voiceInputStatusText.textContent = '✅ Voice assistant is ready for input';
            if (voiceInputText) voiceInputText.disabled = false;
            if (sendVoiceBtn) sendVoiceBtn.disabled = false;
            exampleBtns.forEach(btn => btn.disabled = false);
        } else {
            // Inactive state
            statusIndicator?.setAttribute('class', 'voice-status-indicator status-inactive');
            if (statusIcon) statusIcon.textContent = '🔴';
            if (statusText) statusText.textContent = 'Voice Assistant: Inactive';
            if (startBtn) startBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = true;
            
            // Disable voice input section
            voiceInputSection?.setAttribute('class', 'voice-input-section disabled');
            if (voiceInputStatusText) voiceInputStatusText.textContent = '⚠️ Please start the voice assistant first';
            if (voiceInputText) voiceInputText.disabled = true;
            if (sendVoiceBtn) sendVoiceBtn.disabled = true;
            exampleBtns.forEach(btn => btn.disabled = true);
        }
    }

    async startVoice() {
        if (this.isLoading || this.isActive) return;
        
        this.isLoading = true;
        this.updateUI();
        
        const startTime = new Date().getTime();
        
        try {
            const response = await fetch(`${this.baseURL}/api/voice/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            const responseTime = new Date().getTime() - startTime;
            
            const resultDiv = document.getElementById('result-voice-controls');
            if (resultDiv) {
                resultDiv.style.display = 'block';
                if (data.success) {
                    this.isActive = true;
                    resultDiv.innerHTML = `
                        <div class="success-status">
                            <strong>✅ Status:</strong> 200 (${responseTime}ms)
                        </div>
                        <strong>Response:</strong>
                        <div class="response-data">${JSON.stringify(data)}</div>
                    `;
                    resultDiv.className = 'result success';
                    this.showNotification('Voice assistant started successfully!', 'success');
                } else {
                    resultDiv.innerHTML = `
                        <div class="error-status">
                            <strong>❌ Error:</strong> ${data.error || 'Failed to start voice assistant'}
                        </div>
                    `;
                    resultDiv.className = 'result error';
                    this.showNotification('Failed to start voice assistant', 'error');
                }
            }
        } catch (error) {
            console.error('Error starting voice assistant:', error);
            this.showNotification('Network error starting voice assistant', 'error');
        } finally {
            this.isLoading = false;
            this.updateUI();
        }
    }

    async stopVoice() {
        if (this.isLoading || !this.isActive) return;
        
        this.isLoading = true;
        this.updateUI();
        
        const startTime = new Date().getTime();
        
        try {
            const response = await fetch(`${this.baseURL}/api/voice/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            const responseTime = new Date().getTime() - startTime;
            
            const resultDiv = document.getElementById('result-voice-controls');
            if (resultDiv) {
                resultDiv.style.display = 'block';
                if (data.success) {
                    this.isActive = false;
                    resultDiv.innerHTML = `
                        <div class="success-status">
                            <strong>✅ Status:</strong> 200 (${responseTime}ms)
                        </div>
                        <strong>Response:</strong>
                        <div class="response-data">${JSON.stringify(data)}</div>
                    `;
                    resultDiv.className = 'result success';
                    this.showNotification('Voice assistant stopped successfully!', 'success');
                } else {
                    resultDiv.innerHTML = `
                        <div class="error-status">
                            <strong>❌ Error:</strong> ${data.error || 'Failed to stop voice assistant'}
                        </div>
                    `;
                    resultDiv.className = 'result error';
                    this.showNotification('Failed to stop voice assistant', 'error');
                }
            }
        } catch (error) {
            console.error('Error stopping voice assistant:', error);
            this.showNotification('Network error stopping voice assistant', 'error');
        } finally {
            this.isLoading = false;
            this.updateUI();
        }
    }

    async sendVoiceInput() {
        if (!this.isActive) {
            this.showNotification('Please start the voice assistant first', 'error');
            return;
        }

        const textInput = document.getElementById('voice-input-text');
        if (!textInput) {
            console.error('Voice input field not found');
            return;
        }
        
        const text = textInput.value.trim();
        if (!text) {
            this.showNotification('Please enter some text to send to the voice assistant', 'error');
            textInput.focus();
            return;
        }
        
        const sendBtn = document.getElementById('send-voice-btn');
        const originalText = sendBtn?.textContent;
        
        try {
            if (sendBtn) {
                sendBtn.disabled = true;
                sendBtn.innerHTML = '<span class="loading-spinner"></span>Sending...';
            }
            
            const startTime = new Date().getTime();
            const response = await fetch(`${this.baseURL}/api/voice/input`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            });
            
            const responseTime = new Date().getTime() - startTime;
            const data = await response.json();
            
            const resultDiv = document.getElementById('result-voice-input');
            if (resultDiv) {
                resultDiv.style.display = 'block';
                if (data.success) {
                    resultDiv.innerHTML = `
                        <div class="success-status">
                            <strong>✅ Status:</strong> ${response.status} (${responseTime}ms)
                        </div>
                        <strong>Response:</strong>
                        <div class="response-data">${JSON.stringify(data)}</div>
                    `;
                    resultDiv.className = 'result success';
                    this.showNotification('Voice input processed successfully!', 'success');
                    textInput.value = ''; // Clear input after successful submission
                } else {
                    resultDiv.innerHTML = `
                        <div class="error-status">
                            <strong>❌ Status:</strong> ${response.status} (${responseTime}ms)
                        </div>
                        <strong>Response:</strong>
                        <div class="response-data">${JSON.stringify(data)}</div>
                    `;
                    resultDiv.className = 'result error';
                }
            }
        } catch (error) {
            console.error('Error sending voice input:', error);
            this.showNotification('Network error sending voice input', 'error');
        } finally {
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.textContent = originalText || 'Send Voice Input';
            }
        }
    }

    fillVoiceInput(text) {
        const textInput = document.getElementById('voice-input-text');
        if (textInput) {
            textInput.value = text;
            textInput.focus();
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
        notification.style.background = colors[type] || colors.info;

        // Add to page
        document.body.appendChild(notification);
        
        // Fade in
        setTimeout(() => notification.style.opacity = '1', 100);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => document.body.removeChild(notification), 300);
        }, 3000);
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

// Global instances
let apiClient;
let voiceAssistant;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    apiClient = new VoiceAssistantAPI();
    voiceAssistant = new VoiceAssistantManager();
});