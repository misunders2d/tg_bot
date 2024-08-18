from dotenv import load_dotenv
load_dotenv('.env')

import os, time
from deta import Deta

from openai import OpenAI

import workers

ASSISTANT_ID = os.getenv('ASSISTANT_ID')
OPENAI_KEY = os.getenv('AI_KEY')
DETA_ID = os.getenv('DETA_KEY')
print(OPENAI_KEY)

# CHAT_ID = '107'

# client = OpenAI(api_key = OPENAI_KEY)

# deta_base = Deta(DETA_ID)
# # client.beta.threads.delete('thread_Y1WzIYB3uqTXYSWwRpY6wYzi')

# if not (chat_thread:=workers.check_thread(CHAT_ID, deta_base)):
#     chat_thread = client.beta.threads.create()
#     workers.push_thread(CHAT_ID, chat_thread.id, deta_base)
# current_thread = client.beta.threads.retrieve(thread_id = chat_thread)
# print(current_thread)

# text_input = 'Hey, who are you?'
# messages = [{'type':'text','text':text_input}]
# _ = client.beta.threads.messages.create(
#     thread_id = current_thread.id,
#     content = messages,
#     role = 'user'
#     )
# current_run = client.beta.threads.runs.create(
#     thread_id=chat_thread,
#     assistant_id=ASSISTANT_ID
#     )
# current_status = 'queued'
# while current_status in ('queued','in_progress'):
#     time.sleep(0.5)
#     current_run = client.beta.threads.runs.retrieve(thread_id = current_thread.id, run_id = current_run.id)
#     current_status = current_run.status
#     print(current_status)
# messages = client.beta.threads.messages.list(current_thread.id)
# print(messages)
# # # response = messages.data[0].content[0].text.value
