-- Topics table to organize video recordings
CREATE TABLE IF NOT EXISTS topics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, name)
);

-- Video sessions table to store metadata about recordings
CREATE TABLE IF NOT EXISTS video_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    topic_id UUID REFERENCES topics(id) ON DELETE SET NULL,
    video_url TEXT NOT NULL,
    filename TEXT NOT NULL,
    duration_seconds DECIMAL(10, 2),
    size_bytes BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Update ai_feedback_segments to link to video_sessions (if not already linked)
-- This assumes ai_feedback_segments table already exists
-- ALTER TABLE ai_feedback_segments ADD COLUMN IF NOT EXISTS video_session_id UUID REFERENCES video_sessions(id) ON DELETE CASCADE;

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_topics_user_id ON topics(user_id);
CREATE INDEX IF NOT EXISTS idx_video_sessions_user_id ON video_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_video_sessions_topic_id ON video_sessions(topic_id);
CREATE INDEX IF NOT EXISTS idx_video_sessions_session_id ON video_sessions(session_id);

-- Row Level Security (RLS) Policies for topics table
ALTER TABLE topics ENABLE ROW LEVEL SECURITY;

-- Allow service role to bypass RLS (for backend operations)
CREATE POLICY "Service role can do everything on topics"
    ON topics
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Users can view their own topics"
    ON topics FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own topics"
    ON topics FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own topics"
    ON topics FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own topics"
    ON topics FOR DELETE
    USING (auth.uid() = user_id);

-- Row Level Security (RLS) Policies for video_sessions table
ALTER TABLE video_sessions ENABLE ROW LEVEL SECURITY;

-- Allow service role to bypass RLS (for backend operations)
CREATE POLICY "Service role can do everything on video_sessions"
    ON video_sessions
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Users can view their own video sessions"
    ON video_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own video sessions"
    ON video_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own video sessions"
    ON video_sessions FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own video sessions"
    ON video_sessions FOR DELETE
    USING (auth.uid() = user_id);

-- Function to automatically create a "General" topic for new users
CREATE OR REPLACE FUNCTION create_default_topic()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO topics (user_id, name, description)
    VALUES (NEW.id, 'General', 'Default topic for uncategorized recordings')
    ON CONFLICT (user_id, name) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to create default topic when user signs up
DROP TRIGGER IF EXISTS on_auth_user_created_create_topic ON auth.users;
CREATE TRIGGER on_auth_user_created_create_topic
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION create_default_topic();
