import openai
import os
import pyaudio
import asyncio
import aiohttp
from gpiozero import LED
import simpleaudio as sa
from google.cloud import speech

# OpenAI API 키 설정
openai.api_key = "YOUR_OPENAI_API_KEY"

# Google Cloud 인증 키 설정
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "path_to_your_google_cloud_credentials.json"
speech_client = speech.SpeechClient()

# Initialize LED
led_living_room = LED(17)

class IotControl:
    def __init__(self):
        self.led_living_room = LED(17)  # 거실 불

    def turn_on_living_room_light(self):
        self.led_living_room.on()
        return "거실 불을 켰습니다."

    def turn_off_living_room_light(self):
        self.led_living_room.off()
        return "거실 불을 껐습니다."

    def process_command(self, command):
        if "거실 불 켜줘" in command:
            return self.turn_on_living_room_light()
        elif "거실 불 꺼줘" in command:
            return self.turn_off_living_room_light()
        else:
            return None

class AudioStream:
    def __init__(self):
        self.chunk = 1024  # Record in chunks of 1024 samples
        self.sample_format = pyaudio.paInt16  # 16 bits per sample
        self.channels = 1
        self.fs = 16000  # Record at 16000 samples per second
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=self.sample_format,
                                  channels=self.channels,
                                  rate=self.fs,
                                  frames_per_buffer=self.chunk,
                                  input=True)
        self.frames = []

    def start_stream(self):
        while True:
            data = self.stream.read(self.chunk)
            self.frames.append(data)
            if len(self.frames) >= 10:  # 10 chunks to form a 1-second buffer
                audio_content = b''.join(self.frames)
                self.frames = []
                transcription = asyncio.run(self.transcribe_audio(audio_content))
                if transcription and "헤이 어시스턴트" in transcription.lower():
                    self.play_beep()
                    print("Keyword detected, start conversation")
                    asyncio.run(self.handle_command(transcription.replace("헤이 어시스턴트", "").strip()))

    def play_beep(self):
        wave_obj = sa.WaveObject.from_wave_file("beep.wav")
        play_obj = wave_obj.play()
        play_obj.wait_done()

    async def transcribe_audio(self, audio_content):
        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="ko-KR",
            model="default",
            enable_automatic_punctuation=True,
            speech_contexts=[speech.SpeechContext(phrases=["헤이 어시스턴트", "거실 불 켜줘", "거실 불 꺼줘"])]
        )
        response = speech_client.recognize(config=config, audio=audio)
        for result in response.results:
            return result.alternatives[0].transcript
        return None

    async def handle_command(self, transcript):
        corrected_transcript = await correct_transcript(transcript)
        conversation.append({"role": "user", "content": corrected_transcript})
        gpt_response = await call_chatgpt4_api(conversation)
        print(f"GPT-4o Response: {gpt_response}")
        conversation.append({"role": "assistant", "content": gpt_response})

        # IoT 명령 처리
        iot_response = iot.process_command(gpt_response)
        if iot_response:
            await generate_speech(iot_response)
        else:
            await generate_speech(gpt_response)

async def correct_transcript(transcript):
    system_prompt = (
        "You are a helpful assistant. Your task is to correct any spelling discrepancies "
        "in the transcribed text. Ensure the correct spelling of the following terms: ZyntriQix, "
        "Digique Plus, CynapseFive, VortiQore V8, EchoNix Array, OrbitalLink Seven, DigiFractal Matrix, PULSE, RAPT, "
        "B.R.I.C.K., Q.U.A.R.T.Z., F.L.I.N.T. Only add necessary punctuation such as periods, commas, and capitalization, "
        "and use only the context provided."
    )
    try:
        response = await openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript}
            ]
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error correcting transcript: {e}")
        return transcript

async def call_chatgpt4_api(conversation):
    try:
        response = await openai.ChatCompletion.create(
            model="gpt-4o",
            messages=conversation
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error calling ChatGPT API: {e}")
        return "명령을 처리하는 데 문제가 발생했습니다."

async def generate_speech(text):
    try:
        response = await openai.Audio.create(
            engine="davinci-tts",
            prompt=text,
            format="opus",
            language="ko"
        )
        with open("response.opus", "wb") as f:
            f.write(response['audio'])
        play_obj = sa.WaveObject.from_wave_file("response.opus").play()
        play_obj.wait_done()
    except Exception as e:
        print(f"Error generating speech: {e}")

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

    audio_stream = AudioStream()
    audio_stream.start_stream()

if __name__ == "__main__":
    asyncio.run(main())
