import datetime
import os
import webbrowser
import openai
import re
import threading
import smtplib
import subprocess
import platform
import glob
from urllib.parse import quote
import pyautogui
import pyaudio
import streamlit as st
import speech_recognition as sr
import pyttsx3
import time
import pytz
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pygame

try:
    import pygame.camera
except ImportError:
    pass  # Handle systems without pygame.camera

# --- Global Variables ---
using_terminator = False
take_picture_flag = {"capture": False}
camera_running = False
searching = True
listening_for_interrupt = False
stop_speaking = False
expecting_code = False
conversation_history = []

# --- Streamlit UI Configuration ---
st.set_page_config(page_title="🎙 SAGE Assistant", layout="centered", page_icon="🤖")

# --- CUSTOM CSS ---
st.markdown("""
<style>
/* Background gradient */
body, .stApp {
    background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460);
    background-attachment: fixed;
    color: white;
    font-family: 'Segoe UI', sans-serif;
}

/* Glass effect container */
section.main > div {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 30px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    margin-bottom: 20px;
}

/* Typing animation */
.typing {
  width: 100%;
  white-space: nowrap;
  overflow: hidden;
  border-right: 3px solid #ff8c00;
  animation: typing 3s steps(40, end), blink .75s step-end infinite;
  font-size: 20px;
  font-weight: bold;
  font-family: monospace;
  color: white;
  margin: 10px 0;
}
@keyframes typing {
  from { width: 0 }
  to { width: 100% }
}
@keyframes blink {
  50% { border-color: transparent }
}

/* Button styling */
button[kind="primary"] {
    background: linear-gradient(135deg, #0099cc, #0077b6) !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 10px 20px !important;
    font-weight: bold !important;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2) !important;
    transition: all 0.3s ease !important;
    display: flex; 
    justify-content: center;
    margin: 10px auto;
    width: 100%;
}
button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3) !important;
}

/* Chat bubbles */
.user-message {
    background: rgba(0, 180, 219, 0.2);
    padding: 12px 16px;
    border-radius: 18px 18px 0 18px;
    margin: 8px 0;
    max-width: 80%;
    margin-left: auto;
    border: 1px solid rgba(0, 180, 219, 0.5);
}
.assistant-message {
    background: rgba(255, 140, 0, 0.2);
    padding: 12px 16px;
    border-radius: 18px 18px 18px 0;
    margin: 8px 0;
    max-width: 80%;
    margin-right: auto;
    border: 1px solid rgba(255, 140, 0, 0.5);
}

/* Status indicators */
.status-indicator {
    display: flex;
    align-items: center;
    margin: 10px 0;
    padding: 8px 12px;
    border-radius: 20px;
    background: rgba(0, 0, 0, 0.2);
}
.status-light {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 10px;
}
.listening {
    background: #00ff00;
    box-shadow: 0 0 10px #00ff00;
}
.processing {
    background: #ff8c00;
    box-shadow: 0 0 10px #ff8c00;
}
.idle {
    background: #cccccc;
}

/* Footer */
.footer {
    position: fixed;
    bottom: 0;
    width: 100%;
    text-align: center;
    padding: 10px;
    background: rgba(0, 0, 0, 0.3);
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)

# --- Initialize Text-to-Speech Engine ---
engine = pyttsx3.init()
voices = engine.getProperty('voices')
preferred_voice_index = 1 if len(voices) > 1 else 0
engine.setProperty('voice', voices[preferred_voice_index].id)
engine.setProperty('rate', 170)

# --- UI Elements ---
st.markdown("<h1 style='text-align: center; color: white;'>🤖 SAGE - Your AI Voice Assistant</h1>",
            unsafe_allow_html=True)
st.markdown("<div class='typing'>Hello, I'm SAGE. Ready to assist you.</div>", unsafe_allow_html=True)

# Status indicator
status_col1, status_col2 = st.columns([1, 4])
with status_col1:
    st.markdown("<div class='status-light idle'></div>", unsafe_allow_html=True)
with status_col2:
    status_text = st.empty()
    status_text.markdown("<div class='status-indicator'><div class='status-light idle'></div> Idle</div>",
                         unsafe_allow_html=True)

# Conversation history
conversation_container = st.container()

# Control buttons
col1, col2, col3 = st.columns(3)
with col1:
    listen_btn = st.button("🎤 Start Listening", key="listen_btn", use_container_width=True)
with col2:
    stop_btn = st.button("⏹ Stop", key="stop_btn", use_container_width=True)
with col3:
    clear_btn = st.button("🧹 Clear", key="clear_btn", use_container_width=True)
def say(text):
    """Convert text to speech and update UI"""
    print("Sage:", text)
    engine.say(text)
    try:
        engine.runAndWait()
    except RuntimeError:
        def speak():
            engine.endLoop()
            engine.runAndWait()

        thread = threading.Thread(target=speak)
        thread.start()
        thread.join()

    conversation_history.append(("SAGE", text))
    update_conversation()
def open_music():
    """Open music files"""
    music_folder = os.path.join(os.path.expanduser("~"), "Music")
    music_files = glob.glob(os.path.join(music_folder, "*.mp3"))
    if music_files:
        file_to_play = music_files[0]
        if platform.system() == "Windows":
            os.startfile(file_to_play)
        elif platform.system() == "Darwin":
            subprocess.call(["open", file_to_play])
        else:
            subprocess.call(["xdg-open", file_to_play])
        say("Playing music now.")
    else:
        say("Sorry, I couldn't find any music files.")


def run_in_terminator_mode(command):
    """Handle commands in terminator mode"""
    global using_terminator
    say("Processing your request in Terminator mode.")
    print(f"[TERMINATOR] Executing: {command}")

    if open_app(command):
        return

    if "write" in command.lower() and "notepad" in command.lower():
        topic_match = re.search(r'write (about|a|an|the)?(.*)', command.lower())
        topic = topic_match.group(2).strip() if topic_match else "something interesting"
        prompt = f"Write a paragraph about {topic}."
        content = ai(prompt)
        file_path = os.path.join(os.getcwd(), "terminator_output.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.system(f'start notepad.exe "{file_path}"')
        say("I've written about that in Notepad for you.")
    elif "play" in command.lower() and "youtube" in command.lower():
        query = command.lower().replace("play", "").replace("on youtube", "").strip()
        search_query = quote(query)
        url = f"https://www.youtube.com/results?search_query={search_query}"
        webbrowser.open(url)
        say(f"Searching YouTube for {query} and playing it.")
        time.sleep(6)
        pyautogui.moveTo(330, 350)
        pyautogui.click()
    elif "open gmail" in command.lower():
        webbrowser.open("https://mail.google.com")
        say("Opening Gmail.")
    elif "open" in command.lower() and "website" in command.lower():
        match = re.search(r'open (.*?) website', command.lower())
        site = match.group(1).strip().replace(" ", "")
        url = f"https://{site}.com"
        webbrowser.open(url)
        say(f"Opening {site} website.")
    elif "search" in command.lower():
        search_term = command.lower().replace("search", "").strip()
        search_query = quote(search_term)
        url = f"https://www.google.com/search?q={search_query}"
        webbrowser.open(url)
        say(f"Searching Google for {search_term}.")
    elif "check unread email" in command.lower() or "analyze unread email" in command.lower():
        check_unread_emails()
# Features grid
st.markdown("### ✨ Quick Actions")
feature_col1, feature_col2, feature_col3, feature_col4 = st.columns(4)
with feature_col1:
    if st.button("🕒 Get Time", use_container_width=True):
        current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%I:%M %p")
        say(f"The current time is {current_time}")
        conversation_history.append(("SAGE", f"The current time is {current_time}"))
with feature_col2:
    if st.button("📅 Get Date", use_container_width=True):
        current_date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%A, %d %B %Y")
        say(f"Today is {current_date}")
        conversation_history.append(("SAGE", f"Today is {current_date}"))
with feature_col3:
    if st.button("📧 Check Email", use_container_width=True):
        conversation_history.append(("You", "check unread email"))
        run_in_terminator_mode("check unread email")
with feature_col4:
    if st.button("🎵 Play Music", use_container_width=True):
        conversation_history.append(("You", "play music"))
        open_music()





def update_conversation():
    """Update the conversation display in Streamlit"""
    with conversation_container:
        st.markdown("### 💬 Conversation History")
        for speaker, text in conversation_history[-10:]:
            if speaker == "You":
                st.markdown(f"<div class='user-message'><b>You:</b> {text}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='assistant-message'><b>SAGE:</b> {text}</div>", unsafe_allow_html=True)





def send_email(subject, body, to_email):
    """Send email using SMTP"""
    from_email = "your_email@gmail.com"
    password = "your_password"

    message = MIMEMultipart()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_email, password)
        server.sendmail(from_email, to_email, message.as_string())
        server.quit()
        say("Email has been sent successfully.")
    except Exception as e:
        say("Sorry, I was not able to send the email.")
        print("Email sending error:", e)


def ai(prompt):
    """Query AI model for response"""
    try:
        openai.api_key = "your_openai_api_key"
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response['choices'][0]['message']['content']
        print("AI Response:", reply)
        return reply
    except Exception as e:
        print(f"AI Error: {e}")
        return "Sorry, I encountered an error processing your request."


def chat(prompt):
    """Handle chat interactions"""
    global searching
    if not searching:
        return "Searching is currently paused. Say 'start searching' to resume."

    try:
        reply = ai(prompt)
        say(reply)
        return reply
    except Exception as e:
        error_msg = f"Sorry, I encountered an error: {str(e)}"
        say(error_msg)
        print(f"Chat Error: {e}")
        return error_msg


def takecommand():
    """Capture voice input from microphone"""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        status_text.markdown(
            "<div class='status-indicator'><div class='status-light listening'></div> Listening...</div>",
            unsafe_allow_html=True)
        st.toast("Listening...", icon="🎤")
        print("Listening for your command...")
        r.pause_threshold = 1
        audio = r.listen(source)

    try:
        status_text.markdown(
            "<div class='status-indicator'><div class='status-light processing'></div> Processing...</div>",
            unsafe_allow_html=True)
        print("Recognizing...")
        query = r.recognize_google(audio, language="en-in")
        print(f"User said: {query}")
        conversation_history.append(("You", query))
        update_conversation()
        return query.lower()
    except sr.RequestError:
        error_msg = "Error: Unable to connect to the speech recognition service."
        print(error_msg)
        say(error_msg)
        return error_msg
    except sr.UnknownValueError:
        error_msg = "Sorry, I couldn't understand what you said."
        print(error_msg)
        say(error_msg)
        return error_msg
    except Exception as e:
        print("Sorry, I could not recognize your voice.")
        return None
    finally:
        status_text.markdown("<div class='status-indicator'><div class='status-light idle'></div> Ready</div>",
                             unsafe_allow_html=True)


def open_app(command):
    """Open applications based on command - Improved version"""
    app_mapping = {
        "excel": ("Excel", "excel.exe"),
        "powerpoint": ("PowerPoint", "powerpnt.exe"),
        "word": ("Word", "winword.exe"),
        "notepad": ("Notepad", "notepad.exe"),
        "settings": ("Settings", "ms-settings:"),
        "calculator": ("Calculator", "calc.exe"),
        "paint": ("Paint", "mspaint.exe"),
        "chrome": ("Chrome", "chrome.exe"),
        "command prompt": ("Command Prompt", "cmd.exe"),
        "vscode": ("VS Code", "code.exe"),
        "camera": ("Camera", "start microsoft.windows.camera:")
    }

    command = command.lower()

    for app, (display_name, app_cmd) in app_mapping.items():
        if app in command:
            try:
                print(f"Attempting to open {display_name}...")

                if platform.system() == "Windows":
                    if app == "camera":
                        os.system(app_cmd)
                    else:
                        subprocess.Popen(app_cmd, shell=True)
                elif platform.system() == "Darwin":  # macOS
                    if app == "chrome":
                        subprocess.Popen(["open", "-a", "Google Chrome"])
                    elif app == "notepad":
                        subprocess.Popen(["open", "-a", "TextEdit"])
                else:  # Linux
                    if app == "chrome":
                        subprocess.Popen(["google-chrome"])
                    elif app == "notepad":
                        subprocess.Popen(["gedit"])

                say(f"Opening {display_name}.")
                return True
            except Exception as e:
                print(f"Error opening {display_name}: {e}")
                say(f"Could not open {display_name}.")
                return False

    say("Sorry, I don't recognize that app.")
    return False


def get_current_time():
    """Get current time in Indian timezone"""
    india = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(india)
    return now.strftime("%I:%M %p")


def get_current_date():
    """Get current date in Indian timezone"""
    india = pytz.timezone('Asia/Kolkata')
    today = datetime.datetime.now(india)
    return today.strftime("%A, %d %B %Y")


def check_unread_emails():
    """Check and read unread emails"""
    import imaplib
    import email
    from email.header import decode_header

    username = "your_email@gmail.com"
    password = "your_password"

    def clean(text):
        return "".join(c if c.isalnum() else "_" for c in text)

    say("Checking unread emails...")
    imap = imaplib.IMAP4_SSL("imap.gmail.com")

    try:
        imap.login(username, password)
        imap.select("inbox")
        status, messages = imap.search(None, '(UNSEEN)')
        email_ids = messages[0].split()

        if not email_ids:
            say("No unread emails found.")
        else:
            say(f"You have {len(email_ids)} unread emails.")
            for i, mail_id in enumerate(email_ids[:5], 1):
                status, msg_data = imap.fetch(mail_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                            from_ = msg.get("From")
                        say(f"Email {i} is from {from_} with subject: {subject}")
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode()
                                    print(f"Body:\n{body}\n")
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode()
                            print(f"Body:\n{body}\n")
    except Exception as e:
        say("Failed to check emails.")
        print("Error:", e)
    finally:
        imap.logout()


def play_youtube_music(query, pyautogui=None):
    """Play music from YouTube"""
    search_query = quote(query)
    url = f"https://www.youtube.com/results?search_query={search_query}"
    webbrowser.open(url)
    say(f"Searching YouTube for {query} and playing first music.")
    time.sleep(5)
    if pyautogui:
        pyautogui.press("tab", presses=6)
        pyautogui.press("enter")


def open_file_by_name(name):
    """Open file by name"""
    user_home = os.path.expanduser("~")
    search_paths = [
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "Downloads"),
        user_home
    ]

    for path in search_paths:
        for root, dirs, files in os.walk(path):
            for file in files:
                if name.lower() in file.lower():
                    file_path = os.path.join(root, file)
                    say(f"Opening file: {file}")
                    os.startfile(file_path)
                    return True
            for folder in dirs:
                if name.lower() in folder.lower():
                    folder_path = os.path.join(root, folder)
                    say(f"Opening folder: {folder}")
                    os.startfile(folder_path)
                    return True
    say("Sorry, I couldn't find any matching files or folders.")
    return False


def open_camera():
    """Open camera preview - Improved version"""
    global camera_running

    if platform.system() == "Windows":
        try:
            os.system("start microsoft.windows.camera:")
            say("Opening your camera now.")
            camera_running = True
            return
        except Exception as e:
            print(f"Error opening Windows Camera: {e}")

    # Fallback to pygame camera if available
    try:
        if not pygame.camera:
            raise ImportError("Pygame camera not available")

        def camera_thread():
            global camera_running
            camera_running = True

            pygame.camera.init()
            cameras = pygame.camera.list_cameras()

            if not cameras:
                say("No cameras found!")
                return

            cam = pygame.camera.Camera(cameras[0], (640, 480))
            cam.start()

            screen = pygame.display.set_mode((640, 480))
            pygame.display.set_caption("Camera Preview")

            print("Camera opened. Showing preview for 10 seconds...")
            start_time = time.time()

            while camera_running:
                img = cam.get_image()
                screen.blit(img, (0, 0))
                pygame.display.flip()

                for event in pygame.event.get():
                    if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                        print("User pressed 'q'.")
                        camera_running = False

                if time.time() - start_time > 10:
                    print("Closing camera preview.")
                    break

            cam.stop()
            pygame.quit()

        threading.Thread(target=camera_thread, daemon=True).start()
        say("Opening your camera now.")
    except Exception as e:
        print(f"Camera error: {e}")
        say("Sorry, I couldn't access the camera.")


def handle_code_input(query):
    """Handle code input for correction"""
    global expecting_code
    if "type" in query.lower():
        say("Paste your code. Type 'done' when you're finished.")
        code_input = st.text_area("Enter your code:", height=200)
        if st.button("Submit Code"):
            corrected_code = ai(f"Please correct the following Python code:\n\n{code_input}")
            say("Here's the corrected version.")
            st.code(corrected_code, language='python')
            expecting_code = False
    else:
        say("Please speak your code. Say 'done' when you're finished.")
        code_lines = []
        while True:
            line = takecommand()
            if "done" in line.lower():
                break
            line = line.replace("colon", ":").replace("indent", "    ").replace("open parenthesis", "(").replace(
                "close parenthesis", ")")
            code_lines.append(line)
        full_code = "\n".join(code_lines)
        corrected_code = ai(f"Please correct the following Python code:\n\n{full_code}")
        say("Here's the corrected version.")
        st.code(corrected_code, language='python')
        expecting_code = False


def main():
    global using_terminator, searching, expecting_code, conversation_history

    if listen_btn:
        query = takecommand()
        if query is None:
            return

        if (not query or "couldn't understand" in query.lower() or
                "error" in query.lower() or "none" == query.lower().strip() or
                len(query.strip()) < 3):
            say("Sorry, I didn't catch that. Please say it again.")
            return

        # Handle app opening commands first
        if any(cmd in query.lower() for cmd in ["open ", "start "]):
            for app in ["word", "excel", "powerpoint", "notepad", "calculator",
                        "paint", "chrome", "command prompt", "vscode", "camera"]:
                if app in query.lower():
                    open_app(query)
                    return

        if "use terminator" in query.lower() or (query.lower().strip() == "terminator"):
            using_terminator = True
            say("What should I do in the terminal?")
            return

        if using_terminator:
            if "stop terminator" in query or "exit terminator" in query or "leave terminal" in query:
                say("Exiting Terminator mode.")
                using_terminator = False
                return

            run_in_terminator_mode(query)
            return

        if "i want to type" in query.lower():
            say("Okay, switching to text mode. Please type your command.")
            query = st.text_input("Enter your command:")
            if query:
                conversation_history.append(("You", query))
                update_conversation()

        if "play" in query and "youtube" in query:
            video_query = query.lower().replace("play", "").replace("on youtube", "").strip()
            play_youtube_music(video_query, pyautogui)
            return

        print("Processing query:", query)

        if "stop searching" in query.lower():
            searching = False
            say("I've paused searching. Say 'start searching' to resume.")
            return
        elif "start searching" in query.lower():
            searching = True
            say("I've resumed searching. How can I help you?")
            return

        if "exit youtube" in query.lower() or "close youtube" in query.lower():
            say("Closing the YouTube tab.")
            pyautogui.hotkey('ctrl', 'w')
            return

        skip_processing = False
        apps = [["game", r'start "" "C:\\Users\\Public\\Desktop\\Grand Theft Auto V.lnk"'],
                ["music", open_music],
                ["notepad", r'start "" "C:\\Windows\\notepad.exe"'],
                ["gallery", r'start "" "C:\\Users\\irsha\\OneDrive\\Pictures"']]

        for app in apps:
            if f"open {app[0]}" in query.lower():
                say(f"Starting {app[0]}, sir...")
                if callable(app[1]):
                    app[1]()
                else:
                    os.system(app[1])
                skip_processing = True

        if "the time" in query.lower():
            current_time = get_current_time()
            say(f"Sir, the time is {current_time}")
            print(f"Current time: {current_time}")
            skip_processing = True

        if "the date" in query.lower():
            current_date = get_current_date()
            say(f"Sir, today is {current_date}")
            print(f"Current date: {current_date}")
            skip_processing = True

        if "play" in query and "youtube" in query:
            video_query = query.lower().replace("play", "").replace("on youtube", "").strip()
            play_youtube_music(video_query, pyautogui)
            return

        if any(x in query.lower() for x in ["exit", "quit", "good bye", "bye"]):
            say("Goodbye sir!")
            print("SAGE shutting down...")
            st.rerun()

        if "open file" in query.lower() or "open image" in query.lower() or "open pdf" in query.lower() or "open music" in query.lower():
            say("Which file should I open?")
            file_name = takecommand()
            open_file_by_name(file_name)
            return
        elif "open camera" in query:
            say("Opening your camera now.")
            open_camera()
            return
        elif "close camera" in query or "stop camera" in query:
            global camera_running
            camera_running = False
            say("Camera has been closed.")

        if skip_processing:
            return

        if "using ai" in query.lower():
            response = ai(query)
            print("AI output:", response)
            say(response)
        elif searching:
            response = chat(query)
            print("Chat output:", response)


# --- Footer ---
st.markdown("""
<div class="footer">
    SAGE Voice Assistant v1.0 | Powered by Streamlit, Pyttsx3, and OpenAI
</div>
""", unsafe_allow_html=True)

# --- Button Handlers ---
if listen_btn:
    main()

if stop_btn:
    say("Stopping current operation.")
    status_text.markdown("<div class='status-indicator'><div class='status-light idle'></div> Stopped</div>",
                         unsafe_allow_html=True)

if clear_btn:
    conversation_history = []
    update_conversation()
    st.toast("Conversation cleared!", icon="🧹")

# Initialize conversation display
update_conversation()