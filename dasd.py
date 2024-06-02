import openai
import os
import asyncio
import speech_recognition as sr
from gpiozero import LED
import simpleaudio as sa
import sys
import subprocess

# ALSA 및 기타 stderr 메시지 억제
stderr_fileno = sys.stderr.fileno()
devnull = os.open(os.devnull, os.O_RDWR)
os.dup2(devnull, stderr_fileno)

# OpenAI API 키 설정
openai.api_key = "YOUR_OPENAI_API_KEY"

# Google Cloud 인증 키 설정
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "path_to_your_google_cloud_credentials.json"

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
            return "알 수 없는 명령입니다."

async def correct_transcript(transcript):
    system_prompt = (
        "You are a helpful assistant. Your task is to correct any spelling discrepancies "
        "in the transcribed text. Ensure the correct spelling of the following terms: ZyntriQix, "
        "Digique Plus, CynapseFive, VortiQore V8, EchoNix Array, OrbitalLink Seven, DigiFractal Matrix, PULSE, RAPT, "
        "B.R.I.C.K., Q.U.A.R.T.Z., F.L.I.N.T. Only add necessary punctuation such as periods, commas, and capitalization, "
        "and use only the context provided."
    )
    try:
        response = openai.ChatCompletion.create(
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
        response = openai.ChatCompletion.create(
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
            format="wav",
            language="ko"
        )
        with open("response.wav", "wb") as f:
            f.write(response['data'])
        wave_obj = sa.WaveObject.from_wave_file("response.wav")
        play_obj = wave_obj.play()
        play_obj.wait_done()
    except Exception as e:
        print(f"Error generating speech: {e}")

def play_beep():
    wave_obj = sa.WaveObject.from_wave_file("beep.wav")
    play_obj = wave_obj.play()
    play_obj.wait_done()

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

    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    print("Listening for '시리야'...")

    while True:
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
                corrected_command = await correct_transcript(command)
                conversation.append({"role": "user", "content": corrected_command})
                gpt_response = await call_chatgpt4_api(conversation)
                print(f"GPT-4 Response: {gpt_response}")
                conversation.append({"role": "assistant", "content": gpt_response})

                iot_response = iot.process_command(gpt_response)
                if iot_response:
                    await generate_speech(iot_response)
                else:
                    await generate_speech(gpt_response)
        except sr.UnknownValueError:
            print("음성을 인식하지 못했습니다.")
        except sr.RequestError as e:
            print(f"Google Speech Recognition service 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())
