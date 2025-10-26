'use client';

import { createClient } from "@/lib/supabase/client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

interface Video {
  session_id: string;
  url: string;
  created_at: string;
  name: string;
}

export default function MyVideosPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingVideoId, setEditingVideoId] = useState<string | null>(null);
  const [newVideoName, setNewVideoName] = useState<string>("");
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    const fetchVideos = async () => {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();

      if (user) {
        setUserId(user.id);
        try {
          const response = await fetch(`http://localhost:8000/api/videos/${user.id}`);
          if (!response.ok) {
            throw new Error('Failed to fetch videos');
          }
          const data = await response.json();
          setVideos(data.videos);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'An unknown error occurred');
        }
      }
      setIsLoading(false);
    };

    fetchVideos();
  }, []);

  const handleRename = async (videoSessionId: string) => {
    if (!userId || !newVideoName.trim()) return;

    const video = videos.find(v => v.session_id === videoSessionId);
    if (!video) return;

    try {
      const response = await fetch('http://localhost:8000/api/videos/rename', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          old_filename: video.name,
          new_filename: newVideoName.trim(),
        }),
      });

      const result = await response.json();

      if (result.success) {
        // Update the video in the list
        setVideos(prevVideos =>
          prevVideos.map(v =>
            v.session_id === videoSessionId
              ? { ...v, name: result.new_filename, url: result.url }
              : v
          )
        );
        setEditingVideoId(null);
        setNewVideoName("");
      } else {
        setError(result.message || 'Failed to rename video');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to rename video');
    }
  };

  const handleDelete = async (videoSessionId: string) => {
    if (!userId) return;

    const video = videos.find(v => v.session_id === videoSessionId);
    if (!video) return;

    if (!confirm(`Are you sure you want to delete this video?`)) return;

    try {
      const response = await fetch('http://localhost:8000/api/videos/delete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          filename: video.name,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('Delete response:', result);

      if (result.success) {
        // Remove the video from the list
        setVideos(prevVideos => prevVideos.filter(v => v.session_id !== videoSessionId));
      } else {
        console.error('Delete failed:', result.message);
        setError(result.message || 'Failed to delete video');
      }
    } catch (err) {
      console.error('Delete error:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete video');
    }
  };

  const startEditing = (videoSessionId: string, currentName: string) => {
    setEditingVideoId(videoSessionId);
    // Remove .mp4 extension for editing
    setNewVideoName(currentName.replace('.mp4', ''));
  };

  const cancelEditing = () => {
    setEditingVideoId(null);
    setNewVideoName("");
  };

  if (isLoading) {
    return <div className="flex justify-center items-center min-h-screen">Loading...</div>;
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-red-500">Error: {error}</p>
        <Button onClick={() => window.location.reload()}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-8 p-6">
      <h1 className="text-3xl font-bold">My Videos</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 w-full max-w-7xl">
        {videos.length > 0 ? (
          videos.map(video => (
            <Card key={video.session_id} className="overflow-hidden">
              <video src={video.url} controls className="w-full" />
              <CardContent className="p-4">
                {editingVideoId === video.session_id ? (
                  <div className="space-y-2">
                    <Input
                      type="text"
                      value={newVideoName}
                      onChange={(e) => setNewVideoName(e.target.value)}
                      placeholder="Enter new name"
                      className="w-full"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          handleRename(video.session_id);
                        } else if (e.key === 'Escape') {
                          cancelEditing();
                        }
                      }}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleRename(video.session_id)}
                        className="flex-1"
                      >
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={cancelEditing}
                        className="flex-1"
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div>
                      <p className="font-semibold truncate">{video.name.replace('.mp4', '')}</p>
                      <p className="text-sm text-muted-foreground">
                        {new Date(video.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => startEditing(video.session_id, video.name)}
                        className="flex-1"
                      >
                        Rename
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleDelete(video.session_id)}
                        className="flex-1"
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))
        ) : (
          <div className="col-span-full text-center text-muted-foreground">
            <p>No videos found.</p>
          </div>
        )}
      </div>
    </div>
  );
}
