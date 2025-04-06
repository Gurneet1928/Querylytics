from flask import Flask, render_template, jsonify, request, Response, stream_with_context
import os
from flask_cors import CORS
import numpy as np
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import get_openai_callback
import json
from langchain.agents import tool
from dataclasses import dataclass
from utilities.utils import read_yaml, extract_json_sequence
from utilities import logger
from pathlib import Path
from langchain_experimental.agents import create_csv_agent, create_pandas_dataframe_agent
from langchain.agents import AgentType
import re
import logging
from io import StringIO


# Declare Empty Dataframe
df = pd.DataFrame()
CONFIG_FILE_PATH = "config.yaml"             # Load Configuration File

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
        try:
            logger.info("\n--------------------------------------- Initializing Prompt Call ---------------------------------------")
            file = request.files.get('file')
            prompt = request.form.get('prompt')
            df = pd.read_csv(file)
            logger.info("------ STEP 1: READ DATASET AND USER PROMPT ------")
            logger.info("Dataset Head (features x 5): \n{}\n".format(df.head().to_markdown()))
            logger.info("------ User Prompt: {} ------".format(prompt))
            llm_obj = langchain_analyst()
            llm_obj.load_dataframe(df)
            llm_obj.initializeLLM()
            response = llm_obj.get_llm_response(prompt)
            logger.info("--------- LLM Response --------- \n{}".format(response[0]))
            logger.info("\n--------------------------------------- Prompt Call Ends Here ---------------------------------------")
            final_response = {
                    "insight": extract_json_sequence(response[0]),
                    "cost": response[1],
            }
            logger.info(f"\n----------- Sending Final Answer as: {final_response} -----------")
            return final_response
        except Exception as e:
            final_response = {
                    "insight": {"insight": f"Error while Parsing Response from LLM.\nException: {e}", "plot": ""},
                    "cost": "0.0",
            }
            return final_response

# Dataclasses for Storing Model Credentials and Configurations
@dataclass(frozen=False)
class ConfigCreds:
    model_name: str
    endpoint: str

@dataclass(frozen=False)
class ModelConfig:
    temperature: int
    max_retries: int
    max_tokens: int

# Python Class for Langchain Agent
class langchain_analyst:
    def __init__(self, config_path = CONFIG_FILE_PATH):
        try:
            self.creds = ConfigCreds
            content = read_yaml(Path(config_path))  # Read CONFIG file
            self.creds.model_name = content.LMStudio_Credentials.model_name
            self.creds.endpoint = content.LMStudio_Credentials.endpoint

            self.config = ModelConfig
            self.config.temperature = content.model_behaviour.temperature
            self.config.max_retries = content.model_behaviour.max_retries
            self.config.max_tokens = content.model_behaviour.max_tokens

            self.system_prompt = content.system_prompt

        except Exception as e:
            raise e
    
    def load_dataframe(self, df):
        self.df = df

    def initializeLLM(self):
        """
        Initialize AzureOpenAI Instance for LangchainAgents
        Args:
            None
        Returns:
            None
        """
        try:
            llm = ChatOpenAI(
                model=self.creds.model_name,
                base_url=self.creds.endpoint,
                api_key="1234",
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            self.df_agent = create_pandas_dataframe_agent(
                llm=llm,
                df=[self.df],
                agent_type="openai-tools",
                prefix="Remove any ` from the Action Input. Assume the dataset is named 'temp.csv' and already loaded into memory",
                verbose=True, 
                allow_dangerous_code=True, 
                return_intermediate_steps= True,
                agent_executor_kwargs={"handle_parsing_errors": True},
            )                         
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
        if os.path.exists("frontend/graph.json"):
            os.remove("frontend/graph.json")
            logger.info("---- Removing previous saved graph ---- ")

        with get_openai_callback() as cb:
            agent = self.df_agent
            '''response = list(self.agent_executor.stream({"input":msg}))'''
            logger.info("STEP 3: Generating LLM Response")
            response = agent.invoke(self.system_prompt.format(dhead=self.df.head().to_markdown(),input=msg))
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