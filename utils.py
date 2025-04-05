import os
from box import ConfigBox
from box.exceptions import BoxValueError
from pathlib import Path
import yaml
import json
import re
from langchain.agents import Tool
from langchain_experimental.utilities import PythonREPL

def read_yaml(path_to_yaml: Path) -> ConfigBox:  # Input Arguments -> Output Argument Type
    """
    Reads yaml file and returns
    Args:
        path_to_yaml: Path input
    Raises:
        ValueError: If file is empty
        e: empty file
    Returns:
        ConfigBox: ConfigBox Type
    """
    try:
        with open(path_to_yaml, 'r') as file:
            content = ConfigBox(yaml.safe_load(file))
            return ConfigBox(content)
    except BoxValueError:
        raise ValueError(f"Empty file: {path_to_yaml}")
    except Exception as e:
        return e


def extract_javascript_code(response):
    # Use regular expression to find the JavaScript code block
    pattern = re.compile(r'```javascript(.*?)```', re.DOTALL)
    match = pattern.search(response)
    if match:
        # Extract and return the JavaScript code
        javascript_code = match.group(1).strip()
        return javascript_code
    else:
        return None
    
def python_code(response):
    # Use regular expression to find the JavaScript code block
    pattern = re.compile(r'```python(.*?)```', re.DOTALL)
    match = pattern.search(response)
    if match:
        # Extract and return the JavaScript code
        python_code = match.group(1).strip()
        return python_code
    else:
        return None
