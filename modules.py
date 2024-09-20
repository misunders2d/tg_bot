from typing import List, Union
from openai import OpenAI
from openai.types.beta.threads.image_url_content_block import ImageURLContentBlock
from io import BytesIO
from main import BOT_HANDLE
from func_calling import search_google, get_weather, call_tools
from google.cloud.exceptions import NotFound

def check_thread(chat_id: str, collection):
    """Checks if an OpenAI's thread is assigned to a specific TG chat_id in Firebase database"""
    result = collection.document(chat_id).get(['thread','voice']).to_dict()
    if len(result)>0:
        return result['thread'], result['voice']
    return False, False

def push_to_firebase(chat_id: str, thread_id: str, collection, voice = 'onyx'):
    """updates thread and voice information for a specific chat in Firebase database"""
    try:
        collection.document(chat_id).update({'thread':thread_id, 'voice':voice})
    except NotFound:
        collection.document(chat_id).create({'thread':thread_id, 'voice':voice}, chat_id)


async def delete_img_messages(client: OpenAI, thread_id:str):
    """specific function to delete messages with image links after they've been processed.
    This is due to link expiration in TG and OpenAI's subsequent issues with thread calls
    """
    all_messages = client.beta.threads.messages.list(thread_id = thread_id, limit = 100)
    img_messages = [x for x in all_messages if len(x.content) > 1]
    img_message_ids = [x.id for x in img_messages if isinstance(x.content[1], ImageURLContentBlock)]
    for img_message_id in img_message_ids:
        if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
            print(f'Deleting message {img_message_id}') # for test bot
        try:
            client.beta.threads.messages.delete(message_id = img_message_id, thread_id=thread_id)
        except:
            pass

async def process_text(
        text_input: str,
        client: OpenAI,
        assistant_id: str,
        thread_id: str,
        voice_bool: bool = False,
        voice = 'onyx',
        messages: List[dict] = None,
        **kwargs
        ) -> Union[str, tuple[bytes,str]]:
    if not (tools:= kwargs.get('tools')):
        pass
    msg_created = None
    if not messages:
        messages = [{'type':'text','text':text_input}]
    try:
        msg_created = client.beta.threads.messages.create(
            thread_id = thread_id,
            content = messages,
            role = 'user'
            )
        current_run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id,
            additional_instructions='You reply in the shortest, most concise manner, unless instructed otherwise.',
            tools = tools
            )
        if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
            print(current_run.status) # for test bot
        if current_run.status == 'requires_action':
            tool_calls = current_run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = call_tools(tool_calls)
            if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
                print('running tool outputs') # for test bot
            current_run = client.beta.threads.runs.submit_tool_outputs_and_poll(
                thread_id=thread_id,
                run_id=current_run.id,
                tool_outputs=tool_outputs
                )
            if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
                print(f'functions processed, func_run status is {current_run.status}')
            if current_run.status == 'requires_action':
                print(current_run.status)
                return 'Run not completed'

        elif current_run.status == 'expired':
            return "Timeout on OpenAI side, please try again"
        elif current_run.status == 'failed':
            if current_run.last_error.code == 'invalid_image':
                del_task = delete_img_messages(client, thread_id)
                response = 'Sorry, need to clean up old TG images from my queue, their links are expired.\nPlease try in a few seconds.'
                await del_task
            else:
                return f'Sorry, error occurred: {current_run.last_error}. Please try again.'
        if current_run.status == 'completed':
            thread_messages = client.beta.threads.messages.list(thread_id)
            response = thread_messages.data[0].content[0].text.value
        else:
            response = f"run didn't complete, status {current_run.status}, last error: {current_run.last_error}"
            cancelled_run = client.beta.threads.runs.create_and_poll(run_id = current_run.id, thread_id=thread_id)
        if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
            print(f'Latest message from openai: {response}')

    except Exception as e:
        print(e)
        response = 'Sorry, something went wrong on OpenAI side'
    finally:
        if msg_created and len(msg_created.content)>1:
            if isinstance(msg_created.content[1], ImageURLContentBlock):
                if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
                    print(f'Deleting message {msg_created.id}') # for test bot
                try:
                    client.beta.threads.messages.delete(message_id=msg_created.id, thread_id=thread_id)
                except:
                    pass
    if not voice_bool:
        return response
    else:
        voice_response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=response,
        )
        voice_response = BytesIO(voice_response.content)
        voice_response.name = 'response.ogg'
    return (voice_response,response)

async def image(image: str, caption: str, client: OpenAI, assistant_id: str, thread_id: str, voice_bool: bool = False):
    """separate OpenAI call for Vision capabilities - describe and answer questions about images"""
    if not caption:
        caption = 'What is in these images?'
    messages = [
        {'type':'text','text':caption},
        {'type':'image_url', 'image_url':{'url':image}}
        ]
    try:
        response = await process_text(
            text_input = None,
            client = client,
            assistant_id = assistant_id,
            thread_id = thread_id,
            voice_bool = voice_bool,
            messages = messages,
            tools = []
            )
    except Exception as e:
        print(f'Error while processing image:\n{e}')
        response = "Sorry, couldn't process the image, please try again later"
    return response

def transcribe_audio(voice_input:bytes, client: OpenAI):
    """helper function that transcribes voice messages for further processing"""
    try:
        transcription = client.audio.transcriptions.create(file = voice_input, model = 'whisper-1')
        response = transcription.text
    except Exception as e:
        print(e)
        response = "Can't transcribe audio, please try again a bit later"
    return response
