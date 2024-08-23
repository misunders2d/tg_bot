import os
from dotenv import load_dotenv
_ = load_dotenv('.env')

import requests, json, chardet
from serpapi import GoogleSearch
from openai import OpenAI

SERP_API_KEY = os.getenv('SERP_API')
WEATHER_API_KEY = os.getenv('WEATHER_API')

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
        try:
            func_response = globals()[func_name](attributes)
        except:
             # we just tell openAi we couldn't :)
            func_response = { "status" : f'Error in function call {func_name}({t.function.arguments})'}
        tool_outputs.append(  { "tool_call_id": t.id , "output": json.dumps(func_response) })
    return tool_outputs

def search_google(search_query, language = 'en', num = 3):
    search = GoogleSearch({'q':search_query, 'api_key':SERP_API_KEY, 'language':language, 'num':num})
    result = search.get_dict()
    answer = ''
    answer += result.get('answer_box',{}).get('result','\n')
    answer += result.get('knowledge_graph',{}).get('description','\n')
    organic = ' More details below\n\n'+ '\n\n'.join([
        ', '.join(
        [
            result.get('organic_results',{})[i].get('title','\n'),
            result.get('organic_results',{})[i].get('link','\n'),
            result.get('organic_results',{})[i].get('snippet','\n')
            ]
        )
         for i in range(num)
        ])
    answer += organic
    return answer.strip()
    
def get_weather(location = 'Киев', units = 'temp_c'):
    base_url = 'http://api.weatherapi.com/v1'
    
    # forecast_days = 3
    
    current_weather = f'{base_url}/current.json?key={weather_api_key}&q={location}&aqi=no'
    # forecast_weather =f'{base_url}/forecast.json?key={weather_api_key}&q={location}&days={forecast_days}&aqi=no&alerts=no'    
    result = requests.get(current_weather)
    current_json = result.json()
    temp = current_json['current'][units]
    text = current_json['current']['condition']['text']
    # forecast = requests.get(forecast_weather)
    
    return f'Current temperature is {temp}, current condition is {text}'

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
