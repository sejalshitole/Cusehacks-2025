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
                return os.path.abspath(self.final_video_path)
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
                    return os.path.abspath(self.final_video_path)
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
                    return os.path.abspath(self.final_video_path)
                except subprocess.CalledProcessError as e:
                    print(f"FFmpeg error: {e.stderr}")
                    print("Returning video without audio")
                    return os.path.abspath(self.temp_video_path)
                except FileNotFoundError:
                    print("FFmpeg not found. Returning video without audio.")
                    print("Install FFmpeg: brew install ffmpeg (on macOS)")
                    return os.path.abspath(self.temp_video_path)
            else:
                # No audio, return video only
                return os.path.abspath(self.temp_video_path)
                
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
    """Retrieve all videos for a specific user from Supabase storage and database"""
    if not supabase:
        print("Supabase client not initialized")
        return None

    def fetch_videos():
        try:
            # First, try to get videos from video_sessions table (with topic info)
            try:
                db_response = supabase.table("video_sessions")\
                    .select("*, topics(id, name, description)")\
                    .eq("user_id", user_id)\
                    .order("created_at", desc=True)\
                    .execute()

                if db_response.data:
                    print(f"Found {len(db_response.data)} videos in database")
                    return db_response.data
            except Exception as db_error:
                print(f"Database query failed, falling back to storage listing: {db_error}")

            # Fallback: List files from storage (for videos not yet in database)
            response = supabase.storage.from_("videos").list(path=f"{user_id}/")
            print(f"Supabase storage list response: {response}")
            print(f"Length of response: {len(response) if response else 0}")

            if not response:
                print(f"No videos found for user {user_id}")
                return []

            videos = []
            for file in response:
                # Skip folders and files without metadata
                if not file.get('name', '').endswith('.mp4'):
                    print(f"Skipping non-video file/folder: {file.get('name')}")
                    continue

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
                    "video_url": public_url,
                    "url": public_url,  # Keep for backward compatibility
                    "created_at": file.get('created_at', ''),
                    "updated_at": file.get('updated_at', ''),
                    "size_bytes": file.get('metadata', {}).get('size', 0),
                    "size": file.get('metadata', {}).get('size', 0),  # Keep for backward compatibility
                    "filename": file['name'],
                    "name": file['name'],  # Keep for backward compatibility
                    "topics": None  # No topic info from storage
                }
                videos.append(video_info)

            # Sort by created date (newest first)
            videos.sort(key=lambda x: x.get('created_at', ''), reverse=True)

            print(f"Found {len(videos)} videos for user {user_id}")
            return videos
        except Exception as e:
            print(f"Error retrieving videos for user {user_id}: {e}")
            import traceback
            traceback.print_exc()
            return []

    try:
        return await asyncio.to_thread(fetch_videos)
    except Exception as e:
        print(f"Error in get_user_videos: {e}")
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


async def rename_video(user_id: str, old_filename: str, new_filename: str) -> Dict[str, Any]:
    """
    Rename a video file in Supabase storage.

    Args:
        user_id: The user who owns the video
        old_filename: Current filename (e.g., "session_id.mp4")
        new_filename: New filename (should end with .mp4)

    Returns:
        Dictionary with success flag and message
    """
    if not supabase:
        return {"success": False, "message": "Supabase client not initialized"}

    # Ensure new filename has .mp4 extension
    if not new_filename.endswith('.mp4'):
        new_filename = f"{new_filename}.mp4"

    old_path = f"{user_id}/{old_filename}"
    new_path = f"{user_id}/{new_filename}"

    def rename_operations():
        try:
            # Download the file
            print(f"Downloading file from: {old_path}")
            file_data = supabase.storage.from_(supabase_bucket).download(old_path)

            if not file_data:
                return {"success": False, "message": "Video file not found"}

            # Upload with new name
            print(f"Uploading file to: {new_path}")
            upload_response = supabase.storage.from_(supabase_bucket).upload(
                new_path,
                file_data,
                {"content-type": "video/mp4"}
            )
            print(f"Upload response: {upload_response}")

            # Delete old file
            print(f"Deleting old file: {old_path}")
            supabase.storage.from_(supabase_bucket).remove([old_path])

            # Get public URL of renamed file
            public_url = supabase.storage.from_(supabase_bucket).get_public_url(new_path)

            return {
                "success": True,
                "message": "Video renamed successfully",
                "new_filename": new_filename,
                "url": public_url
            }
        except Exception as e:
            print(f"Error renaming video: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    return await asyncio.to_thread(rename_operations)


async def delete_video(user_id: str, filename: str) -> Dict[str, Any]:
    """
    Delete a video file from Supabase storage.

    Args:
        user_id: The user who owns the video
        filename: Filename to delete (e.g., "session_id.mp4")

    Returns:
        Dictionary with success flag and message
    """
    if not supabase:
        return {"success": False, "message": "Supabase client not initialized"}

    file_path = f"{user_id}/{filename}"

    def delete_operations():
        try:
            # First, verify the file exists
            print(f"Attempting to delete file: {file_path}")
            print(f"Bucket: {supabase_bucket}, User ID: {user_id}, Filename: {filename}")

            # Try to list the file first to verify it exists and get its details
            file_to_delete = None
            try:
                list_response = supabase.storage.from_(supabase_bucket).list(path=f"{user_id}/")
                print(f"Files in user directory before delete: {list_response}")

                # Find the specific file
                file_to_delete = next((f for f in list_response if f.get('name') == filename), None)
                if not file_to_delete:
                    error_msg = f"File '{filename}' not found in user directory"
                    print(f"ERROR: {error_msg}")
                    return {"success": False, "message": error_msg}

                print(f"Found file to delete: {file_to_delete}")
            except Exception as list_error:
                error_msg = f"Could not list files: {list_error}"
                print(f"ERROR: {error_msg}")
                return {"success": False, "message": error_msg}

            # Try multiple deletion approaches
            deletion_successful = False

            # Approach 1: Use the standard remove() method
            print(f"Attempting deletion with remove(['{file_path}'])")
            try:
                delete_response = supabase.storage.from_(supabase_bucket).remove([file_path])
                print(f"Delete response type: {type(delete_response)}")
                print(f"Delete response: {delete_response}")

                # Check if we got a successful response
                if isinstance(delete_response, list) and len(delete_response) > 0:
                    deletion_successful = True
                    print(f"SUCCESS: Standard remove() method worked")
            except Exception as del_ex:
                print(f"Standard remove() failed: {str(del_ex)}")
                # Continue to try other methods

            # If standard method failed, the issue is permissions
            if not deletion_successful:
                error_msg = (
                    "Unable to delete file - This is likely a Supabase Storage permissions issue. "
                    "Please check your Supabase Storage bucket policies. "
                    "You need to add a DELETE policy for the 'videos' bucket. "
                    "Go to: Supabase Dashboard → Storage → videos bucket → Policies → New Policy → "
                    "Allow DELETE for authenticated users where (bucket_id = 'videos')"
                )
                print(f"ERROR: {error_msg}")
                return {"success": False, "message": error_msg}

            # Also delete associated feedback segments if session_id matches
            session_id = filename.replace('.mp4', '')
            try:
                feedback_response = supabase.table("ai_feedback_segments")\
                    .delete()\
                    .eq("session_id", session_id)\
                    .eq("user_id", user_id)\
                    .execute()
                print(f"Deleted feedback segments for session {session_id}: {feedback_response}")
            except Exception as fb_error:
                print(f"Warning: Could not delete feedback segments: {fb_error}")
                # Continue even if feedback deletion fails

            return {
                "success": True,
                "message": "Video deleted successfully"
            }
        except Exception as e:
            error_message = str(e)
            print(f"Error deleting video: {error_message}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": error_message}

    return await asyncio.to_thread(delete_operations)


async def get_user_topics(user_id: str) -> Dict[str, Any]:
    """
    Get all topics for a specific user.

    Args:
        user_id: The user ID

    Returns:
        Dictionary with success flag and topics list
    """
    if not supabase:
        return {"success": False, "message": "Supabase client not initialized", "topics": []}

    def fetch_topics():
        try:
            response = supabase.table("topics")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=False)\
                .execute()

            topics = response.data if response.data else []

            # Ensure "General" topic exists
            if not any(t.get('name') == 'General' for t in topics):
                # Create default General topic
                general_topic = supabase.table("topics").insert({
                    "user_id": user_id,
                    "name": "General",
                    "description": "Default topic for uncategorized recordings"
                }).execute()

                if general_topic.data:
                    topics.insert(0, general_topic.data[0])

            return {"success": True, "topics": topics}
        except Exception as e:
            print(f"Error fetching topics: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e), "topics": []}

    return await asyncio.to_thread(fetch_topics)


async def create_topic(user_id: str, name: str, description: str = "") -> Dict[str, Any]:
    """
    Create a new topic for a user.

    Args:
        user_id: The user ID
        name: Topic name
        description: Optional topic description

    Returns:
        Dictionary with success flag and topic data
    """
    if not supabase:
        return {"success": False, "message": "Supabase client not initialized"}

    def insert_topic():
        try:
            response = supabase.table("topics").insert({
                "user_id": user_id,
                "name": name,
                "description": description
            }).execute()

            if response.data:
                return {"success": True, "topic": response.data[0]}
            else:
                return {"success": False, "message": "Failed to create topic"}
        except Exception as e:
            error_msg = str(e)
            print(f"Error creating topic: {error_msg}")
            import traceback
            traceback.print_exc()

            # Check for unique constraint violation
            if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
                return {"success": False, "message": "A topic with this name already exists"}

            return {"success": False, "message": error_msg}

    return await asyncio.to_thread(insert_topic)


async def save_video_session(
    session_id: str,
    user_id: str,
    topic_id: str,
    video_url: str,
    filename: str,
    duration_seconds: float = None,
    size_bytes: int = None
) -> Dict[str, Any]:
    """
    Save video session metadata to database.

    Args:
        session_id: Unique session identifier
        user_id: User ID
        topic_id: Topic ID to link the video to
        video_url: Public URL of the video
        filename: Video filename
        duration_seconds: Optional video duration
        size_bytes: Optional file size

    Returns:
        Dictionary with success flag
    """
    if not supabase:
        return {"success": False, "message": "Supabase client not initialized"}

    def insert_session():
        try:
            response = supabase.table("video_sessions").insert({
                "session_id": session_id,
                "user_id": user_id,
                "topic_id": topic_id if topic_id else None,
                "video_url": video_url,
                "filename": filename,
                "duration_seconds": duration_seconds,
                "size_bytes": size_bytes
            }).execute()

            if response.data:
                return {"success": True, "video_session": response.data[0]}
            else:
                return {"success": False, "message": "Failed to save video session"}
        except Exception as e:
            error_msg = str(e)
            print(f"Error saving video session: {error_msg}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": error_msg}

    return await asyncio.to_thread(insert_session)


async def get_videos_by_topic(user_id: str, topic_id: str = None) -> Dict[str, Any]:
    """
    Get all videos for a user, optionally filtered by topic.

    Args:
        user_id: User ID
        topic_id: Optional topic ID to filter by

    Returns:
        Dictionary with success flag and videos list
    """
    if not supabase:
        return {"success": False, "message": "Supabase client not initialized", "videos": []}

    def fetch_videos():
        try:
            query = supabase.table("video_sessions")\
                .select("*, topics(id, name, description)")\
                .eq("user_id", user_id)

            if topic_id:
                query = query.eq("topic_id", topic_id)

            response = query.order("created_at", desc=True).execute()

            videos = response.data if response.data else []

            return {"success": True, "videos": videos}
        except Exception as e:
            error_msg = str(e)
            print(f"Error fetching videos by topic: {error_msg}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": error_msg, "videos": []}

    return await asyncio.to_thread(fetch_videos)


async def cleanup_all_user_data(user_id: str) -> Dict[str, Any]:
    """
    Clean up ALL user data - videos, sessions, topics, and feedback.
    Use with caution - this is irreversible!

    Args:
        user_id: The user ID to clean up

    Returns:
        Dictionary with success flag and cleanup details
    """
    if not supabase:
        return {"success": False, "message": "Supabase client not initialized"}

    def cleanup_operations():
        deleted_items = {
            "storage_files": 0,
            "video_sessions": 0,
            "feedback_segments": 0,
            "topics": 0
        }

        try:
            # 1. Delete all files from storage
            print(f"Cleaning up storage files for user {user_id}...")
            try:
                # List all files in user's folder
                files = supabase.storage.from_(supabase_bucket).list(path=f"{user_id}/")

                if files:
                    # Delete each file
                    for file in files:
                        if file.get('name', '').endswith('.mp4'):
                            file_path = f"{user_id}/{file['name']}"
                            try:
                                supabase.storage.from_(supabase_bucket).remove([file_path])
                                deleted_items["storage_files"] += 1
                                print(f"Deleted storage file: {file_path}")
                            except Exception as file_error:
                                print(f"Error deleting file {file_path}: {file_error}")
            except Exception as storage_error:
                print(f"Error cleaning storage: {storage_error}")

            # 2. Delete all feedback segments
            print(f"Deleting feedback segments for user {user_id}...")
            try:
                feedback_response = supabase.table("ai_feedback_segments")\
                    .delete()\
                    .eq("user_id", user_id)\
                    .execute()
                deleted_items["feedback_segments"] = len(feedback_response.data) if feedback_response.data else 0
                print(f"Deleted {deleted_items['feedback_segments']} feedback segments")
            except Exception as feedback_error:
                print(f"Error deleting feedback segments: {feedback_error}")

            # 3. Delete all video sessions
            print(f"Deleting video sessions for user {user_id}...")
            try:
                sessions_response = supabase.table("video_sessions")\
                    .delete()\
                    .eq("user_id", user_id)\
                    .execute()
                deleted_items["video_sessions"] = len(sessions_response.data) if sessions_response.data else 0
                print(f"Deleted {deleted_items['video_sessions']} video sessions")
            except Exception as sessions_error:
                print(f"Error deleting video sessions: {sessions_error}")

            # 4. Delete all topics
            print(f"Deleting topics for user {user_id}...")
            try:
                topics_response = supabase.table("topics")\
                    .delete()\
                    .eq("user_id", user_id)\
                    .execute()
                deleted_items["topics"] = len(topics_response.data) if topics_response.data else 0
                print(f"Deleted {deleted_items['topics']} topics")
            except Exception as topics_error:
                print(f"Error deleting topics: {topics_error}")

            return {
                "success": True,
                "message": "All user data cleaned successfully",
                "deleted": deleted_items,
                "total_items": sum(deleted_items.values())
            }

        except Exception as e:
            error_msg = str(e)
            print(f"Error during cleanup: {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": error_msg,
                "deleted": deleted_items
            }

    return await asyncio.to_thread(cleanup_operations)