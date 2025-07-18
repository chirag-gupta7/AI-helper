# Voice Assistant Frontend

This project is a voice assistant frontend application built using React. It provides a control panel for managing a voice assistant, allowing users to start and stop the assistant and view real-time status updates.

## Project Structure

```
voice-assistant-frontend
├── public
│   └── index.html          # Main HTML file serving as the entry point
├── src
│   ├── services
│   │   ├── api.js         # Axios instance for API communication
│   │   └── socket.js      # Socket.IO client for real-time communication
│   ├── App.css            # CSS styles for the main App component
│   ├── App.jsx            # Main React component for the application
│   ├── index.css          # Global CSS styles for the application
│   └── main.jsx           # Entry point for the React application
├── package.json            # Configuration file for npm
├── vite.config.js         # Configuration file for Vite
└── README.md              # Documentation for the project
```

## Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd voice-assistant-frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Run the application**:
   ```bash
   npm run dev
   ```

4. **Open your browser** and navigate to `http://localhost:3000` (or the port specified in your terminal) to view the application.

## Usage

- Use the "Start Voice Chat" button to activate the voice assistant.
- Use the "Stop Voice Chat" button to deactivate the voice assistant.
- Monitor the activity log for real-time updates on the voice assistant's status.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.