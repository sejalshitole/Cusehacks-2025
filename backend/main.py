from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime
import json
import base64
import asyncio
import uuid
from video_recorder import (
    VideoRecorder,
    upload_to_supabase,
    get_user_videos,
    save_feedback_segments_to_supabase,
)
from feedback_agent import FeedbackAgent

app = FastAPI(title="SpeakFlow API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class HealthResponse(BaseModel):
    status: str
    message: str

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    quantity: int = 1

# Routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to Zynk API"}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", message="Server is running")

@app.get("/api/items")
async def get_items():
    """Get all items"""
    return {
        "items": [
            {"id": 1, "name": "Item 1", "price": 10.99},
            {"id": 2, "name": "Item 2", "price": 20.99},
        ]
    }

@app.post("/api/items")
async def create_item(item: Item):
    """Create a new item"""
    return {
        "message": "Item created successfully",
        "item": item.dict()
    }

@app.get("/api/items/{item_id}")
async def get_item(item_id: int):
    """Get a specific item by ID"""
    return {
        "id": item_id,
        "name": f"Item {item_id}",
        "price": 10.99 * item_id
    }

@app.get("/api/videos/{user_id}")
async def get_videos(user_id: str):
    """Get all videos for a specific user"""
    try:
        videos = await get_user_videos(user_id)
        
        if videos is None:
            return {
                "success": False,
                "message": "Error retrieving videos",
                "videos": []
            }
        
        return {
            "success": True,
            "user_id": user_id,
            "count": len(videos),
            "videos": videos
        }
    except Exception as e:
        print(f"Error in get_videos endpoint: {e}")
        return {
            "success": False,
            "message": str(e),
            "videos": []
        }

@app.get("/api/feedback/{session_id}")
async def get_feedback(session_id: str):
    """Get AI feedback segments for a specific session"""
    try:
        from supabase import create_client
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            return {
                "success": False,
                "message": "Supabase configuration not found",
                "feedback": []
            }
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Query feedback segments for the session
        response = supabase.table("ai_feedback_segments")\
            .select("*")\
            .eq("session_id", session_id)\
            .order("start_seconds", desc=False)\
            .execute()
        
        feedback_segments = response.data if response.data else []
        
        return {
            "success": True,
            "session_id": session_id,
            "count": len(feedback_segments),
            "feedback": feedback_segments
        }
    except Exception as e:
        print(f"Error in get_feedback endpoint: {e}")
        return {
            "success": False,
            "message": str(e),
            "feedback": []
        }

# Store active video recorders and feedback agents
active_recorders: Dict[str, VideoRecorder] = {}
active_feedback_agents: Dict[str, FeedbackAgent] = {}

# WebSocket endpoint for real-time video processing
@app.websocket("/ws/video")
async def websocket_video_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time video frame processing with AI feedback"""
    await websocket.accept()
    print("WebSocket connection established")
    
    # Generate unique session ID for this connection
    session_id = str(uuid.uuid4())
    video_recorder = None
    feedback_agent = None
    user_id = "anonymous"  # Default value
    
    # Feedback collection buffers
    frame_buffer: List[str] = []
    audio_buffer: Optional[str] = None
    session_start_time = asyncio.get_event_loop().time()
    last_feedback_time = session_start_time
    feedback_segments: List[Dict[str, Any]] = []
    FEEDBACK_INTERVAL = 5.0  # seconds
    
    try:
        data_chunk_count = 0
        
        while True:
            # Receive data from client
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type")
            
            # Handle user authentication message
            if message_type == "auth":
                user_id = message.get("user_id", "anonymous")
                print(f"User authenticated: {user_id} for session {session_id}")
                
                # Initialize feedback agent
                feedback_agent = FeedbackAgent()
                active_feedback_agents[session_id] = feedback_agent
                
                await websocket.send_json({
                    "type": "auth_success",
                    "session_id": session_id,
                    "message": "Authentication successful"
                })
                continue
            
            if message_type == "video_chunk":
                if video_recorder is None:
                    video_recorder = VideoRecorder(session_id, user_id=user_id, fps=30)
                    active_recorders[session_id] = video_recorder
                    print(f"Started recording for session {session_id}, user {user_id}")
                
                # Video chunks are for recording only, not for AI analysis
                data_chunk_count += 1

                # Send status update
                if data_chunk_count % 30 == 0:
                    status = {
                        "type": "status",
                        "segments_processed": data_chunk_count,
                        "message": "Recording...",
                    }
                    await websocket.send_json(status)

            elif message_type == "video_complete":
                print(f"Received video_complete message for session {session_id}")
                if video_recorder is None:
                    video_recorder = VideoRecorder(session_id, user_id=user_id, fps=30)
                    active_recorders[session_id] = video_recorder
                    print(f"Started recording for session {session_id}, user {user_id}")

                complete_data = message.get("data", "")
                if complete_data:
                    print(f"Video data received: {len(complete_data)} characters")
                    video_recorder.set_final_webm_blob(complete_data)
                    await websocket.send_json(
                        {
                            "type": "status",
                            "message": "Final video received. Preparing upload…",
                        }
                    )
                else:
                    print("ERROR: No video data in video_complete message")
                    await websocket.send_json(
                        {
                            "type": "upload_error",
                            "message": "No video data provided",
                        }
                    )

            elif message_type == "frame":
                # Initialize video recorder and feedback agent on first frame
                if video_recorder is None:
                    video_recorder = VideoRecorder(session_id, user_id=user_id, fps=30)
                    active_recorders[session_id] = video_recorder
                    print(f"Started recording for session {session_id}, user {user_id}")
                
                if feedback_agent is None:
                    feedback_agent = FeedbackAgent()
                    active_feedback_agents[session_id] = feedback_agent
                    print(f"Started feedback agent for session {session_id}")
                
                # Add frame to recorder
                frame_data = message.get("data", "")
                video_recorder.add_frame(frame_data)
                
                # Add frame to feedback buffer
                frame_buffer.append(frame_data)
                
                data_chunk_count += 1
                
                # Check if it's time for AI feedback (every 5 seconds)
                current_time = asyncio.get_event_loop().time()
                if current_time - last_feedback_time >= FEEDBACK_INTERVAL:
                    if frame_buffer:
                        # Generate AI feedback in background to avoid blocking
                        try:
                            ai_feedback = feedback_agent.analyze_segment(
                                frames=frame_buffer[-6:],  # Use last 6 frames (approx 0.2s at 30fps)
                                audio_data=audio_buffer
                            )
                            
                            current_offset = current_time - session_start_time
                            segment_start = max(0.0, last_feedback_time - session_start_time)
                            segment_end = max(segment_start, current_offset)
                            created_at = datetime.utcnow().isoformat() + "Z"

                            feedback_text = (ai_feedback or "").strip()
                            is_actionable = (
                                bool(feedback_text)
                                and feedback_text.upper() != "OK"
                                and not feedback_text.lower().startswith("error")
                            )

                            payload: Dict[str, Any] = {
                                "type": "ai_feedback",
                                "message": ai_feedback,
                                "timestamp": round(segment_end, 2),
                                "session_id": session_id,
                                "is_actionable": is_actionable,
                            }

                            if is_actionable:
                                segment_entry = {
                                    "feedback_text": feedback_text,
                                    "start_seconds": round(segment_start, 2),
                                    "end_seconds": round(segment_end, 2),
                                    "created_at": created_at,
                                }
                                feedback_segments.append(segment_entry)
                                payload.update(
                                    {
                                        "start_seconds": segment_entry["start_seconds"],
                                        "end_seconds": segment_entry["end_seconds"],
                                        "created_at": created_at,
                                        "segment_index": len(feedback_segments) - 1,
                                    }
                                )

                            # Send AI feedback to client
                            await websocket.send_json(payload)

                            if is_actionable:
                                print(
                                    "AI Feedback sent:",
                                    f"{feedback_text} ({payload['start_seconds']}s-{payload['end_seconds']}s)",
                                )
                            else:
                                print(f"AI Feedback (non-actionable): {ai_feedback}")
                        except Exception as e:
                            print(f"Error generating AI feedback: {e}")
                        
                        # Clear buffers and reset timer
                        frame_buffer.clear()
                        audio_buffer = None
                        last_feedback_time = current_time
                
                # Send status acknowledgment
                if data_chunk_count % 60 == 0:
                    status = {
                        "type": "status",
                        "segments_processed": data_chunk_count,
                        "message": "Processing..."
                    }
                    await websocket.send_json(status)
                    
            elif message_type == "audio":
                print(f"Received audio chunk for session {session_id}")
                # Handle audio chunks
                if video_recorder is None:
                    video_recorder = VideoRecorder(session_id, user_id=user_id, fps=30)
                    active_recorders[session_id] = video_recorder
                    print(f"Started recording for session {session_id}, user {user_id}")
                
                # Add audio chunk to recorder
                audio_data = message.get("data", "")
                video_recorder.add_audio_chunk(audio_data)
                
                # Store latest audio for feedback
                audio_buffer = audio_data
                    
            elif message_type == "stop":
                # Handle stop recording request
                print(f"Stop recording request received for session {session_id}")
                
                if video_recorder:
                    print(f"Video recorder exists, has_combined_blob: {video_recorder.has_combined_blob}")
                    await websocket.send_json(
                        {
                            "type": "status",
                            "message": "Processing recording…",
                        }
                    )

                    # Save video to disk
                    video_path = video_recorder.save_video()
                    print(f"Video save result: {video_path}")
                    
                    if video_path:
                        print(f"Uploading video to Supabase: {video_path}")
                        # Upload to Supabase
                        public_url = await upload_to_supabase(video_path, session_id, user_id)
                        
                        if public_url:
                            print(f"Upload successful: {public_url}")
                            # Send success response with video URL
                            await websocket.send_json({
                                "type": "upload_complete",
                                "url": public_url,
                                "message": "Video uploaded successfully",
                                "session_id": session_id,
                            })
                        else:
                            print("Upload to Supabase failed")
                            await websocket.send_json({
                                "type": "upload_error",
                                "message": "Failed to upload video to Supabase",
                                "session_id": session_id,
                            })
                        
                        # Cleanup temporary file
                        video_recorder.cleanup()
                    else:
                        print("Failed to save video - no video path returned")
                        await websocket.send_json({
                            "type": "upload_error",
                            "message": "Failed to save video"
                        })
                    
                    # Remove from active recorders
                    if session_id in active_recorders:
                        del active_recorders[session_id]
                else:
                    print(f"No video recorder found for session {session_id}")
                
                # Persist AI feedback segments to Supabase
                try:
                    save_result = await save_feedback_segments_to_supabase(
                        session_id=session_id,
                        user_id=user_id,
                        segments=feedback_segments,
                    )

                    if save_result.get("success"):
                        await websocket.send_json(
                            {
                                "type": "feedback_saved",
                                "session_id": session_id,
                                "segments_saved": save_result.get("count", 0),
                            }
                        )
                        print(
                            f"Saved {save_result.get('count', 0)} feedback segments for session {session_id}"
                        )
                    else:
                        await websocket.send_json(
                            {
                                "type": "feedback_save_error",
                                "session_id": session_id,
                                "message": save_result.get(
                                    "error", "Failed to save feedback segments"
                                ),
                            }
                        )
                        print(
                            f"Failed to save feedback segments for session {session_id}: {save_result.get('error')}"
                        )
                except Exception as e:
                    error_text = str(e)
                    await websocket.send_json(
                        {
                            "type": "feedback_save_error",
                            "session_id": session_id,
                            "message": error_text,
                        }
                    )
                    print(f"Exception while saving feedback segments: {error_text}")

                feedback_segments.clear()

                # Cleanup feedback agent
                if session_id in active_feedback_agents:
                    del active_feedback_agents[session_id]
                
                break  # Exit the loop after handling stop
                    
            elif message_type == "ping":
                # Respond to ping messages to keep connection alive
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        print(f"WebSocket connection closed for session {session_id}")
        # Cleanup recorder if connection closed unexpectedly
        if session_id in active_recorders:
            active_recorders[session_id].cleanup()
            del active_recorders[session_id]
        # Cleanup feedback agent
        if session_id in active_feedback_agents:
            del active_feedback_agents[session_id]
    except Exception as e:
        print(f"WebSocket error: {e}")
        # Cleanup recorder on error
        if session_id in active_recorders:
            active_recorders[session_id].cleanup()
            del active_recorders[session_id]
        # Cleanup feedback agent
        if session_id in active_feedback_agents:
            del active_feedback_agents[session_id]
        await websocket.close()

# Run the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)