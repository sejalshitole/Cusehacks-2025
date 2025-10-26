"""
Feedback Agent - AI-powered public speaking coach
Uses Gemini API to analyze speaker's performance in real-time
"""

import os
import tempfile
import base64
from typing import List, Optional
from PIL import Image
import io

from .feedback_utils import analyze_audio_tone_fast, compress_images_for_gemini

try:
    from google import genai
    from google.genai import types  # google-genai package
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False
    print("Warning: google-genai not installed. AI feedback will be disabled.")


SYSTEM_PROMPT = """You are an expert AI public speaking coach observing a live on-stage presentation. 
The speaker is addressing a large audience in front of them (not the camera). 
Your role is to analyze the speaker’s physical delivery and vocal performance in a real auditorium context.

Focus your feedback on:
- **Body posture:** stance, balance, openness, and authority.
- **Gestures:** naturalness, emphasis, timing, and energy.
- **Eye direction:** whether they connect with the live audience effectively.
- **Vocal delivery:** tone, volume, pitch, pace, clarity, emotion, and projection.

Do NOT comment on camera eye contact or framing — the audience is in front of the speaker, not the camera.

Provide **only corrective feedback** when improvement is needed.
If performance is solid and no correction is needed, reply only with: `OK`.

When giving feedback:
- Be **concise (1 sentence)** and **actionable** (tell the speaker exactly what to adjust).
- Avoid generic praise or soft language.
- Reference prior feedback if relevant to maintain consistency over time (e.g., “still too fast,” “same slouch as before”).
- Use clear, behavior-based language (e.g., “slow down your pace by 20%” instead of “speak slower”).

Your goal: help the speaker appear confident, engaging, and commanding on stage through precise, professional feedback.
"""


class FeedbackAgent:
    """
    AI Feedback Agent for real-time public speaking coaching
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the feedback agent
        
        Args:
            api_key: Google Gemini API key (will use env var if not provided)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.chat_history: List[str] = []
        self.client = None
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

        if GENAI_AVAILABLE and types and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as exc:  # pylint: disable=broad-except
                self.client = None
                print(f"Failed to initialize Gemini client: {exc}")
        else:
            print("Warning: Gemini AI not configured. Feedback will be placeholder.")
    
    def analyze_segment(
        self, 
        frames: List[str], 
        audio_data: Optional[str] = None
    ) -> str:
        """
        Analyze a segment of the presentation (frames + audio)
        
        Args:
            frames: List of base64 encoded image frames
            audio_data: Optional base64 encoded audio data
        
        Returns:
            Feedback string
        """
        if not self.client or not types:
            return "AI feedback unavailable (API not configured)"
        
        try:
            # Convert base64 frames to PIL Images
            images = []
            for idx, frame_b64 in enumerate(frames):
                try:
                    # Clean up base64 data
                    if "base64," in frame_b64:
                        frame_b64 = frame_b64.split("base64,")[1]
                    
                    # Decode base64 to bytes
                    img_bytes = base64.b64decode(frame_b64)
                    
                    # Verify it's actually image data
                    if len(img_bytes) < 100:
                        print(f"Warning: Frame {idx} has suspicious size ({len(img_bytes)} bytes), skipping")
                        continue
                    
                    # Try to open as image
                    img = Image.open(io.BytesIO(img_bytes))
                    
                    # Verify image was loaded properly
                    img.verify()
                    
                    # Re-open since verify() closes the file
                    img = Image.open(io.BytesIO(img_bytes))
                    
                    images.append(img)
                    print(f"Successfully loaded frame {idx}: {img.size} {img.mode}")
                    
                except Exception as e:
                    print(f"Error processing frame {idx}: {str(e)}")
                    continue
            
            if not images:
                return "Error: No valid image frames received for analysis"
            
            print(f"Successfully loaded {len(images)} frames for analysis.")
            
            # Compress images for Gemini
            images = compress_images_for_gemini(images, max_images=4, target_size=(640, 480))
            
            # Analyze audio if provided
            tone_report = "No audio data"
            if audio_data:
                try:
                    # Save audio to temp file for analysis
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as audio_file:
                        if "base64," in audio_data:
                            audio_data = audio_data.split("base64,")[1]
                        
                        audio_bytes = base64.b64decode(audio_data)
                        audio_file.write(audio_bytes)
                        audio_fp = audio_file.name
                    
                    tone_report = analyze_audio_tone_fast(audio_fp)
                    
                    # Cleanup temp file
                    os.unlink(audio_fp)
                except Exception as e:
                    tone_report = f"Audio analysis failed: {str(e)[:50]}"
            
            # Build prompt including system guidance and context
            prompt = SYSTEM_PROMPT
            if self.chat_history:
                prompt += "\n\nPrevious feedbacks:\n" + "\n".join(self.chat_history[-3:])  # Only last 3 for context
            prompt += f"\n\nSpeaker voice/tone: {tone_report}"
            
            # Get feedback from Gemini
            parts = [{"text": prompt}]
            for img in images:
                buffered = io.BytesIO()
                # Default to JPEG to keep size manageable
                img_format = (img.format or "JPEG").upper()
                mime_type = "image/jpeg" if img_format == "JPEG" else f"image/{img_format.lower()}"
                try:
                    img.save(buffered, format=img_format)
                except ValueError:
                    # Fallback to JPEG if the specific format isn't supported for saving
                    buffered = io.BytesIO()
                    img.save(buffered, format="JPEG")
                    mime_type = "image/jpeg"

                image_bytes = buffered.getvalue()
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_b64,
                    }
                })

            contents = [{"role": "user", "parts": parts}]

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
            )
            feedback = response.candidates[0].content.parts[0].text.strip()
            
            # Store non-OK feedback in history
            if feedback and feedback != "OK":
                self.chat_history.append(feedback)
            
            return feedback
            
        except Exception as e:
            error_msg = f"Error analyzing segment: {str(e)}"
            print(error_msg)
            return error_msg
    
    def reset_history(self):
        """Reset the chat history for a new session"""
        self.chat_history.clear()
    
    def get_history(self) -> List[str]:
        """Get the feedback history"""
        return self.chat_history.copy()