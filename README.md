
# SpeakFlow (Speak Up prototype)

SpeakFlow is an AI-powered public speaking coach that gives real-time, actionable feedback on delivery, voice, and body language so you can practice and improve faster.

## Inspiration

Public speaking is a common anxiety and professional hurdle. Coaching is effective but expensive and time-consuming. We built SpeakFlow to democratize coaching by using AI to provide objective, instant feedback anyone can access from a browser.

## What it does

- Captures webcam video and microphone audio while you practice.
- Streams frames and audio to a FastAPI backend for low-latency, real-time AI feedback.
- Highlights actionable moments (e.g., pacing, volume, posture) and stores feedback segments.
- Saves recordings to Supabase Storage and metadata/feedback to Supabase database.
- Lets users organize practice sessions by topics and review detailed reports.

## How we built it

- Frontend: Next.js (TypeScript), Tailwind CSS, and shadcn/ui components for an accessible UI.
- Backend: FastAPI with a WebSocket endpoint that receives frames/audio and coordinates analysis.
- Real-time AI: Custom `FeedbackAgent` integrates LLM-based analysis and heuristics for audiovisual signals.
- Audio analysis: Librosa-based utilities analyze tone, energy, and pace.
- Video handling: Frame capture and chunked uploads are combined server-side into MP4/WebM assets.
- Persistence: Supabase for authentication, Postgres tables, and cloud storage for videos.

## Challenges we ran into

- Achieving low-latency AI feedback while keeping compute costs reasonable.
- Synchronizing audio and video streams and handling large uploads robustly.
- Building a UX that communicates confidence without overwhelming users with raw AI output.
- Managing concurrent WebSocket sessions and cleaning up temporary files reliably.

## Accomplishments that we're proud of

- A working end-to-end prototype that streams webcam data and returns live, contextual feedback.
- Seamless integration between a Next.js frontend and FastAPI backend over WebSocket.
- Accurate, fast audio analysis using Librosa and a modular feedback agent for LLM augmentation.
- Topic-based organization and persistent storage of videos and feedback for review.

## What we learned

- Practical patterns for real-time WebSocket communication in Python and TypeScript.
- Trade-offs between on-device and server-side processing for video and audio.
- How to structure AI feedback to be concise, actionable, and timed to video segments.
- Supabase workflows for auth, storage, and row-level policies.

## Quickstart — development

Prerequisites: Python 3.10+, Node 18+, Supabase project (or local dev), and an AI API key if you plan to enable generative feedback.

1) Backend

```bash
# from repo root
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Set environment variables (examples)
export SUPABASE_URL="https://your-supabase-url"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
export Gemini_API_KEY="your-ai-api-key"
# Run backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2) Frontend

```bash
cd frontend
npm install
# Provide Supabase keys to .env.local or your environment
# Example env variables for Next.js (see frontend/README if present):
# NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
npm run dev
# Frontend runs on http://localhost:3000 and expects backend at http://localhost:8000
```

3) Database / Storage

- Apply the SQL schema in `backend/supabase_schema.sql` to your Supabase project to create `topics`, `video_sessions`, and other required tables.

## Where to record

- Once both servers are running and you are authenticated, open the app and navigate to the protected Record page (e.g., `/protected/record`) to start a practice session.

## Troubleshooting

- If topics or videos don't appear, ensure the backend is reachable at port 8000 and your Supabase keys are correct.
- Check browser console for WebSocket errors; the backend logs helpful messages for connections and file handling.

## Contributing

We welcome contributions. Please open an issue first to discuss significant changes. For small fixes, submit a pull request with tests where applicable.

## Credits

- Built with Next.js, FastAPI, Supabase, Librosa, and modern LLM tools.

## License

This project is offered under the MIT License. See the `LICENSE` file for details.

