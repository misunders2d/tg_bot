import os
from dotenv import load_dotenv
_ = load_dotenv('.env')

import requests, json, chardet
# from serpapi import GoogleSearch
# from openai import OpenAI

SERP_API_KEY = os.getenv('SERP_API')
WEATHER_API_KEY = os.getenv('WEATHER_API')
GOOGLE_SEARCH_API = os.getenv('GOOGLE_SEARCH_API')
GOOGLE_SEARCH_ENGINE_ID = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
BOT_HANDLE = os.getenv('BOT_HANDLE')

def call_tools(tool_calls):
    """ Process "tool_calls that come straight from openai's run.
        Extracts function names and arguments and runs them one by one.
        Appends results to "tool_outputs" list and passes them back
        to openai to complete the run
    """
    tool_outputs = []
    for t in tool_calls:
        func_name = t.function.name
        attributes = json.loads(t.function.arguments)
        if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
            print(func_name, attributes)
        try:
            func_response = globals()[func_name](attributes)
        except:
             # we just tell openAi we couldn't :)
            func_response = { "status" : f'Error in function call {func_name}({t.function.arguments})'}
        tool_outputs.append(  { "tool_call_id": t.id , "output": json.dumps(func_response) })
    if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
        print('tool_outputs: ',tool_outputs)
    return tool_outputs

def search_google(search_query, language = 'en', num = 2, api_key = SERP_API_KEY):
    """
    basic Google search to provide top level results for any updated information that the bot has no access to
    """
    ### google custom search calling
    url = 'https://www.googleapis.com/customsearch/v1'
    params = {
        'key': GOOGLE_SEARCH_API,
        'cx': GOOGLE_SEARCH_ENGINE_ID,
        'q': search_query.get('search_query'),
        'hl':language,
        'num':num
    }
    print(params) # TODO remove
    # Make the request
    response = requests.get(url, params=params)
    if response.status_code == 200:
        results = response.json()
        answer = ''
        for item in results.get('items', []):
            answer += (f"Title: {item['title']}\n")
            answer += (f"Link: {item['link']}\n")
            answer += (f"Quick info: {item['snippet']}\n\n")
    else:
        print('Error:', response.status_code, response.text)    
    # print('\n\n',result) # TODO remove
    # print(f"Here's the information from google search: {answer.strip()}")
    return f"Here's the information from google search: {answer.strip()}"
    
def get_weather(location = 'Киев', units = 'temp_c'):
    """Check basic weather data for requested location. Prompt the user for location if the details are unclear"""
    base_url = 'http://api.weatherapi.com/v1'
    
    # forecast_days = 3
    
    current_weather = f'{base_url}/current.json?key={WEATHER_API_KEY}&q={location}&aqi=no'
    # forecast_weather =f'{base_url}/forecast.json?key={weather_api_key}&q={location}&days={forecast_days}&aqi=no&alerts=no'    
    result = requests.get(current_weather)
    current_json = result.json()
    temp = current_json['current'][units]
    text = current_json['current']['condition']['text']
    icon_link = current_json['current']['condition']['icon']
    # forecast = requests.get(forecast_weather)
    result = f"""Current temperature is {temp}, current condition is {text}.
    Make sure to include the raw link: https://{icon_link} (plain text, NOT markdown)
    """

    return result

def parse_json_conditions(file):
    """
    Future function to parse multi-language weather conditions from "conditions.json" file
    """
    with open(file, 'rb') as f:
        result = chardet.detect(f.read())
        encoding = result['encoding']

    with open('conditions.json', encoding=encoding) as conditions_file:
        weather_conditions = json.load(conditions_file)
    return weather_conditions