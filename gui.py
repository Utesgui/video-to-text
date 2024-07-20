from moviepy.editor import *
import tkinter as tk
from tkinter import filedialog, Label, Tk, Button, Entry, StringVar, Frame, Text
from configparser import ConfigParser
import azure.cognitiveservices.speech as speechsdk
import time
import pickle
import threading
from datetime import timedelta, datetime


config_file = "settings.ini"
config = ConfigParser()

def save_settings():
    config['DEFAULT'] = {
        'SpeechKey': speech_key_var.get(),
        'Region': region_var.get()
    }
    with open(config_file, 'w') as f:
        config.write(f)

def load_settings():
    config.read(config_file)
    speech_key_var.set(config['DEFAULT'].get('SpeechKey', ''))
    region_var.set(config['DEFAULT'].get('Region', ''))


def log_message(message):
    log_field.config(state=tk.NORMAL)  # Enable editing of the Text widget
    log_field.insert(tk.END, message + "\n")  # Append message to the Text widget
    log_field.config(state=tk.DISABLED)  # Disable editing of the Text widget
    log_field.see(tk.END)  # Scroll to the end of the Text widget
    
def select_video_file():
    file_path = filedialog.askopenfilename()
    video_file_var.set(file_path)
    log_message(f"Selected video file: {file_path}")
    try:
        with VideoFileClip(file_path) as video:
            duration = video.duration
            duration_formatted = str(timedelta(seconds=int(duration)))
            log_message(f"Video duration: {duration_formatted}")
    except Exception as e:
        log_message(f"Error extracting video duration: {e}")


# Global flag to signal the thread to stop
stop_requested = False

def start_process():
    global stop_requested
    stop_requested = False  # Reset the flag when starting a new process
    video_file = video_file_var.get()
    speech_key = speech_key_var.get()
    region = region_var.get()
    log_message("Starting process...")
    
    def process():
        try:
            audio_file = extract_audio(video_file)
            log_message(f"Extracted audio to: {audio_file}")
            if stop_requested:
                return  # Exit the process if stop is requested
            transcribe_audio(audio_file, speech_key, region)
            if stop_requested:
                return  # Check again after long-running operations
            log_message("Transcription completed.")
        except Exception as e:
            log_message(f"Error during processing: {e}")

    # Run the process function in a separate thread
    threading.Thread(target=process).start()

def stop_process():
    global stop_requested
    stop_requested = True
    log_message("Stopping process...")


def extract_audio(video_file):
    output_file = video_file.rsplit('.', 1)[0] + ".wav"
    video = VideoFileClip(video_file)
    audio = video.audio
    audio.write_audiofile(output_file, codec="pcm_s16le", fps=16000, bitrate="16k", ffmpeg_params=["-ac", "1"])
    return output_file

def transcribe_audio(audio_file, subscription_key, service_region):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Authenticate
    speech_config = speechsdk.SpeechConfig(subscription_key, service_region)
    # Set up the file as the audio source
    audio_config = speechsdk.AudioConfig(filename=audio_file)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config, audio_config)
    audio_file_name_without_extension = audio_file.rsplit('.', 1)[0]
    transcript_file_name = audio_file_name_without_extension + ".txt"
    with open(transcript_file_name, 'a') as file:
                file.write('\n'+'\n'+'\n')
                file.write("Transcription started at " + timestamp + '\n')
                file.write('\n'+'\n')

    # Flag to end transcription
    done = False
    # List of transcribed lines
    results = list()

    def stop_cb(evt):
        """callback that stops continuous recognition upon receiving an event `evt`"""
        print(f"CLOSING on {evt}")
        log_message(f"CLOSING on {evt}")
        speech_recognizer.stop_continuous_recognition()
        # Let the function modify the flag defined outside this function
        global done
        done = True
        print(f"CLOSED on {evt}")
        log_message(f"CLOSED on {evt}")

    
    # Define a function to handle the recognized event
    def recognized_handler(evt):
        recognised_text = evt.result.text
        video_file = video_file_var.get()
        video_file_name_without_extension = video_file.rsplit('.', 1)[0]
        # Append the timestamp before the filetype
        transcript_file_name = video_file_name_without_extension + ".txt"
        # Convert offset to seconds. 1 tick = 100 nanoseconds, so divide by 10**7 to get seconds
        offset_seconds = evt.result.offset / 10**7
        # Format the offset into HH:MM:SS
        timestamp = time.strftime('%H:%M:%S', time.gmtime(offset_seconds))
        # Append the new transcription with timestamp to the running list
        transcription_with_timestamp = f"[{timestamp}] {recognised_text}"
        results.append(transcription_with_timestamp)
        # This function will be called every time a segment is recognized
        message = f"transcript: '{transcription_with_timestamp}'"
        print(message)  # You can also log to console if needed
        log_message(message)  # Use the log_message function to log in the GUI
        # Write to the transcript file
        if recognised_text.strip():
            with open(transcript_file_name, 'a') as file:
                file.write(transcription_with_timestamp + '\n')

    # Attach the event handler
    speech_recognizer.recognized.connect(recognized_handler)
    
    # Define behaviour for end of session
    speech_recognizer.session_stopped.connect(stop_cb)
    # And for canceled sessions
    speech_recognizer.canceled.connect(stop_cb)

    # Create a synchronous continuous recognition, the transcription itself if you will
    speech_recognizer.start_continuous_recognition()
    # Set a brief pause between API calls
    while not done:
        if stop_requested:
                return  # Exit the process if stop is requested
        time.sleep(0.5)

    # Dump the whole transcription to a pickle file
    with open("transcribed_video.pickle", "wb") as f:
        pickle.dump(results, f)
        #print("Transcription dumped")
        log_message("Transcription dumped")


####################################################
################## GUI SETUP #######################
####################################################

# Create the main window
root = tk.Tk()
root.title("Video Transcription Tool")

video_file_var = tk.StringVar()
speech_key_var = tk.StringVar()
region_var = tk.StringVar()

load_settings()  # Load settings at startup

# Set a nicer font
default_font = ('Helvetica', 12)
root.option_add("*Font", default_font)

# Create a frame for the video file selection
video_frame = Frame(root, pady=5)
video_frame.pack(fill='x', padx=10)
Label(video_frame, text="Video File:").pack(side='left')
Button(video_frame, text="Select Video File", command=select_video_file).pack(side='left', padx=10)
Entry(video_frame, textvariable=video_file_var, fg="blue", state='readonly').pack(side='left', fill='x', expand=True)

# Create a frame for the speech key input
speech_key_frame = Frame(root, pady=5)
speech_key_frame.pack(fill='x', padx=10)
Label(speech_key_frame, text="Speech Key:").pack(side='left')
Entry(speech_key_frame, textvariable=speech_key_var).pack(side='left', fill='x', expand=True, padx=(10, 0))

# Create a frame for the region input
region_frame = Frame(root, pady=5)
region_frame.pack(fill='x', padx=10)
Label(region_frame, text="Region:").pack(side='left')
Entry(region_frame, textvariable=region_var).pack(side='left', fill='x', expand=True, padx=(10, 0))

# Create a frame for the action buttons
action_frame = Frame(root, pady=5)
action_frame.pack(fill='x', padx=10)
Button(action_frame, text="Start", command=start_process).pack(side='left', padx=10)
Button(action_frame, text="Save Settings", command=save_settings).pack(side='left', padx=10)
#Button(action_frame, text="Stop", command=stop_process).pack(side='left', padx=10)

# Create a frame for the log section
log_frame = Frame(root, pady=10)
log_frame.pack(fill='both', expand=True, padx=10)

# Log field setup
log_field = Text(log_frame, state='disabled', height=10, bg="black", fg="white")
log_field.pack(fill='both', expand=True)

root.mainloop()
