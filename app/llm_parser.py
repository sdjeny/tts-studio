import json
import re
from typing import List, Dict
from openai import OpenAI
from .config import SYSTEM_PROMPT

def parse_with_llm(text: str, api_base: str, api_key: str, model: str) -> List[Dict]:
    client = OpenAI(base_url=api_base, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    content = response.choices[0].message.content
    content = re.sub(r'^```json\s*|\s*```$', '', content.strip())
    return json.loads(content)
