import openai
import os
import asyncio
import speech_recognition as sr
import pyaudio
import time
from pathlib import Path
import wave
import sys
from openai import OpenAI

# ALSA 에러 억제
stderr_fileno = sys.stderr.fileno()
devnull = os.open(os.devnull, os.O_RDWR)
os.dup2(devnull, stderr_fileno)

# OpenAI API 키 설정 (환경 변수에서 가져옴)
openai_api_key = "YOUR_OPENAI_API_KEY"
client = OpenAI(api_key=openai_api_key)

# Initialize LED
# led_living_room = LED(17)  # 주석 처리

class IotControl:
    def __init__(self):
        # self.led_living_room = LED(17)  # 주석 처리
        self.led_living_room = lambda: print('test')  # 대체 코드

    def turn_on_living_room_light(self):
        self.led_living_room()
        return "거실 불을 켰습니다."

    def turn_off_living_room_light(self):
        self.led_living_room()
        return "거실 불을 껐습니다."

    def process_command(self, command):
        if "거실 불 켜줘" in command:
            return self.turn_on_living_room_light()
        elif "거실 불 꺼줘" in command:
            return self.turn_off_living_room_light()
        else:
            return "알 수 없는 명령입니다."

async def call_chatgpt4_api(conversation):
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4",
            messages=conversation,
            temperature=1,
            max_tokens=256,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling ChatGPT API: {e}")
        return "명령을 처리하는 데 문제가 발생했습니다."

async def stream_to_speakers(text):
    pyaudio_instance = pyaudio.PyAudio()
    player_stream = pyaudio_instance.open(format=pyaudio.paInt16, channels=1, rate=24000, output=True)

    start_time = time.time()

    async with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="alloy",
        response_format="pcm",  # similar to WAV, but without a header chunk at the start.
        input=text,
    ) as response:
        print(f"Time to first byte: {int((time.time() - start_time) * 1000)}ms")
        for chunk in response.iter_bytes(chunk_size=1024):
            player_stream.write(chunk)

    print(f"Done in {int((time.time() - start_time) * 1000)}ms.")
    player_stream.stop_stream()
    player_stream.close()
    pyaudio_instance.terminate()

def play_beep():
    beep_path = Path(__file__).parent / "beep.wav"
    with wave.open(str(beep_path), 'rb') as wave_file:
        wave_obj = wave_file.readframes(wave_file.getnframes())
    pyaudio_instance = pyaudio.PyAudio()
    player_stream = pyaudio_instance.open(format=pyaudio.paInt16, channels=1, rate=wave_file.getframerate(), output=True)
    player_stream.write(wave_obj)
    player_stream.stop_stream()
    player_stream.close()
    pyaudio_instance.terminate()

async def handle_voice_command():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    global conversation, iot

    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        print("Listening...")
        audio = recognizer.listen(source)
    
    try:
        transcription = recognizer.recognize_google(audio, language="ko-KR")
        print(f"Transcription: {transcription}")
        if "시리야" in transcription:
            play_beep()
            command = transcription.replace("시리야", "").strip()
            conversation.append({"role": "user", "content": command})
            gpt_response = await call_chatgpt4_api(conversation)
            print(f"GPT-4 Response: {gpt_response}")
            conversation.append({"role": "assistant", "content": gpt_response})

            iot_response = iot.process_command(command)
            # IoT 명령이 처리되지 않은 경우 gpt_response를 사용
            if iot_response == "알 수 없는 명령입니다.":
                await stream_to_speakers(gpt_response)
            else:
                await stream_to_speakers(iot_response)
    except sr.UnknownValueError:
        print("음성을 인식하지 못했습니다.")
    except sr.RequestError as e:
        print(f"Google Speech Recognition service 오류: {e}")

async def main():
    global conversation, iot
    iot = IotControl()
    conversation = [{"role": "system", "content": """
You are an assistant that helps control IoT devices and also have daily conversations.
You understand commands related to controlling household items and can engage in casual conversation.
For IoT commands, respond with clear and concise actions.
For casual conversations, be friendly and engaging.
Examples of IoT commands include:
- "거실 불 켜줘" (Turn on the living room light)
- "거실 불 꺼줘" (Turn off the living room light)
For other requests, provide helpful and informative responses. Provide detailed answers when asked about specific topics.
Avoid mentioning that you are an AI, respond as if you are a human.
""" }]

    print("Listening for '시리야'...")
    while True:
        await handle_voice_command()

if __name__ == "__main__":
    asyncio.run(main())
