import time
from typing import List
from openai import OpenAI
from io import BytesIO
from deta import Deta

def check_thread(chat_id: str, deta_base: Deta):
    result = deta_base.Base('chat_ids').fetch({"key":chat_id}).items
    if len(result)>0:
        return result[0]['thread']
    return False

def push_thread(chat_id: str, thread_id: str, deta_base: Deta):
    deta_base.Base('chat_ids').put(key = chat_id, data = {'thread':thread_id})

def process_text(text_input: str, client: OpenAI, assistant_id: str, thread_id: str, voice: bool = False, messages: List[dict] = None):
    if not messages:
        messages = [{'type':'text','text':text_input}]
    try:
        _ = client.beta.threads.messages.create(
            thread_id = thread_id,
            content = messages,
            role = 'user'
            )
        current_run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
            )
        current_status = 'queued'
        while current_status in ('queued','in_progress'):
            time.sleep(0.5)
            current_run = client.beta.threads.runs.retrieve(thread_id = thread_id, run_id = current_run.id)
            current_status = current_run.status
        thread_messages = client.beta.threads.messages.list(thread_id)
        response = thread_messages.data[0].content[0].text.value
    except Exception as e:
        print(e)
        response = 'Sorry, something went wrong on OpenAI side'
    if not voice:
        return response
    else:
        voice_response = client.audio.speech.create(
        model="tts-1",
        voice="onyx",
        input=response
        )
        voice_response = BytesIO(voice_response.content)
        voice_response.name = 'response.ogg'
    return voice_response

def image(image: str, caption: str, client, assistant_id: str, thread_id: str, voice: bool = False):
    if not caption:
        caption = 'What is in these images?'
    messages = [
        {'type':'text','text':caption},
        {'type':'image_url', 'image_url':{'url':image}}
        ]
    try:
        response = process_text(
            text_input = None,
            client = client,
            assistant_id = assistant_id,
            thread_id = thread_id,
            voice = False,
            messages = messages)
    except Exception as e:
        print(f'Error while processing image:\n{e}')
        response = "Sorry, couldn't process the image, please try again later"
    return response

def transcribe_audio(voice_input:bytes, client: OpenAI):
    try:
        transcription = client.audio.transcriptions.create(file = voice_input, model = 'whisper-1')
        response = transcription.text
    except Exception as e:
        print(e)
        response = "Can't transcribe audio, please try again a bit later"
    return response
