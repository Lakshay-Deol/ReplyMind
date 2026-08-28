# CreatorMind Implementation Plan

## 1. Existing Architecture
The current application is a YouTube Comment Assistant with the following workflow:
**YouTube OAuth** → **CommentFetcher** → **Deduplication** → **Rule-based Triage** (`app/ai/triage_engine.py`) → **Batch Reply Drafting** (custom OpenAI client using `requests` in `app/ai/batch_drafter.py`) → **Runtime JSON Storage** (`runtime/drafts/`, `runtime/triage/`) → **FastAPI Review UI** (`app/review/webapp.py`) → **Human Approval** → **YouTube Publishing**.

## 2. New Architecture
The goal is to convert this into **CreatorMind — Persistent AI Community Manager**. The core workflow will remain, but the AI drafting layer will be replaced with an intelligent agent powered by the **Minds Builder API**. 
**New Agent Workflow:** CommentFetcher → Deduplication → **CreatorMind Agent** (which retrieves **Memory/Context** for the specific user) → **Context-Aware Reply Drafting** → Review UI (now displaying context) → Human Approval → Publish & Update Memory.

## 3. Discrepancies (README vs Code)
The README states the project is built with:
- **Guardrail**: This is entirely missing from the codebase and `requirements.txt`. Triage is currently handled via simple regex and string matching rules.
- **OpenAI**: The official `openai` SDK is missing from `requirements.txt`. Instead, a custom client using `requests` is implemented in `app/ai/openai_client.py`.

## 4. Files to Create
- `app/ai/creatormind_agent.py`: New client to interact with the Minds Builder API and manage agent state.
- `app/ai/memory_store.py`: Logic to persist and retrieve conversation history keyed by YouTube user ID/Channel ID.
- `runtime/memory/` (Directory): Local storage path for JSON-based conversation memory (or SQLite if upgraded).

## 5. Files to Modify
- `app/ai/batch_drafter.py`: Reroute drafting to use `creatormind_agent.py` instead of the raw `openai_client.py`.
- `main.py`: Initialize the `MemoryStore` and pass it to the drafting workflow.
- `app/review/webapp.py`: Update the FastAPI endpoints and HTML templates to display conversation history (Memory) and agent reasoning to the human reviewer.
- `app/review/models.py`: Add `context` and `memory` fields to the review data models.
- `requirements.txt`: Add required dependencies for the Minds Builder API or any missing packages.

## 6. Data Models Required
- **MemoryContext / Conversation**: Model to store past interactions (`user_id`, `past_comments`, `past_replies`, `timestamps`).
- **AgentConfig**: Configuration model containing `MINDS_BUILDER_API_KEY` and specific agent parameters.

## 7. Agent Responsibilities
- Retrieve past interactions with a user before drafting a reply.
- Analyze the user's sentiment and history.
- Generate highly contextual, personalized replies based on the creator's persona.
- Update the memory store once a reply is published.

## 8. Memory Design
- **Local Persistence**: Use JSON files inside `runtime/memory/` keyed by `author_channel_id` (e.g., `runtime/memory/{author_id}.json`).
- **Structure**: Each file contains an array of `Interaction` objects (Comment + Reply + Date). 
- **Retrieval**: The agent pulls the last N interactions for the author before generating the draft.

## 9. UI Changes
- Modify the review dashboard (http://127.0.0.1:8000) to include a **"Context / History"** panel next to the draft.
- Reviewers should see if this is a returning user and what was discussed previously to make an informed approval decision.

## 10. Testing Strategy
- **Unit Tests**: Test `memory_store.py` for correct read/write/append operations.
- **Integration Tests**: Mock the Minds Builder API to ensure the agent correctly incorporates memory context into prompts.
- **E2E Tests**: Simulate a returning user commenting twice to verify the UI displays the history during the second review.

## 11. Deployment Considerations
- **Environment Variables**: Add `MINDS_BUILDER_API_KEY` to `.env.example`.
- **State Persistence**: Ensure the `runtime/memory/` directory is mounted to a persistent volume (e.g., Render Disks) so community context isn't lost between deployments.
