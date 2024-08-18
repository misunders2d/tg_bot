import time
from typing import List
from io import BytesIO
def check_thread(chat_id, deta_base):
    result = deta_base.Base('chat_ids').fetch({"key":chat_id}).items
    if len(result)>0:
        return result[0]['thread']
    return False

def push_thread(chat_id, thread_id, deta_base):
    deta_base.Base('chat_ids').put(key = chat_id, data = {'thread':thread_id})

def text(text_input, client, assistant_id, thread_id, voice = False):
    messages = [{'type':'text','text':text_input}]
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
    messages = client.beta.threads.messages.list(thread_id)
    response = messages.data[0].content[0].text.value
    if not voice:
        return response
    else:
        voice_response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=response
        )

        voice_response = BytesIO(voice_response.content)
        voice_response.name = 'response.ogg'
    return voice_response

def image(images: List, text: str, client, assistant_id: str, thread_id: str):
    assert isinstance(images, list)
    if not text:
        text = 'What is in these images?'
    messages = [{'type':'text','text':text}]
    


def transcribe_audio(voice_input, client):
    response = client.audio.transcriptions.create(file = voice_input, model = 'whisper-1')
    return response.text
