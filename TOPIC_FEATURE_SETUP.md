# Topic Feature Setup Guide

This guide will help you set up the new topic linking feature for video recordings.

## Overview

The topic feature allows users to organize their recordings into topics (e.g., "Interview Practice", "Public Speaking", "General"). Each recording is linked to a topic, which can later be used to generate detailed reports.

## Database Setup

### Step 1: Run the SQL Migration

1. Go to your Supabase Dashboard: https://supabase.com/dashboard
2. Select your project
3. Navigate to **SQL Editor** (left sidebar)
4. Click **New Query**
5. Copy and paste the entire contents of `backend/supabase_schema.sql`
6. Click **Run** or press `Ctrl+Enter`

This will create:
- `topics` table - stores user-created topics
- `video_sessions` table - stores video metadata with topic links
- Appropriate indexes and Row Level Security (RLS) policies
- A trigger to auto-create a "General" topic for new users

### Step 2: Verify the Tables

Run this query in the SQL Editor to verify:

```sql
SELECT * FROM topics LIMIT 5;
SELECT * FROM video_sessions LIMIT 5;
```

## Features Implemented

### Backend (`backend/`)

1. **New Functions in `video_recorder.py`:**
   - `get_user_topics(user_id)` - Fetch all topics for a user
   - `create_topic(user_id, name, description)` - Create a new topic
   - `save_video_session(...)` - Save video metadata with topic link
   - `get_videos_by_topic(user_id, topic_id)` - Filter videos by topic

2. **New API Endpoints in `main.py`:**
   - `GET /api/topics/{user_id}` - Get all topics
   - `POST /api/topics/create` - Create a new topic
   - `POST /api/video-sessions/save` - Save video session metadata
   - `GET /api/videos/by-topic/{user_id}?topic_id=...` - Get videos by topic

### Frontend (`frontend/`)

1. **Record Page** (`app/protected/record/page.tsx`):
   - Topic selection dropdown before starting recording
   - "New Topic" button to create topics on the fly
   - Auto-saves video session with selected topic after recording
   - Auto-selects "General" topic by default

2. **UI Components**:
   - New `components/ui/select.tsx` - Dropdown select component

## Usage

### For Users:

1. **Navigate to Record Page** (`/protected/record`)
2. **Select or Create a Topic:**
   - Choose from existing topics in the dropdown
   - Or click "+ New" to create a new topic
3. **Start Recording** - The video will be linked to the selected topic
4. **View Videos by Topic** - Use the my-videos page (future enhancement)

### Creating a New Topic:

1. Click "+ New" button next to topic dropdown
2. Enter topic name (e.g., "Job Interview Practice")
3. Optionally add a description
4. Click "Create"
5. The new topic is automatically selected

## Next Steps

1. **Update My-Videos Page** to show topics and filter by topic
2. **Implement Detailed Report Generation** using videos from a specific topic
3. **Add Topic Management Page** to edit/delete topics
4. **Add Topic Statistics** (number of recordings, total duration, etc.)

## API Examples

### Get Topics
```bash
curl http://localhost:8000/api/topics/{user_id}
```

### Create Topic
```bash
curl -X POST http://localhost:8000/api/topics/create \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-uuid",
    "name": "Interview Practice",
    "description": "Practice for job interviews"
  }'
```

### Save Video Session
```bash
curl -X POST http://localhost:8000/api/video-sessions/save \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-uuid",
    "user_id": "user-uuid",
    "topic_id": "topic-uuid",
    "video_url": "https://...",
    "filename": "session.mp4"
  }'
```

### Get Videos by Topic
```bash
curl "http://localhost:8000/api/videos/by-topic/{user_id}?topic_id={topic_id}"
```

## Troubleshooting

### Topics Not Loading
- Check browser console for errors
- Verify backend is running on port 8000
- Check that SQL migration was successful

### "General" Topic Not Created
- The trigger creates it for new users only
- For existing users, it's created automatically when they first visit the record page
- Or manually create it via the UI

### Video Session Not Saving
- Check browser console for errors
- Verify the `video_sessions` table exists
- Check that RLS policies allow INSERT operations

## Files Changed

### Backend
- `backend/supabase_schema.sql` (NEW) - Database schema
- `backend/video_recorder.py` - Added topic management functions
- `backend/main.py` - Added topic API endpoints

### Frontend
- `frontend/app/protected/record/page.tsx` - Added topic selection UI
- `frontend/components/ui/select.tsx` (NEW) - Select dropdown component

## Database Schema

### topics table
```sql
- id (UUID, primary key)
- user_id (UUID, foreign key to auth.users)
- name (TEXT, unique per user)
- description (TEXT, optional)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

### video_sessions table
```sql
- id (UUID, primary key)
- session_id (TEXT, unique)
- user_id (UUID, foreign key to auth.users)
- topic_id (UUID, foreign key to topics, nullable)
- video_url (TEXT)
- filename (TEXT)
- duration_seconds (DECIMAL, optional)
- size_bytes (BIGINT, optional)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```
