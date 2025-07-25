# AI Voice Assistant

This project is a full-stack AI Voice Assistant with a Python-based backend and a React-based frontend. The assistant can understand voice commands, interact with external services like Google Calendar, and provide real-time feedback through a web interface.

## Table of Contents

- [Project Overview & Description](#project-overview--description)
- [Key Features & Capabilities](#key-features--capabilities)
- [Technical Architecture](#technical-architecture)
- [Installation & Setup](#installation--setup)
- [Usage Examples](#usage-examples)
- [Contributing & Development](#contributing--development)
- [Future Roadmap](#future-roadmap)

## Project Overview & Description

The AI Voice Assistant is designed to provide a hands-free interface for managing tasks and retrieving information. It leverages speech recognition and natural language processing to understand user commands and perform actions, such as managing your Google Calendar. The web-based frontend serves as a control panel and a visual feedback mechanism, showing the assistant's status in real-time.

This project is for anyone interested in voice-controlled applications, AI/ML integration, or full-stack Python and JavaScript development.

## Key Features & Capabilities

- **Voice Command Recognition**: Listens for and processes voice commands.
- **Google Calendar Integration**: Fetches and displays upcoming events from your Google Calendar.
- **Real-time Communication**: Uses WebSockets for instant communication between the frontend and backend.
- **Web-based Control Panel**: An intuitive UI to start, stop, and monitor the voice assistant.

## Technical Architecture

The project is structured as a monorepo with two main components: a Python backend and a React frontend.

-   **Backend**:
    -   **Framework**: Flask
    -   **Real-time Communication**: Flask-SocketIO
    -   **Key Libraries**:
        -   `SpeechRecognition` for converting speech to text.
        -   `pyttsx3` for text-to-speech conversion.
        -   `google-api-python-client` for Google Calendar integration.
    -   **Authentication**: OAuth 2.0 for Google Calendar API access.

-   **Frontend**:
    -   **Framework**: React
    -   **Build Tool**: Vite
    -   **Real-time Communication**: `socket.io-client`
    -   **API Communication**: Axios

## Installation & Setup

### Prerequisites

-   Python 3.x
-   Node.js and npm
-   Git

### Backend Setup

1.  **Navigate to the backend directory**:
    ```bash
    cd backend
    ```

2.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up Google Calendar API Credentials**:
    -   Follow the [Google Calendar API Python Quickstart](https://developers.google.com/calendar/api/quickstart/python) to enable the API and download your `credentials.json` file.
    -   Place the `credentials.json` file in the `backend` directory.
    -   The first time you run the application, you will be prompted to authorize access to your Google account. This will create a `token.pickle` file for future authentications.

4.  **Run the backend server**:
    ```bash
    python app.py
    ```
    The backend will be running at `http://localhost:5000`.

### Frontend Setup

1.  **Navigate to the frontend directory**:
    ```bash
    cd frontend
    ```

2.  **Install Node.js dependencies**:
    ```bash
    npm install
    ```

3.  **Run the frontend development server**:
    ```bash
    npm run dev
    ```
    The frontend will be accessible at `http://localhost:5173` (or another port if 5173 is busy).

## Usage Examples

1.  Ensure both the backend and frontend servers are running.
2.  Open your browser and navigate to the frontend URL (e.g., `http://localhost:5173`).
3.  Click the **"Start Voice Chat"** button to activate the assistant.
4.  The assistant will greet you. You can then issue commands like:
    -   "What's on my calendar?"
    -   "Hello"
5.  The assistant's responses and status updates will appear in the activity log on the web page.
6.  Click the **"Stop Voice Chat"** button to deactivate the assistant.

## Contributing & Development

Contributions are welcome! If you have suggestions for improvements or want to fix a bug, please follow these steps:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'Add some feature'`).
5.  Push to the branch (`git push origin feature/your-feature-name`).
6.  Open a Pull Request.

Please adhere to the existing code style and add comments where necessary.

## Future Roadmap

-   **Add more voice commands**: Expand the range of tasks the assistant can perform (e.g., weather forecasts, news updates, sending emails).
-   **Support for more languages**: Implement multi-language support for both speech recognition and text-to-speech.
-   **Enhanced AI models**: Integrate more advanced NLP/NLU models for better conversational abilities.
-   **Database Integration**: Add a database to store user preferences and conversation history.
-   **Improved UI/UX**: Enhance the frontend with more visualizations and controls.