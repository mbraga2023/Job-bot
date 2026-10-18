import json
import time
import ollama

prompt = """
Extract these fields from the job listing:
title, seniority, remote, evidence.

Return only JSON.

Software Quality Engineer II
Location: Brazil - Remote
Requirements:
- 2+ years of software testing
- API and automation testing
"""

start = time.perf_counter()

response = ollama.chat(
    model="qwen3:4b",
    messages=[{"role": "user", "content": prompt}],
    think=False,
    format="json",
    options={
        "temperature": 0,
        "num_predict": 150,
    },
)

print("Thinking:", response.message.thinking)
print("Answer:", response.message.content)
print(f"Elapsed: {time.perf_counter() - start:.2f}s")
print("Tokens generated:", response.get("eval_count"))

try:
    print(json.loads(response.message.content))
except json.JSONDecodeError:
    print("Invalid JSON")