import httpx
from .config import settings

CHAT_PATH = "/chat/completions"

SYSTEM_FIRST_ACTION = """You are an ADHD-aware focus coach. The user names a task that feels hard to start.
Your job: return a single concrete, ≤5-minute physical first action — not a plan, not advice, not a pep talk.
The action must be doable right now at a desk and must reduce the activation energy of the larger task.
Output ONLY the action, one sentence, no markdown, no preamble."""

SYSTEM_OUTLINE = """You convert a rambling spoken transcript into a clean, structured outline that helps the speaker
overcome activation-energy and start the actual work elsewhere.

Rules:
- Output Markdown with headers and short bullets.
- Preserve the speaker's actual ideas; do not invent content not present in the transcript.
- Drop filler ("um", "you know", "like", repetition).
- Group related thoughts. Surface the implicit structure.
- If the speaker mentions specific names, places, numbers, or identifiers that look like case data,
  REPLACE them with abstract placeholders ([SUBJECT], [LOCATION], [DATE], [CASE_REF]).
- Begin with a 1-sentence summary, then the outline.
- Do not add a conclusion or commentary."""


async def _chat(messages: list[dict], max_tokens: int = 200, temperature: float = 0.4) -> str:
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
        r = await client.post(
            f"{settings.LLM_BASE_URL}{CHAT_PATH}",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.LLM_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()


async def first_action(task_title: str, notes: str | None = None) -> str:
    return await _chat(
        [
            {"role": "system", "content": SYSTEM_FIRST_ACTION},
            {"role": "user", "content": f"Task: {task_title}\nNotes: {notes or '(none)'}"},
        ],
        max_tokens=80,
        temperature=0.4,
    )


async def outline_from_transcript(
    transcript: str,
    task_title: str | None = None,
    task_notes: str | None = None,
) -> str:
    user_content = transcript
    if task_title:
        user_content = (
            f"[Context: the speaker is preparing to work on the task: \"{task_title}\""
            + (f". Existing notes: {task_notes}" if task_notes else "")
            + "]\n\n"
            + transcript
        )
    return await _chat(
        [
            {"role": "system", "content": SYSTEM_OUTLINE},
            {"role": "user", "content": user_content},
        ],
        max_tokens=900,
        temperature=0.3,
    )
