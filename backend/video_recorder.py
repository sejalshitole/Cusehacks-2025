import os
import asyncio
import cv2
import numpy as np
from PIL import Image
import base64
from io import BytesIO
from datetime import datetime
from typing import List, Optional, Dict, Any
from supabase import create_client, Client
from dotenv import load_dotenv
import subprocess
import wave
from pathlib import Path

# Load environment variables
load_dotenv()

# Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase_bucket = os.getenv("SUPABASE_BUCKET_NAME", "videos")

supabase: Optional[Client] = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)


class VideoRecorder:
    """Handles video and audio recording from WebSocket frames"""
    
    def __init__(self, session_id: str, user_id: str = "anonymous", fps: int = 60):
        self.session_id = session_id
        self.user_id = user_id
        self.fps = fps
        self.frames: List[np.ndarray] = []
        self.audio_chunks: List[bytes] = []
        
        # Create user-specific directory structure
        self.user_session_dir = f"temp_videos/{user_id}/{session_id}"
        os.makedirs(self.user_session_dir, exist_ok=True)
        
        self.temp_video_path = f"{self.user_session_dir}/video.mp4"
        self.temp_audio_path = f"{self.user_session_dir}/audio.webm"
        self.temp_combined_video_path = f"{self.user_session_dir}/combined.webm"
        self.final_video_path = f"{self.user_session_dir}/final.mp4"
        self.has_combined_blob = False
        
        # Audio properties (will be set when first audio chunk arrives)
        self.audio_sample_rate = 48000  # Default for WebM
        self.audio_channels = 1  # Mono
    
    def add_frame(self, base64_frame: str):
        """Add a frame to the recording"""
        try:
            # Remove data URL prefix if present
            if "base64," in base64_frame:
                base64_frame = base64_frame.split("base64,")[1]
            
            # Decode base64 to image
            image_data = base64.b64decode(base64_frame)
            image = Image.open(BytesIO(image_data))
            
            # Convert PIL Image to OpenCV format (BGR)
            frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            self.frames.append(frame)
        except Exception as e:
            print(f"Error adding frame: {e}")
    
    def add_audio_chunk(self, base64_audio: str):
        """Add an audio chunk to the recording"""
        try:
            # Remove data URL prefix if present
            if "base64," in base64_audio:
                base64_audio = base64_audio.split("base64,")[1]
            
            # Decode base64 to audio data
            audio_data = base64.b64decode(base64_audio)
            self.audio_chunks.append(audio_data)
        except Exception as e:
            print(f"Error adding audio chunk: {e}")

    def set_final_webm_blob(self, base64_blob: str):
        """Store the complete WebM blob received at the end of the session"""
        try:
            if "base64," in base64_blob:
                base64_blob = base64_blob.split("base64,")[1]

            blob_data = base64.b64decode(base64_blob)
            with open(self.temp_combined_video_path, "wb") as f:
                f.write(blob_data)

            self.has_combined_blob = True
            print(f"Stored final WebM blob for session {self.session_id}")
        except Exception as e:
            print(f"Error storing WebM blob: {e}")
            self.has_combined_blob = False
    
    def save_video(self) -> Optional[str]:
        """Save recorded frames and audio as a video file"""
        if self.has_combined_blob:
            try:
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-y",
                    "-fflags",
                    "+genpts",
                    "-i",
                    self.temp_combined_video_path,
                    "-vsync",
                    "2",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-r",
                    str(self.fps),
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "160k",
                    "-ar",
                    str(self.audio_sample_rate),
                    "-ac",
                    str(self.audio_channels),
                    "-af",
                    "aresample=async=1:first_pts=0",
                    "-movflags",
                    "+faststart",
                    "-shortest",
                    self.final_video_path,
                ]

                subprocess.run(
                    ffmpeg_cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                print(f"Converted WebM blob to MP4: {self.final_video_path}")
                return self.final_video_path
            except subprocess.CalledProcessError as e:
                print(f"FFmpeg conversion error (primary pipeline): {e.stderr}")
                print("Attempting simplified fallback conversion…")

                fallback_cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    self.temp_combined_video_path,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    self.final_video_path,
                ]

                try:
                    subprocess.run(
                        fallback_cmd,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    print(
                        f"Fallback FFmpeg conversion succeeded: {self.final_video_path}"
                    )
                    return self.final_video_path
                except subprocess.CalledProcessError as fallback_error:
                    print(
                        f"Fallback FFmpeg conversion failed: {fallback_error.stderr}"
                    )
                    return None
            except FileNotFoundError:
                print("FFmpeg not found. Cannot convert WebM to MP4.")
                print("Install FFmpeg: brew install ffmpeg (on macOS)")
                return None
            except Exception as e:
                print(f"Error converting WebM blob: {e}")
                return None

        if not self.frames:
            print("No frames to save")
            return None
        
        try:
            # Save video frames
            height, width, _ = self.frames[0].shape
            
            # Use H.264 codec for better compatibility
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            video_writer = cv2.VideoWriter(
                self.temp_video_path,
                fourcc,
                self.fps,
                (width, height)
            )
            
            # Write all frames
            for frame in self.frames:
                video_writer.write(frame)
            
            video_writer.release()
            print(f"Video frames saved to {self.temp_video_path}")
            
            # If we have audio chunks, save them and combine with video
            if self.audio_chunks:
                # Save audio chunks to file
                with open(self.temp_audio_path, 'wb') as f:
                    for chunk in self.audio_chunks:
                        f.write(chunk)
                print(f"Audio saved to {self.temp_audio_path}")
                
                # Combine video and audio using FFmpeg
                try:
                    subprocess.run([
                        'ffmpeg',
                        '-i', self.temp_video_path,
                        '-i', self.temp_audio_path,
                        '-c:v', 'copy',
                        '-c:a', 'aac',
                        '-y',
                        self.final_video_path
                    ], check=True, capture_output=True, text=True)
                    print(f"Combined video with audio: {self.final_video_path}")
                    return self.final_video_path
                except subprocess.CalledProcessError as e:
                    print(f"FFmpeg error: {e.stderr}")
                    print("Returning video without audio")
                    return self.temp_video_path
                except FileNotFoundError:
                    print("FFmpeg not found. Returning video without audio.")
                    print("Install FFmpeg: brew install ffmpeg (on macOS)")
                    return self.temp_video_path
            else:
                # No audio, return video only
                return self.temp_video_path
                
        except Exception as e:
            print(f"Error saving video: {e}")
            return None
    
    def cleanup(self):
        """Clean up temporary files"""
        try:
            if os.path.exists(self.temp_video_path):
                os.remove(self.temp_video_path)
                print(f"Cleaned up {self.temp_video_path}")
            if os.path.exists(self.temp_audio_path):
                os.remove(self.temp_audio_path)
                print(f"Cleaned up {self.temp_audio_path}")
            if os.path.exists(self.temp_combined_video_path):
                os.remove(self.temp_combined_video_path)
                print(f"Cleaned up {self.temp_combined_video_path}")
            if os.path.exists(self.final_video_path):
                os.remove(self.final_video_path)
                print(f"Cleaned up {self.final_video_path}")
            
            # Remove the session directory if empty
            if os.path.exists(self.user_session_dir) and not os.listdir(self.user_session_dir):
                os.rmdir(self.user_session_dir)
                print(f"Cleaned up {self.user_session_dir}")
            
            # Remove user directory if empty
            user_dir = f"temp_videos/{self.user_id}"
            if os.path.exists(user_dir) and not os.listdir(user_dir):
                os.rmdir(user_dir)
                print(f"Cleaned up {user_dir}")
        except Exception as e:
            print(f"Error cleaning up: {e}")


async def upload_to_supabase(video_path: str, session_id: str, user_id: str = "anonymous") -> Optional[str]:
    """Upload video to Supabase storage with organized path structure"""
    if not supabase:
        print("Supabase client not initialized")
        return None
    
    try:
        # Determine extension/content type based on saved file
        file_path = Path(video_path)
        extension = file_path.suffix.lower()

        if extension != ".mp4":
            print(
                f"Upload aborted: expected MP4 file but received '{extension or 'unknown'}'"
            )
            return None

        content_type = "video/mp4"

        # Organize in Supabase storage as: user_id/session_id.mp4
        storage_path = f"{user_id}/{session_id}.mp4"
        
        # Read video file
        with open(video_path, "rb") as f:
            video_data = f.read()

        if not video_data:
            print("Supabase upload aborted: video file is empty")
            return None

        file_size = len(video_data)

        print(
            f"Uploading {storage_path} to Supabase (size={file_size} bytes, content_type={content_type})"
        )
        
        # Upload to Supabase storage
        file_options = {
            "content-type": content_type,
            # Supabase Python client expects header values to be strings
            "upsert": "true"
        }

        response = supabase.storage.from_(supabase_bucket).upload(
            storage_path,
            video_data,
            file_options=file_options
        )
        print(f"Supabase upload response: {response}")
        
        # Get public URL
        public_url = supabase.storage.from_(supabase_bucket).get_public_url(storage_path)
        
        print(f"Video uploaded to Supabase: {public_url}")
        return public_url
    except Exception as e:
        print(f"Error uploading to Supabase: {e}")
        return None


async def get_user_videos(user_id: str) -> Optional[List[dict]]:
    """Retrieve all videos for a specific user from Supabase storage"""
    if not supabase:
        print("Supabase client not initialized")
        return None
    
    try:
        # List all files in the user's folder
        response = (
            supabase.storage
            .from_("videos")
            .list(
                path=f"{user_id}/",

            )
        )
        print(f"Supabase list response: {response}")
        print(f"Length of response: {len(response) if response else 0}")
        
        if not response:
            print(f"No videos found for user {user_id}")
            return []
        
        videos = []
        for file in response:
            # Skip folders and files without metadata (folders don't have .mp4 extension)
            if not file.get('name', '').endswith('.mp4'):
                print(f"Skipping non-video file/folder: {file.get('name')}")
                continue
                
            # Skip if no metadata (folders don't have metadata)
            if not file.get('metadata'):
                print(f"Skipping item without metadata: {file.get('name')}")
                continue
            
            # Each file represents a session
            file_path = f"{user_id}/{file['name']}"
            
            # Get public URL
            public_url = supabase.storage.from_(supabase_bucket).get_public_url(file_path)
            
            # Extract session_id from filename (remove .mp4 extension)
            session_id = file['name'].replace('.mp4', '')
            
            video_info = {
                "session_id": session_id,
                "url": public_url,
                "created_at": file.get('created_at', ''),
                "updated_at": file.get('updated_at', ''),
                "size": file.get('metadata', {}).get('size', 0),
                "name": file['name']
            }
            videos.append(video_info)
        
        # Sort by created date (newest first)
        videos.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        print(f"Found {len(videos)} videos for user {user_id}")
        return videos
    except Exception as e:
        print(f"Error retrieving videos for user {user_id}: {e}")
        return None


async def save_feedback_segments_to_supabase(
    session_id: str,
    user_id: str,
    segments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Persist AI feedback segments to Supabase database.

    Args:
        session_id: Unique session identifier
        user_id: Authenticated user identifier
        segments: List of segment dictionaries containing feedback_text and timing

    Returns:
        Dictionary with success flag, count saved, and optional error message
    """

    if not segments:
        return {"success": True, "count": 0}

    if not supabase:
        error_msg = "Supabase client not initialized"
        print(error_msg)
        return {"success": False, "count": 0, "error": error_msg}

    rows = []
    for segment in segments:
        feedback_text = segment.get("feedback_text")
        if not feedback_text:
            continue

        rows.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "feedback_text": feedback_text,
                "start_seconds": round(float(segment.get("start_seconds", 0.0)), 2),
                "end_seconds": round(float(segment.get("end_seconds", 0.0)), 2),
            }
        )

    if not rows:
        return {"success": True, "count": 0}

    def insert_rows():
        try:
            response = supabase.table("ai_feedback_segments").insert(rows).execute()
            data = getattr(response, "data", None)
            saved_count = len(data) if data else len(rows)
            return {"success": True, "count": saved_count, "data": data}
        except Exception as exc:
            error_text = str(exc)
            print(f"Error saving feedback segments: {error_text}")
            return {"success": False, "count": 0, "error": error_text}

    return await asyncio.to_thread(insert_rows)