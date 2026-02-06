import json
import numpy as np
import sounddevice as sd
import soundfile as sf
import websocket
import io
from openai import OpenAI
import requests
import argparse
import os

# openai setup
openai_api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

# args from webapp
parser = argparse.ArgumentParser()
parser.add_argument("--language", default="French")
parser.add_argument("--level", default="intermediate")
parser.add_argument("--in", dest="in_device", type=int, default=None)
parser.add_argument("--out", dest="out_device", type=int, default=None)
args = parser.parse_args()

language = args.language
level = args.level

if args.in_device is not None or args.out_device is not None:
    sd.default.device = (args.in_device, args.out_device)

print("CLI starting with:")
print("language = ", language)
print("level = ", level)

# system prompt
prompt = f"""You are a conversational partner to a user attempting to practice {language} at the 
        {level} level. You will continue a pleasant conversation in whichever language your user selected by asking 
        questions and giving statements related to the previous inputs by your conversational partner. 
        Rules that MUST be followed:
        1. Correct all mistakes, including stand-in English words.
        2. If they are a beginner, do not use complicated phrases or expressions. Stick to basics.
        3. After a few questions on the same topic, if you are repeating yourself, move to something different. Some acceptable topics might be pets, hobbies, television, weather, location, food, sports, or music.
        """

# openai settings
text_model="gpt-4o-mini"  # pick your favorite text model
stt_model="gpt-4o-mini-transcribe"
tts_model="gpt-4o-mini-tts"
voice="alloy"

# audio settings
rate = 24000
channels = 1
dtype = 'int16'
frame_ms = 20  # 20ms frames are a good realtime chunk size
blocksize = int(rate * (frame_ms / 1000.0))  # 480 samples at 24kHz

# function to record audio - runs until user hits 'enter' key
def record_audio_until_enter():
    print("Starting recording from mic.")

    stop = False
    chunks = []
    total_frames = 0

    def mic_callback(indata, frames, time_info, status):
        nonlocal total_frames
        chunks.append(indata.copy())  # keep as numpy int16
        total_frames += frames

    stream = sd.InputStream(
        samplerate=rate,
        channels=channels,
        dtype=dtype,
        blocksize=blocksize,
        callback=mic_callback,
    )
    stream.start()

    input(">>> Press ENTER to stop recording <<<\n")
    stop = True

    stream.stop()
    stream.close()

    print("\nStopped recording.")

    audio = np.concatenate(chunks, axis=0)  # shape (n_frames, 1)
    audio = audio.reshape(-1)               # flatten to 1D int16

    return audio

def generate_response(
    recorded_audio_np, 
    conversation):
    
    client = OpenAI(api_key=openai_api_key)

    # 1. STT
    wav_buf = io.BytesIO()

    # write a WAV container into the buffer so the transcription endpoint recognizes it
    sf.write(wav_buf, recorded_audio_np, rate, format="WAV")
    wav_buf.seek(0)
    wav_buf.name = "input.wav" # infers format

    # create stt transcription
    transcription = client.audio.transcriptions.create(
        model=stt_model,
        file=wav_buf,
    )
    user_text = transcription.text
    print(repr(user_text))

    # append user's transcribed text to conversation history
    conversation.append({"role": "user", "content": user_text})

    # 2. Generate response
    resp = client.responses.create(
        model=text_model,
        instructions=prompt,
        input=conversation,
    )

    assistant_text = resp.output_text
    print(repr(assistant_text))

    # append response to conversation history
    conversation.append({"role": "assistant", "content": assistant_text})

    # 3. TTS
    tts_url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": tts_model,
        "voice": voice,
        "input": assistant_text,
        "speed": 0.85, # optional, set to .85 so it's slower for practice
        "response_format": "wav",
    }

    r = requests.post(tts_url, headers=headers, data=json.dumps(payload))

    tts_wav_bytes = r.content
    bio = io.BytesIO(tts_wav_bytes)
    audio, sr = sf.read(bio, dtype="float32")  

    print("Playing...")
    sd.play(audio, sr)
    sd.wait()

    return assistant_text

conversation = []

turn = 0
while True:
    turn += 1
    print("\n==============================")
    print("TURN", turn)
    print("==============================")

    audio = record_audio_until_enter()
    print("Got audio, sending to model...")

    generate_response(audio, conversation)

