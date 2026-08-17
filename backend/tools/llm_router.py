import os
import json
import re
import sys
import time
import logging
import threading
import collections
from dotenv import load_dotenv
from tools.errors import PipelineError

load_dotenv()


# ── Structured file logger ────────────────────────────────────────────────────
# Writes JSON-structured lines to forge_pipeline.log alongside console output.
_log_path = os.getenv("FORGE_LOG_FILE", "forge_pipeline.log")
_file_handler = logging.FileHandler(_log_path, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter('{"time": "%(asctime)s", "level": "%(levelname)s", "msg": %(message)s}'))
_logger = logging.getLogger("forge")
_logger.setLevel(logging.DEBUG)
if not _logger.handlers:
    _logger.addHandler(_file_handler)


def safe_print(*args, **kwargs):
    """Safely print to console (Windows emoji-safe) AND write to forge_pipeline.log."""
    text = " ".join(str(a) for a in args)
    # Log to file as JSON (escape quotes so formatter is valid)
    try:
        _logger.info(json.dumps(text, ensure_ascii=False))
    except Exception:
        pass
    # Console output — strip non-ASCII on Windows to avoid 'charmap' errors
    if sys.platform == 'win32':
        text = text.encode('ascii', 'replace').decode('ascii')
    print(text, **kwargs)


# ── Global TPM Throttle Tracker ───────────────────────────────────────────────
class _TPMTracker:
    """
    Tracks estimated Groq TPM (tokens per minute) usage across all LLM calls.
    Estimates tokens from message character counts (1 token ≈ 4 chars).
    Automatically sleeps before any call that would push usage over the limit.
    """
    # Groq free-tier on-demand: ~6 000 TPM. We leave a 1 000-token buffer.
    _LIMIT = int(os.getenv("GROQ_TPM_LIMIT", "5000"))
    _WINDOW = 60  # seconds

    def __init__(self):
        self._lock = threading.Lock()
        self._calls: collections.deque = collections.deque()  # (timestamp, tokens)

    def _prune(self):
        now = time.time()
        while self._calls and now - self._calls[0][0] > self._WINDOW:
            self._calls.popleft()

    @staticmethod
    def estimate(messages) -> int:
        """Rough token estimate: total chars / 4, min 100."""
        try:
            total = sum(len(getattr(m, 'content', '') or '') for m in messages)
            return max(100, total // 4)
        except Exception:
            return 200

    def check_and_throttle(self, estimated_tokens: int, label: str = 'groq'):
        """Call BEFORE an LLM request. Sleeps if the window is nearly full."""
        # Only throttle Groq providers (not Ollama)
        if 'groq' not in label.lower() and label != 'primary' and label != 'secondary-fallback':
            return
        with self._lock:
            self._prune()
            window_tokens = sum(t for _, t in self._calls)
            if window_tokens + estimated_tokens > self._LIMIT:
                if self._calls:
                    oldest = self._calls[0][0]
                    wait = self._WINDOW - (time.time() - oldest) + 2
                    if wait > 0:
                        safe_print(
                            f'[TPM GUARD] Window ~{window_tokens} tokens used. '
                            f'Sleeping {wait:.0f}s before next call...'
                        )
                        time.sleep(wait)
                        self._prune()
            self._calls.append((time.time(), estimated_tokens))


_tpm_tracker = _TPMTracker()


def get_llm(temperature: float = 0.3):
    mode = os.getenv('LLM_MODE', 'groq')

    if mode == 'local':
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv('OLLAMA_MODEL', 'llama3.2:3b'),
            base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
            temperature=temperature
        )

    elif mode == 'groq':
        from langchain_groq import ChatGroq
        groq_model = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
        return ChatGroq(
            model=groq_model,
            api_key=os.getenv('GROQ_API_KEY'),
            temperature=temperature,
            max_retries=0
        )

    elif mode == 'gemini':
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv('GEMINI_MODEL', 'gemini-1.5-flash'),
            google_api_key=os.getenv('GOOGLE_API_KEY'),
            temperature=temperature,
            max_retries=0
        )

    else:
        raise ValueError(f'Unknown LLM_MODE: {mode}. Use local/groq/gemini')


def get_fallback_llm(temperature: float = 0.3):
    """
    Returns a fallback LLM when the primary hits rate limits.
    Order:
    1. If primary is Groq -> try a different smaller Groq model (lower TPM cost)
    2. If primary is Gemini -> try Groq
    3. Final resort: Local Ollama
    """
    mode = os.getenv('LLM_MODE', 'groq')
    groq_key = os.getenv('GROQ_API_KEY', '')

    # If primary is Groq, fallback to a lighter Groq model first (saves TPM)
    if mode == 'groq' and groq_key and 'YOUR_KEY' not in groq_key:
        from langchain_groq import ChatGroq
        fallback_model = os.getenv('GROQ_FALLBACK_MODEL', 'llama-3.1-8b-instant')
        safe_print(f'[FALLBACK] Switching to Groq ({fallback_model})...')
        return ChatGroq(
            model=fallback_model,
            api_key=groq_key,
            temperature=temperature,
            max_retries=0
        )

    # If primary is Gemini, fallback to Groq
    if mode == 'gemini' and groq_key and 'YOUR_KEY' not in groq_key:
        from langchain_groq import ChatGroq
        safe_print('[FALLBACK] Switching to Groq...')
        return ChatGroq(
            model=os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile'),
            api_key=groq_key,
            temperature=temperature,
            max_retries=0
        )

    # Final resort: Ollama (Unlimited/Free)
    ollama_model = os.getenv('OLLAMA_MODEL', '')
    if ollama_model:
        from langchain_ollama import ChatOllama
        safe_print(f'[FALLBACK] Final resort: Switching to Local Ollama ({ollama_model})...')
        return ChatOllama(
            model=ollama_model,
            base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
            temperature=temperature
        )

    return None


def get_llm_info() -> dict:
    mode = os.getenv('LLM_MODE', 'groq')

    if mode == 'local':
        return {
            'mode': 'local',
            'model_name': os.getenv('OLLAMA_MODEL', 'llama3.2:3b'),
            'is_free': True,
            'context_window': 4096,
            'tokens_per_second': '~15 (GPU)'
        }
    elif mode == 'groq':
        return {
            'mode': 'groq',
            'model_name': os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile'),
            'is_free': True,
            'context_window': 32768,
            'tokens_per_second': '~750 (API)'
        }
    elif mode == 'gemini':
        return {
            'mode': 'gemini',
            'model_name': os.getenv('GEMINI_MODEL', 'gemini-1.5-flash'),
            'is_free': True,
            'context_window': 1000000,
            'tokens_per_second': '~100 (API)'
        }
    else:
        return {
            'mode': mode,
            'model_name': 'unknown',
            'is_free': False,
            'context_window': 0,
            'tokens_per_second': 'N/A'
        }


def _coerce_types(data: dict, model_cls) -> dict:
    """Coerce string values to match Pydantic field types, including nested list items."""
    try:
        fields = model_cls.model_fields
    except AttributeError:
        return data

    for field_name, field_info in fields.items():
        if field_name not in data:
            continue
        val = data[field_name]
        annotation = field_info.annotation
        origin = getattr(annotation, '__origin__', None)

        # Handle int coercion
        if annotation is int or (origin is None and str(annotation) == "<class 'int'>"):
            try:
                data[field_name] = int(val)
            except (ValueError, TypeError):
                pass

        # Handle bool coercion
        elif annotation is bool or (origin is None and str(annotation) == "<class 'bool'>"):
            if isinstance(val, str):
                data[field_name] = val.strip().lower() not in ('false', '0', 'no', '')

        # Handle List[SomePydanticModel] — recurse into each item
        elif origin is list and isinstance(val, list):
            args = getattr(annotation, '__args__', None)
            if args and len(args) > 0:
                item_type = args[0]
                # Only recurse if the item type is a Pydantic BaseModel subclass
                try:
                    from pydantic import BaseModel as _BaseModel
                    if isinstance(item_type, type) and issubclass(item_type, _BaseModel):
                        coerced_items = []
                        for item in val:
                            if isinstance(item, dict):
                                coerced_items.append(_coerce_types(item, item_type))
                            else:
                                coerced_items.append(item)
                        data[field_name] = coerced_items
                except Exception:
                    pass

    return data


def _try_parse(json_str: str, pydantic_class, coerce: bool = True):
    """Parse a JSON string into pydantic_class with optional type coercion."""
    data = json.loads(json_str)
    if isinstance(data, dict) and coerce:
        data = _coerce_types(data, pydantic_class)
    return pydantic_class(**data)


def _extract_json_from_text(text: str) -> list[str]:
    """
    Extract all candidate JSON object strings from arbitrary text.
    Returns them largest-first (most complete candidates first).
    """
    candidates = []

    # Strategy 1: greedy {...} match (handles nested objects)
    start = text.find('{')
    while start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidates.append(text[start:i + 1])
                    break
        start = text.find('{', start + 1)

    # Strategy 2: regex fallback for smaller blobs that Strategy 1 might miss
    for blob in re.findall(r'\{[^{}]{20,}\}', text, re.DOTALL):
        if blob not in candidates:
            candidates.append(blob)

    # Sort by length descending - larger = more complete
    return sorted(candidates, key=len, reverse=True)


def build_schema_prompt(pydantic_class) -> str:
    """
    Build a compact, human-readable schema description to inject into prompts
    BEFORE the first LLM call, so the model knows the required output shape.
    """
    try:
        schema = pydantic_class.model_json_schema()
        props = schema.get('properties', {})
        required = schema.get('required', [])
        lines = [
            f'\n\n=== REQUIRED OUTPUT FORMAT ===',
            f'You MUST output a single raw JSON object (no markdown, no explanation) matching this schema:',
            f'Model: {pydantic_class.__name__}',
            '',
        ]
        for field_name, field_info in props.items():
            req_marker = ' [REQUIRED]' if field_name in required else ' [optional]'
            ftype = field_info.get('type', field_info.get('anyOf', [{}])[0].get('type', 'any'))
            desc = field_info.get('description', '')
            # Handle array types
            if ftype == 'array':
                items_type = field_info.get('items', {}).get('type', 'object')
                ftype = f'array of {items_type}'
            # Handle integer constraints
            if field_info.get('minimum') is not None or field_info.get('maximum') is not None:
                mn = field_info.get('minimum', '')
                mx = field_info.get('maximum', '')
                ftype += f' ({mn}-{mx})'
            detail = f' -- {desc}' if desc else ''
            lines.append(f'  "{field_name}": {ftype}{req_marker}{detail}')
        lines += [
            '',
            'CRITICAL TYPES:',
            '  - integer fields MUST be numbers: 8  NOT "8"',
            '  - boolean fields MUST be: true or false  NOT "true" or "false"',
            '  - string fields with min_length constraints MUST meet the minimum',
            '  - array fields with min_length constraints MUST have at least that many items',
            '  - Literal fields must use EXACTLY one of the allowed values',
            '=== END FORMAT ===',
        ]
        return '\n'.join(lines)
    except Exception as e:
        raise PipelineError('LLMRouter', f'Step failed: {str(e)}')


def _is_rate_limit_error(error_str: str) -> bool:
    """Check if the error is a rate limit / quota exhaustion error."""
    el = error_str.lower()
    return (
        'rate_limit' in el or
        'rate limit' in el or
        '429' in error_str or
        'quota' in el or
        'tokens per day' in el or
        'tokens per minute' in el or
        'resource_exhausted' in el or      # Gemini format
        'resourceexhausted' in el or       # Gemini gRPC format
        'exceeded your current quota' in el or  # OpenAI/Gemini format
        'request_rate_limit_reached' in el or   # Groq format
        'ratelimitreached' in el
    )


def _attempt_parse(current_llm, pydantic_class, messages, llm_label: str):
    """
    Try all 3 tiers against a specific LLM instance.
    Returns a valid pydantic_class instance or raises.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    # -- Tier 1: structured output --
    tier1_error = None
    estimated_tokens = _tpm_tracker.estimate(messages)
    _tpm_tracker.check_and_throttle(estimated_tokens, llm_label)
    try:
        structured_llm = current_llm.with_structured_output(pydantic_class)
        res = structured_llm.invoke(messages)
        if isinstance(res, pydantic_class):
            safe_print(f'[OK] Tier 1 ({llm_label}): {pydantic_class.__name__}')
            return res
        elif isinstance(res, dict):
            return pydantic_class(**_coerce_types(res, pydantic_class))
        elif isinstance(res, str):
            for candidate in _extract_json_from_text(res):
                try:
                    return _try_parse(candidate, pydantic_class)
                except Exception:
                    continue
            raise ValueError('Tier 1 returned unparseable string')
        else:
            raise ValueError(f'Tier 1 returned unexpected type: {type(res)}')
    except Exception as e:
        tier1_error = e
        safe_print(f'[WARN] Tier 1 failed ({llm_label}/{pydantic_class.__name__}): {str(e)[:150]}')
        if _is_rate_limit_error(str(e)):
            raise  # Propagate rate limit so caller can switch LLM

    # -- Tier 2: salvage JSON from error string --
    safe_print(f'[RETRY] Tier 2: scanning error string for JSON blobs...')
    error_str = str(tier1_error)

    func_matches = re.findall(
        r'<function=[^>]+>\s*(\{.*?\})\s*(?:</function>|$)',
        error_str,
        re.DOTALL
    )
    for match in reversed(func_matches):
        try:
            result = _try_parse(match, pydantic_class)
            safe_print(f'[OK] Tier 2 (function tag/{llm_label}): {pydantic_class.__name__}')
            return result
        except Exception:
            continue

    for candidate in _extract_json_from_text(error_str):
        try:
            result = _try_parse(candidate, pydantic_class)
            safe_print(f'[OK] Tier 2 (JSON blob/{llm_label}): {pydantic_class.__name__}')
            return result
        except Exception:
            continue

    # -- Tier 3: plain text retry with schema injected --
    safe_print(f'[RETRY] Tier 3: schema-injected plain text retry ({llm_label})...')
    try:
        schema_dict = pydantic_class.model_json_schema()

        schema_block = (
            '\n\n=== STRICT OUTPUT INSTRUCTION ===\n'
            'Your ENTIRE response must be a single raw JSON object.\n'
            'NO markdown code fences. NO explanation. NO <function> tags.\n'
            'Start your response with { and end with }.\n\n'
            f'Required schema for {pydantic_class.__name__}:\n'
            f'{json.dumps(schema_dict, indent=2)}\n\n'
            'Field type rules:\n'
            '- Integers: write 8 not "8"\n'
            '- Booleans: write true or false not "true" or "false"\n'
            '- Arrays: provide AT LEAST the minimum number of items\n'
            '- Strings: meet the min_length if specified\n'
            '- Literals: use ONLY one of the allowed enum values\n'
            '=== OUTPUT JSON NOW ==='
        )

        modified_messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                cleaned = re.sub(
                    r'\n*CRITICAL: You must respond ONLY with a single tool call.*?(?=\n\n|\Z)',
                    '',
                    msg.content,
                    flags=re.DOTALL
                ).strip()
                modified_messages.append(SystemMessage(content=cleaned))
            else:
                modified_messages.append(msg)

        if modified_messages and isinstance(modified_messages[-1], HumanMessage):
            modified_messages[-1] = HumanMessage(
                content=modified_messages[-1].content + schema_block
            )
        else:
            modified_messages.append(HumanMessage(content=schema_block))

        raw_response = current_llm.invoke(modified_messages).content.strip()
        raw_response = re.sub(r'^```(?:json)?\s*', '', raw_response)
        raw_response = re.sub(r'\s*```$', '', raw_response).strip()

        for candidate in _extract_json_from_text(raw_response):
            try:
                result = _try_parse(candidate, pydantic_class)
                safe_print(f'[OK] Tier 3 ({llm_label}): {pydantic_class.__name__}')
                return result
            except Exception:
                continue

    except Exception as e3:
        safe_print(f'[FAIL] Tier 3 ({llm_label}) failed: {e3}')
        if _is_rate_limit_error(str(e3)):
            raise

    raise ValueError(
        f'All 3 tiers exhausted for {pydantic_class.__name__} on {llm_label}.'
    )


def call_with_fallback(llm, pydantic_class, messages, max_retries_per_provider: int = 2):
    """
    State-of-the-art redundancy logic with exponential backoff.
    Attempts structured output through a chain of LLMs:
    1. Primary (from .env) — up to max_retries_per_provider retries with backoff
    2. Fallback secondary (e.g. Gemini if Primary was Groq)
    3. Final Fallback (Local Ollama)

    On rate-limit errors: waits then retries same provider before switching.
    On hard errors (schema mismatch, etc.): switches provider immediately.
    """
    providers = []

    # Provider 1: Primary
    providers.append((llm, 'primary'))

    # Provider 2: Secondary
    fb1 = get_fallback_llm()
    if fb1:
        providers.append((fb1, 'secondary-fallback'))

    # Provider 3: Always add Ollama if config exists and not already in chain
    ollama_model = os.getenv('OLLAMA_MODEL', '')
    if ollama_model and not any(
        getattr(p[0], '__class__', type).__name__ == 'ChatOllama' for p in providers
    ):
        try:
            from langchain_ollama import ChatOllama
            lo_llm = ChatOllama(
                model=ollama_model,
                base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
                temperature=0.3
            )
            providers.append((lo_llm, 'local-ollama'))
        except Exception:
            pass

    errors = []
    for current_llm, label in providers:
        # Retry within this provider for rate limits (exponential backoff)
        for attempt in range(1, max_retries_per_provider + 1):
            try:
                return _attempt_parse(current_llm, pydantic_class, messages, label)
            except Exception as e:
                err_msg = str(e)
                is_rate_limit = _is_rate_limit_error(err_msg)

                if is_rate_limit and attempt < max_retries_per_provider:
                    wait_secs = 2 ** attempt  # 2s, 4s
                    safe_print(
                        f"[RETRY] {label} rate-limited (attempt {attempt}/{max_retries_per_provider}). "
                        f"Waiting {wait_secs}s before retry..."
                    )
                    time.sleep(wait_secs)
                    continue  # retry same provider

                # Either not a rate limit, or final retry exhausted
                errors.append(f"{label}: {err_msg[:120]}")
                if is_rate_limit:
                    safe_print(f"[REDUNDANCY] {label} rate-limited. Moving to next provider...")
                    # Both Groq models share the same org TPM bucket.
                    # Sleep 15s before switching so the window can partially reset.
                    time.sleep(15)
                else:
                    safe_print(
                        f"[REDUNDANCY] {label} failed: {err_msg[:120]}. Moving to next provider..."
                    )
                break  # exit retry loop, try next provider

    raise ValueError(
        f"CRITICAL: All providers exhausted for {pydantic_class.__name__}.\n"
        f"Chain attempted: {', '.join([p[1] for p in providers])}\n"
        f"Errors: {'; '.join(errors)}"
    )


if __name__ == '__main__':
    info = get_llm_info()
    safe_print(f'Mode: {info["mode"]} | Model: {info["model_name"]}')
    llm = get_llm()
    from langchain_core.messages import HumanMessage
    r = llm.invoke([HumanMessage(content='Say hello in one sentence.')])
    safe_print(f'Test: {r.content}')
