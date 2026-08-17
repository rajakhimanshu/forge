from tools.llm_router import safe_print
with open("tools/pydantic_models.py", "r", encoding="utf-8") as f:
    text = f.read()

# Replace all empty string defaults in models (but keep for failed/error_message)
text = text.replace(': str = ""', ': str')
text = text.replace(': str = \'\'', ': str')
text = text.replace(': int = 0', ': int')
text = text.replace(': bool = False', ': bool')

# We must restore the defaults for `failed` and `error_message`
text = text.replace('failed: bool\n', 'failed: bool = False\n')
text = text.replace('error_message: str\n', 'error_message: str = ""\n')
text = text.replace('failed: bool\r\n', 'failed: bool = False\r\n')
text = text.replace('error_message: str\r\n', 'error_message: str = ""\r\n')

with open("tools/pydantic_models.py", "w", encoding="utf-8") as f:
    f.write(text)

safe_print("Replaced defaults.")