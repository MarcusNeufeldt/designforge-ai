from flask import Flask, send_file, request, jsonify, send_from_directory
import requests
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import os
import time
import re
import logging

load_dotenv()

app = Flask(__name__, static_folder='static')

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

prompt_history = []

def extract_html(content):
    match = re.search(r'<!DOCTYPE html>.*?</html>', content, re.DOTALL)
    if match:
        return match.group(0)
    return content  # Return original content if no HTML found

def query_llm(llm, prompt, injected_html=None, previous_content=None):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = []
    if previous_content:
        messages.append({
            "role": "assistant",
            "content": f"I previously generated this HTML:\n\n{previous_content}"
        })

    if injected_html:
        messages.append({
            "role": "user",
            "content": f"Here's some existing HTML code:\n\n{injected_html}\n\nPlease use this as a starting point and modify it according to the following prompt:"
        })

    messages.append({
        "role": "user",
        "content": f"Generate HTML code for a {prompt}. You are invited to use CSS styling, but not in a seperate file. Your response must start with '<!DOCTYPE html>' and end with '</html>'. Do not include any explanations or additional text outside of the HTML code."
    })

    data = {
        "model": llm,
        "messages": messages
    }

    start_time = time.time()
    debug_info = {
        "request": {
            "url": OPENROUTER_API_URL,
            "headers": headers,
            "data": data
        }
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        end_time = time.time()
        content = result['choices'][0]['message']['content'] if 'choices' in result else ''
        extracted_html = extract_html(content)

        debug_info["response"] = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": result
        }

        return {
            'llm': llm,
            'content': extracted_html,
            'response_time': round(end_time - start_time, 2),
            'token_count': result.get('usage', {}).get('total_tokens', 'N/A')
        }, debug_info
    except requests.exceptions.RequestException as e:
        debug_info["error"] = str(e)
        return {'llm': llm, 'error': str(e)}, debug_info

@app.route('/')
def index():
    return send_file('static/index.html')

@app.route('/styles.css')
def styles():
    return send_file('static/styles.css')

@app.route('/app.js')
def app_js():
    return send_file('static/app.js')

@app.route('/api/compare', methods=['POST'])
def api_compare():
    data = request.json
    prompt = data['prompt']
    selected_llms = data.get('selected_llms', [])
    injected_html = data.get('injected_html')

    if prompt not in prompt_history:
        prompt_history.append(prompt)
        prompt_history[:] = prompt_history[-10:]  # Keep only the last 10 prompts

    results = []
    debug_info = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_llm = {executor.submit(query_llm, llm, prompt, injected_html): llm for llm in selected_llms}
        for future in future_to_llm:
            llm = future_to_llm[future]
            try:
                result, llm_debug_info = future.result()
                results.append(result)
                debug_info[llm] = llm_debug_info
            except Exception as exc:
                print(f'{llm} generated an exception: {exc}')

    return jsonify({"results": results, "debug_info": debug_info})

@app.route('/api/reiterate', methods=['POST'])
def api_reiterate():
    data = request.json
    original_prompt = data['original_prompt']
    changes_prompt = data['changes_prompt']
    llm = data['llm']
    previous_content = data['previous_content']
    injected_html = data.get('injected_html')

    full_prompt = f"{original_prompt}. Make the following changes: {changes_prompt}"
    result, debug_info = query_llm(llm, full_prompt, injected_html, previous_content)
    return jsonify({"result": result, "debug_info": debug_info})

@app.route('/api/llms', methods=['GET'])
def get_llms():
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        logger.info(f"Fetching models from OpenRouter...")
        response = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"OpenRouter API response status: {response.status_code}")
        logger.debug(f"OpenRouter API response content: {response.text}")
        
        response_data = response.json()
        if not isinstance(response_data, dict) or 'data' not in response_data or not isinstance(response_data['data'], list):
            logger.error(f"Unexpected response format. Expected a dict with 'data' key containing a list, got: {type(response_data)}")
            return jsonify({"error": "Unexpected response format from OpenRouter API"}), 500
        
        models = response_data['data']
        model_ids = [model['id'] for model in models if isinstance(model, dict) and 'id' in model]
        logger.info(f"Successfully fetched {len(model_ids)} models from OpenRouter")
        return jsonify(model_ids)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching models from OpenRouter: {str(e)}")
        return jsonify({"error": str(e)}), 500
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response: {str(e)}")
        logger.error(f"Raw response content: {response.text}")
        return jsonify({"error": "Invalid JSON response from OpenRouter API"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_llms: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/prompt_history', methods=['GET'])
def get_prompt_history():
    return jsonify(prompt_history)

if __name__ == '__main__':
    app.run(debug=True)