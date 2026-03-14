from openai import OpenAI
client = OpenAI(api_key='ollama', base_url='http://localhost:11434/v1')
resp = client.chat.completions.create(
    model='qwen3:8b',
    messages=[{'role':'user','content':'BTC investment one sentence'}],
    max_tokens=50
)
print('OK:', resp.choices[0].message.content[:100])
