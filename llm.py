"""
Module tuong tac voi Ollama LLM.

chat_json(): goi Ollama o che do JSON, tu retry, tra {'error': ...} neu that bai.
Moi noi trong project chi dung DUY NHAT ham nay de goi LLM -> de dem so lan goi,
de monkeypatch trong test (xem tests/conftest.py) va de doi model o mot cho.
"""
import json
import sys
from typing import Any, Dict, List

import ollama

from config import MODEL_NAME, MAX_RETRIES, TEMPERATURE, OLLAMA_HOST


def chat_json(prompt: str, system_prompt: str = '', schema_hint: str = '') -> Dict[str, Any]:
    """
    Goi Ollama chat kem theo format JSON.
    Neu that bai se thu lai (retry) va tra ve {'error': ...} neu van that bai.

    schema_hint duoc noi vao system prompt; neu khong co system_prompt thi tu tao
    mot system message chi chua schema (truoc day schema_hint bi bo im lang).
    """
    client = ollama.Client(host=OLLAMA_HOST)
    messages: List[Dict[str, Any]] = []

    system = system_prompt or ''
    if schema_hint:
        system = (system + "\n\n" if system else "") + \
                 f"Require output in JSON format. Schema: {schema_hint}"
    if system:
        messages.append({'role': 'system', 'content': system})

    messages.append({'role': 'user', 'content': prompt})

    attempts = MAX_RETRIES + 1   # 1 lan goi dau + MAX_RETRIES lan thu lai
    for attempt in range(1, attempts + 1):
        try:
            response = client.chat(
                model=MODEL_NAME,
                messages=messages,
                format='json',
                options={'temperature': TEMPERATURE}
            )

            content = response.get('message', {}).get('content', '')
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                print(f"Attempt {attempt}/{attempts}: khong parse duoc JSON. Content: {content}",
                      file=sys.stderr)
                messages.append({'role': 'assistant', 'content': content})
                messages.append({'role': 'user', 'content':
                                 "Error: The previous response was not valid JSON. "
                                 "Please provide a valid JSON object."})

        except Exception as e:
            print(f"Attempt {attempt}/{attempts}: loi goi Ollama API - {e}", file=sys.stderr)

    return {'error': f'Khong lay duoc JSON hop le sau {attempts} lan goi'}
