from openai import OpenAI
import os


ASSISTANT_ID = os.getenv('ASSISTANT_ID')
OPENAI_KEY = os.getenv('AI_KEY')

client = OpenAI(api_key = OPENAI_KEY)


def check_thread(chat_id, deta_base):
    result = deta_base.Base('chat_ids').fetch({"key":chat_id}).items
    if len(result)>0:
        return result[0]['thread']
    return False

def push_thread(chat_id, thread_id, deta_base):
    deta_base.Base('chat_ids').put(key = chat_id, data = {'thread':thread_id})

def text(text_input, client, assistant_id, thread_id):
    messages = [{'role':'user','content':text_input}]
    response = client.beta.thre

def image(image_input):
    pass

def voice(voice_input):
    pass