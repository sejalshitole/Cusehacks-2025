import os
import time
import mimetypes
from typing import Optional, Dict, Any

import google.generativeai as genai
from supabase import create_client


DEFAULT_MODEL = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")  # override via env if you like


DEFAULT_PROMPT = """
You are a public speaking content feedback assistant.

Task:
Analyze the entire uploaded speech video and provide constructive, content-focused feedback in Markdown format. Your goal is to help the speaker improve the quality, clarity, and impact of their spoken content — not to describe visuals or actions.

Summary

Summarize the main topic and message of the speech in 3–5 sentences. Identify the intended purpose or audience (e.g., persuasive, informative, motivational).

Content Evaluation

Assess the speech content in detail:

Clarity and focus of the main idea

Logical flow and organization of points

Strength of arguments or supporting evidence

Relevance and depth of examples or stories

Accuracy and credibility of facts or claims

Engagement & Delivery Style

Provide feedback on how engaging and relatable the content is:

Emotional connection, storytelling, or use of rhetorical devices

Audience awareness (does the content address listener needs or expectations?)

Pacing, transitions, and balance between detail and brevity

Language & Word Choice

Evaluate the use of language:

Word clarity and vocabulary level (simple vs. complex)

Persuasiveness, tone consistency, and professional appropriateness

Overuse of filler words, clichés, or jargon

Topic Depth & Originality

Comment on:

How well the topic demonstrates critical thinking or unique perspective

Whether it offers new insights or ideas instead of common knowledge

Areas where more depth, data, or structure would strengthen the content

Recommendations

Actionable steps to improve the speech content:

How to refine the structure, argument strength, or clarity

How to make the message more impactful or memorable

Suggested improvements in tone, examples, or phrasing
"""


class VideoAnalyzer:
    """
    Uploads a video to Gemini, gets a detailed Markdown report, and saves it to Supabase.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
    ):
        print("[VideoAnalyzer] Initializing VideoAnalyzer...")
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required.")
        print("[VideoAnalyzer] Gemini API key present (not printed for security).")

        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_KEY")
        if not (self.supabase_url and self.supabase_key):
            raise ValueError("SUPABASE_URL and SUPABASE_KEY (or service role key) are required.")
        print(f"[VideoAnalyzer] Supabase URL set: {self.supabase_url} (key not printed)")

        # Configure clients
        print(f"[VideoAnalyzer] Configuring Genie/Gemini client for model {model_name}...")
        genai.configure(api_key=self.gemini_api_key)
        self.model_name = model_name
        self.sb = create_client(self.supabase_url, self.supabase_key)
        print("[VideoAnalyzer] Supabase client created.")

        # Create model instance once
        self.model = genai.GenerativeModel(self.model_name)
        print(f"[VideoAnalyzer] GenerativeModel instance created for: {self.model_name}")

    # ---------- GEMINI ----------
    def _upload_video(self, file_path: str):
        """
        Upload the local video file to Gemini. Returns a File object with .name (id) and .uri.
        """
        print(f"[VideoAnalyzer] _upload_video called with path: {file_path}")
        if not os.path.isfile(file_path):
            print(f"[VideoAnalyzer] File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        guessed_type, _ = mimetypes.guess_type(file_path)
        print(f"[VideoAnalyzer] Guessed MIME type: {guessed_type}")

        # Gemini can infer type, but passing a hint is helpful when known
        print(f"[VideoAnalyzer] Uploading file to Gemini: {file_path} ...")
        file_obj = genai.upload_file(path=file_path, mime_type=guessed_type or None)
        print(f"[VideoAnalyzer] Upload initiated. File object: {getattr(file_obj, 'name', None)}")

        # Wait until the file is ready (Gemini processes uploads asynchronously)
        while True:
            file_obj = genai.get_file(file_obj.name)
            state_name = getattr(file_obj.state, "name", None)
            print(f"[VideoAnalyzer] Polling upload state: {state_name}")
            if state_name == "ACTIVE":
                print(f"[VideoAnalyzer] Upload ACTIVE for file: {file_path}")
                break
            if state_name == "FAILED":
                print(f"[VideoAnalyzer] Upload FAILED for file: {file_path} - state: {file_obj.state}")
                raise RuntimeError(f"Gemini upload failed for {file_path}: {file_obj.state}")
            time.sleep(1.0)

        print(f"[VideoAnalyzer] Returning uploaded file object: {getattr(file_obj, 'name', None)}")
        return file_obj

    def _request_report(self, gemini_file, prompt: str = DEFAULT_PROMPT, request_timeout: int = 600) -> str:
        """
        Ask Gemini to analyze the uploaded video and return Markdown text.
        """
        print(f"[VideoAnalyzer] _request_report called for file: {getattr(gemini_file, 'name', None)}")
        print(f"[VideoAnalyzer] Prompt length: {len(prompt)} characters")
        # The content is a list of "parts": the uploaded file object + a text prompt.
        print("[VideoAnalyzer] Sending generate_content request to Gemini...")
        response = self.model.generate_content(
            [gemini_file, {"text": prompt}],
            request_options={"timeout": request_timeout},
        )
        print("[VideoAnalyzer] Received response from Gemini SDK.")

        # The SDK exposes .text for simple text responses:
        report_md = getattr(response, "text", None)
        if report_md:
            print(f"[VideoAnalyzer] Report text received directly from response (length {len(report_md)}).")
        else:
            print("[VideoAnalyzer] No direct .text on response, checking candidates fallback...")
            # Fall back to first candidate if needed
            if getattr(response, "candidates", None) and getattr(response.candidates[0].content, "parts", None):
                parts = response.candidates[0].content.parts
                assembled = "".join(p.text or "" for p in parts)
                report_md = assembled
                print(f"[VideoAnalyzer] Assembled report from candidates (length {len(report_md)}).")
        if not report_md:
            print(f"[VideoAnalyzer] Gemini did not return text content. Full response: {response}")
            raise RuntimeError("Gemini did not return text content.")
        print("[VideoAnalyzer] Returning Markdown report.")
        return report_md

    # ---------- SUPABASE ----------
    def _save_report_row(
        self,
        table: str,
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Inserts a single row into Supabase. Returns the inserted record.
        """
        print(f"[VideoAnalyzer] _save_report_row called. Table: {table}")
        print(f"[VideoAnalyzer] Row to insert (truncated): {{'filename': {row.get('filename')}, 'status': {row.get('status')}}} ...")
        result = self.sb.table(table).insert(row).execute()
        print(f"[VideoAnalyzer] Supabase insert result: {result}")
        if not result.data:
            print(f"[VideoAnalyzer] Insert returned no data. Full response: {result}")
            raise RuntimeError(f"Insert returned no data. Response: {result}")
        print(f"[VideoAnalyzer] Inserted record ID or row: {result.data[0]}")
        return result.data[0]

    # ---------- PUBLIC API ----------
    def analyze(
        self,
        file_path: str,
        *,
        prompt: str = DEFAULT_PROMPT,
        supabase_table: str = "video_reports",
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrates: upload video -> ask Gemini -> save to Supabase.
        Returns the inserted Supabase row.
        """
        print(f"[VideoAnalyzer] analyze() start for file: {file_path}")
        # 1) Upload video to Gemini
        gemini_file = self._upload_video(file_path)
        print(f"[VideoAnalyzer] Uploaded to Gemini: {getattr(gemini_file, 'name', None)}")

        # 2) Ask for a detailed Markdown report
        report_md = self._request_report(gemini_file, prompt=prompt)
        print(f"[VideoAnalyzer] Received report (length {len(report_md)}).")

        # 3) Save in Supabase
        filename = os.path.basename(file_path)
        file_bytes = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        print(f"[VideoAnalyzer] Preparing to save report. filename={filename}, size={file_bytes}, mime_type={mime_type}")

        row = {
            "filename": filename,
            "gemini_file_id": getattr(gemini_file, "name", None) or getattr(gemini_file, "uri", None),
            "report_md": report_md,
            "status": "completed",
            **(extra_metadata or {}),
        }

        print(f"[VideoAnalyzer] Inserting row into Supabase table '{supabase_table}'...")
        inserted = self._save_report_row(supabase_table, row)
        print(f"[VideoAnalyzer] analyze() completed. Inserted row: {inserted}")
        return inserted
