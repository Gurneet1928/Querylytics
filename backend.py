from flask import Flask, render_template, jsonify, request, Response, stream_with_context
import os
from flask_cors import CORS
import numpy as np
import pandas as pd
from langchain_openai.chat_models.azure import AzureChatOpenAI
# from langchain.agents import AgentExecutor, OpenAIFunctionsAgent
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain_experimental.tools import PythonREPLTool
from langchain_community.callbacks import get_openai_callback
import json
from langchain.agents import tool
from dataclasses import dataclass
from common.utils import read_yaml
from common import logger
from pathlib import Path
from langchain_experimental.agents import create_csv_agent
from langchain.agents import AgentType
import re
import logging

## Uncomment only while using a custom agent
#from langchain.agents.format_scratchpad.openai_tools import (
#    format_to_openai_tool_messages,
#)
#from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
#from langchain.agents import AgentExecutor


# -------------------- Main prompt ------------------------------
# Generates python plotly code, executes it and then stores the plot as graph.json in local directory.
system_prompt = """
You work for Seagate Technologies as a data analyst assistant.
Prior to utilizing the dataframe, it is crucial to comprehend its properties. The output of `df.head().to_markdown()' is as follows:
<df>
{dhead}
</df>
As part of your task, you will clean the data, offer insights into it, run statistical tests on it, and arrange the data columns correctly.
Assume that the data has been imported into the Python variable `df`. Don't use any data samples while charting; only use this dataframe.
These rows are intended to inform you about the structure and organization of the dataframe; they are not intended to be used exclusively for answering questions.
You may also run intermediate queries to perform exploratory data analysis and obtain additional information as needed.
Observe the following when responding to inquiries from users:

1. If the user requests that data be retrieved from the database, return the SQL query.
2. Carry out the requested data cleansing or update.
3. Provide a comprehensive report with the values and outcomes if a statistical test is requested.
4. Encode by default any category columns in the data before using them for analysis. Your final response should also specify the encoding method used for this data.
5. Use only plotly to plot the data. In graphs, use any plotly color scheme. Give each variable a name and display the legend. To make it look nice, use appropriate variable names, axis names, etc. Print the Plotly code for the graphs after they have been plotted. Sandbox API should not be used for this purpose. Analyze the graph you created and provide the user with your conclusions. 
6. Complete the necessary operations in whatever operation the user requests, include the data modifications, and provide a description of the data in your final response. 
7. If any data alteration is necessary during the procedure, make the necessary modifications and notify the user of them.
8. Include your last operation and its result to provide a detailed summary statistics to user query.
9. You can run Python routines by utilizing the [pythonREPL] that is available to you.
10. Instead of using 'fig.show()', use 'pio.write_json(fig, file='javascript_research/graph.json', pretty=True)' in the local directory to export the finished graph in a plotly json file format. Ensure that name = 'javascript_research/graph.json' is the only way it is saved. Only plot one plot per user query.
As an illustration:
<question>How old is Jane?</question>
<logic>Use `person_name_search` since you can use the query `Jane`</logic>

<question>Plot a bar plot for cars vs years</question>
<logic>Write a Python plotly code which can generate the required graph/plot, execute the code using [pythonREPL] and save it as 'javascript_research/graph.json' in local directory.</logic>

After answering the question, provide 3 suggestions the user can ask next in format:
1. <<suggestion1>>\n
2. <<suggestion2>>\n
3. <<suggestion3>>\n

Let's begin 

Question: {input}
"""

system_prompt_2 = """
You are a data analyst assitant at Seagate Technology.
It is important to understand the attributes of the dataframe before working with it. This is the result of running `df.head().to_markdown()`:

<df>
{dhead}
</df>

Your work includes cleaning the data, provide insights into the data, performing statistical tests on data, converting data columns in proper format.
Assume that the data is loaded in variable 'df' in python. Use this dataframe for plotting and do not use any data samples.
You are not meant to use only these rows to answer questions - they are meant as a way of telling you about the shape and schema of the dataframe.
You also do not have use only the information here to answer questions - you can run intermediate queries to do exporatory data analysis to give you more information as needed.
Keep track of the following when resolving user queries:

1. Return SQL query in case user asks to fetch the data from Database.
2. If data cleaning/modification is asked, perform the operation.
3. If any statistical test is asked to perform, report the values and results in a detailed.
4. If the data has any categorical columns, encode them by default and then use for analysis. Also include the encoding method this data in your final answer.
5. For plotting the data use only plotly. Use plotly color scheme in graphs. Provide name to each variable and show legend. User proper variable names, axis names, legends, etc. to make it beautiful. Once the graphs are plotted, print the Javascript Plotly code for it. Do not use sandbox API for this purpose. Interpret the graph you plotted and share the insights with the user. 
6. In any operation asked by the user, perform the required operations, include the changes made in data and also describe the data in your final answer. 
7. During the operation, if any data modification is required, do it and report the user about the changes made.
8. Include your last operation and its result to provide a detailed summary statistics to user query.
9. You have access to a [pythonREPL], which you can use to execute python codes.
10. Do not use 'fig.show()' and plot only a single plot per user query, just export the final graph in plotly json file format using 'pio.write_json(fig, file='javascript_research/graph.json', pretty=True)' in local directory. Make sure to save it only using name = 'javascript_research/graph.json'. 
For example:

<question>How old is Jane?</question>
<logic>Use `person_name_search` since you can use the query `Jane`</logic>

<question>Plot a bar plot for cars vs years</question>
<logic>Write a Python plotly code which can generate the required graph/plot, execute the code using [pythonREPL] and save it as 'javascript_research/graph.json' in local directory.</logic>

After answering the question, provide 3 suggestions the user can ask next in format:
1. <<suggestion1>>\n
2. <<suggestion2>>\n
3. <<suggestion3>>\n

Let's begin 

Here is the user question: 
{input}
"""


# pio.write_html(fig, file='javascript_research/graph.html', auto_open=False) << for HTML Output

# -------------------- Backup prompt ------------------------------
# To be used for Generating Javascript Codes, in case required.

_ = """You are a data analyst assistant at Seagate Technology. It is important to understand the attributes of the dataframe before working with it. This is the result of running df.head().to_markdown():

<df> {dhead} </df>

Your work includes cleaning the data, providing insights into the data, performing statistical tests on the data, and converting data columns into the proper format. Keep track of the following when resolving user queries:

0. (Important) Assume that the data is loaded in an array named 'fileInput' in the JavaScript code. The code should only include the loading of the data from this array directly and should not use any samples. You are not meant to use only these rows to answer questions - they are meant as a way of telling you about the shape and schema of the dataframe. You also do not have to use only the information here to answer questions - you can run intermediate queries to do exploratory data analysis to give you more information as needed. The data has not been preprocessed in any form, so include these steps as well.
1. Return SQL query in case the user asks to fetch the data from the database.
2. If data cleaning/modification is required, perform the operation.
3. If any statistical test is asked to perform, report the values and results in detail.
4. If the data has any categorical columns, encode them by default and then use them for analysis. Also, include the encoding method used in your final answer.
5. For plotting the data, use only Plotly. Use Plotly color scheme in graphs. Use proper variable names, axis names, legends, etc., to make it beautiful. Once the graphs are plotted, print the JavaScript Plotly code for it. Do not use the sandbox API for this purpose. Interpret the graph you plotted and share the insights with the user.
6. In any operation asked by the user, perform the required operations, include the changes made in the data, and also describe the data in your final answer.
7. Include your last operation and its result to provide detailed summary statistics to the user query.
8. In any case, do not share the Python code with the user.
9. Only print the JavaScript Plotly code for use in the front end with the division tag = “myDiv”. The code generated will be used inside a function, so don't create any function, just create a code snippet.
10. Use the following format to respond to queries:
...code here (if any)...
...insights and explanation... 
...suggestions for next ste...

11. Import any necessary JavaScript libraries if required. Use the following format for writing codes, where fileInput is a data Array in Javascript:
... 
var tempData = fileInput;
..... rest of code goes here .....
...

For example:

<question>How old is Jane?</question> 
<logic>Use person_name_search since you can use the query Jane</logic>

<question>Plot a bar plot for cars vs years</question> 
<logic>Write a JavaScript Plotly code which can generate the required graph/plot, which loads data from array fileInput and returns a plotly code which displays the graph in 'myDiv' division of HTML frontend.</logic>

After answering the question, provide 3 suggestions the user can ask next in the format:

1. <<suggestion1>>\n
2. <<suggestion2>>\n
3. <<suggestion3>>\n

Let's begin.
"""

# Declare Empty Dataframe
df = pd.DataFrame()
CONFIG_FILE_PATH = "config/config.yaml"             # Load Configuration File

# Define headers for Flask

header = {
    'Content-type':'application/json', 
    'Accept':'application/json'
}


app = Flask(__name__)
CORS(app)

# Function to be called using POST.
@app.route('/data', methods=['POST', 'GET'])
def main_function():
    global df
    if request.method == "POST":
        logger.info("\n--------------------------------------- Initializing Prompt Call ---------------------------------------")
        # Python Response
        request.headers = header    # type: ignore
        data = request.data.decode("UTF-8")
        prompt = data.split("]")[1]
        json_data = str(data.split("]")[0]) + "]"
        df = pd.read_json(json_data)
        df.to_csv("temp.csv", index=False)
        logger.info("STEP 1: READ DATASET AND USER PROMPT")
        logger.info("Dataset Head (features x 5): \n{}\n".format(df.head().to_markdown()))
        logger.info("User Prompt: {} ".format(prompt))
        llm_obj = langchain_analyst()
        llm_obj.initializeLLM()
        response = llm_obj.get_llm_response(prompt)
        logger.info("--------- LLM Response --------- \n{}".format(response[0]))
        logger.info("\n--------------------------------------- Prompt Call Ends Here ---------------------------------------")
        final_response = {
                "insight": response[0],
                "cost": response[1],
        }
        if os.path.exists("javascript_research/graph.json"):
            logger.info("Adding Graph to the Response")
            with open("javascript_research/graph.json") as j:
                graph_json = json.loads(j.read())
                final_response["plot"] = graph_json
            # os.remove("javascript_research/graph.json")
        else:
            logger.info("No Graph Required")
            final_response["plot"] = "none"
        return final_response
        # def generate():
        #     response = llm_obj.get_llm_response(prompt)
        #     logger.info("--------- LLM Response --------- \n{}".format(response[0]))
        #     logger.info("\n--------------------------------------- Prompt Call Ends Here ---------------------------------------")
        #     final_response = {
        #         "insight": response[0],
        #         "cost": response[1],
        #     }
        #     for word in final_response["insight"].split():
        #         yield f"data: {word} \n\n"
        #         logger.info(f"Sent word: {word}")
            
        # return Response(stream_with_context(generate()), content_type='text/event-stream', mimetype='text/event-stream', headers=header)
            
        # Working with JS responses
        _ = '''if "```javascript" in response:
            code = extract_javascript_code(response)
            print(code)
        if code is not None:
            other_response = response.replace(code, "")
            final_response = {
                "code": code,
                "response": response
            }
        else:
            final_response = {
                "repsonse": response
            }
        return response'''

    return "Using Get Method"

# Custom tool which does nothing
@tool
def nothing_tool(word: None) -> None:
    """Returns Nothing."""
    return None

tool = [nothing_tool]

# Dataclasses for Storing Model Credentials and Configurations
@dataclass(frozen=False)
class ConfigCreds:
    model_name: str
    api_token: str
    azure_endpoint: str
    api_version: str
    deployment_name: str

@dataclass(frozen=False)
class ModelConfig:
    temperature: int
    max_retries: int


# Python Class for Langchain Agent
class langchain_analyst:
    def __init__(self, config_path = CONFIG_FILE_PATH) -> None:
        try:
            self.creds = ConfigCreds
            content = read_yaml(Path(config_path))  # Read CONFIG file
            
            self.creds.model_name = content.Azure_OpenAI_credentials.model_name
            self.creds.api_token = content.Azure_OpenAI_credentials.api_token
            self.creds.azure_endpoint = content.Azure_OpenAI_credentials.azure_endpoint
            self.creds.api_version = content.Azure_OpenAI_credentials.api_version
            self.creds.deployment_name = content.Azure_OpenAI_credentials.deployment_name

            self.config = ModelConfig
            self.config.temperature = content.model_behaviour.temperature
            self.config.max_retries = content.model_behaviour.max_retries

        except Exception as e:
            raise e
        
    def initializeLLM(self):
        """
        Initialize AzureOpenAI Instance for LangchainAgents
        Args:
            None
        Returns:
            None
        """
        try:
            global tool
            llm = AzureChatOpenAI(
                name = self.creds.model_name,
                api_key = self.creds.api_token,
                azure_endpoint = self.creds.azure_endpoint,
                api_version = self.creds.api_version,
                azure_deployment = self.creds.deployment_name,
                temperature = self.config.temperature,
                max_retries = self.config.max_retries,
                streaming=False,
            )

            # Using Custom Agent - PLAN B
            '''llm_tools = llm.bind_tools(tool)
            
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system", 
                        system_prompt.format(dhead=df.head().to_markdown()),
                    ),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                    ("user", "{input}"),
                ]
            )

            agent = (
                {
                    "input": lambda x: x["input"],
                    "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                        x["intermediate_steps"]
                    ),
                }
                | prompt
                | llm_tools
                | OpenAIToolsAgentOutputParser()
            )
            
            self.agent_executor = AgentExecutor(agent=agent, tools=tool, verbose=True, stream_runnable=False, handle_parsing_errors=True)'''

            self.df_agent = create_csv_agent(llm=llm,
                                                 path="temp.csv",
                                                 agent_type=AgentType.OPENAI_FUNCTIONS,
                                                 prefix="Remove any ` from the Action Input. Assume the dataset is named 'temp.csv' and already loaded into memory",
                                                 #verbose=True, 
                                                 allow_dangerous_code=True, 
                                                 return_intermediate_steps= True,
                                                 agent_executor_kwargs={"handle_parsing_errors": True},
                                                 )                          # CSV Agent - Plan A
            self.df_agent.agent.stream_runnable=False
            logger.info("STEP 2: CREATE CSV AGENT - SUCCESS")
        except Exception as e:
            logger.info("STEP 2: CREATE CSV AGENT - FAILED")
            print(e)

    def get_llm_response(self, msg: str):

        # To be used when storing .html as response.
        '''if os.path.exists("javascript_research/graph.html"):
            os.remove("javascript_research/graph.html")
            print(">> graph.html removed")'''
        
        # To be used when storing .json as response. Clears previous temporary graph file and makes space for new one.
        if os.path.exists("javascript_research/graph.json"):
            os.remove("javascript_research/graph.json")
            logger.info("---- Removing previous saved graph ---- ")

        with get_openai_callback() as cb:
            agent = self.df_agent
            '''response = list(self.agent_executor.stream({"input":msg}))'''
            logger.info("STEP 3: Generating LLM Response")
            response = agent.invoke(system_prompt.format(dhead=df.head().to_markdown(),input=msg))
            logger.info("-------- Intermediate Steps --------")
            for step in response["intermediate_steps"]:
                stp = step[0]
                logger.info("--(3.1)-- Tool: %s", stp.tool)
                try:
                    logger.info("--(3.2)-- Tool Input: \n%s", stp.tool_input['query'])
                except:
                    logger.info("--(3.2)-- Tool Input: \n%s", stp.tool_input)
                logger.info("--(3.3)-- Log: \n%s", stp.log)
            logger.info("--------- Tokens Used --------- \n{}".format(cb))
            return [response["output"], cb.total_cost]


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)