'use client';

import { createClient } from "@/lib/supabase/client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Topic {
  id: string;
  name: string;
  description?: string;
}

interface Video {
  session_id: string;
  url?: string;
  video_url?: string;
  created_at: string;
  name?: string;
  filename?: string;
  topics?: Topic | null;
}

export default function MyVideosPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [filteredVideos, setFilteredVideos] = useState<Video[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingVideoId, setEditingVideoId] = useState<string | null>(null);
  const [newVideoName, setNewVideoName] = useState<string>("");
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();

      if (user) {
        setUserId(user.id);
        console.log('Fetching videos for user:', user.id);

        try {
          // Fetch videos
          const videosResponse = await fetch(`http://localhost:8000/api/videos/${user.id}`);
          console.log('Videos response status:', videosResponse.status);

          if (!videosResponse.ok) {
            throw new Error(`Failed to fetch videos: ${videosResponse.status}`);
          }

          const videosData = await videosResponse.json();
          console.log('Videos data received:', videosData);

          const videosList = videosData.videos || [];
          console.log('Number of videos:', videosList.length);

          setVideos(videosList);
          setFilteredVideos(videosList);

          // Fetch topics
          const topicsResponse = await fetch(`http://localhost:8000/api/topics/${user.id}`);
          console.log('Topics response status:', topicsResponse.status);

          if (topicsResponse.ok) {
            const topicsData = await topicsResponse.json();
            console.log('Topics data:', topicsData);

            if (topicsData.success && topicsData.topics) {
              setTopics(topicsData.topics);
            }
          }
        } catch (err) {
          console.error('Error fetching data:', err);
          setError(err instanceof Error ? err.message : 'An unknown error occurred');
        }
      } else {
        console.log('No authenticated user found');
        setError('Please log in to view your videos');
      }
      setIsLoading(false);
    };

    fetchData();
  }, []);

  // Filter videos when topic selection changes
  useEffect(() => {
    if (!selectedTopicId) {
      setFilteredVideos(videos);
    } else {
      setFilteredVideos(
        videos.filter(video => video.topics?.id === selectedTopicId)
      );
    }
  }, [selectedTopicId, videos]);

  const handleRename = async (videoSessionId: string) => {
    if (!userId || !newVideoName.trim()) return;

    const video = videos.find(v => v.session_id === videoSessionId);
    if (!video) return;

    // Get the correct old filename
    const oldFilename = video.filename || video.name || `${videoSessionId}.mp4`;

    try {
      const response = await fetch('http://localhost:8000/api/videos/rename', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          old_filename: oldFilename,
          new_filename: newVideoName.trim(),
        }),
      });

      const result = await response.json();

      if (result.success) {
        // Update the video in both lists
        const updateVideo = (v: Video) =>
          v.session_id === videoSessionId
            ? {
                ...v,
                name: result.new_filename,
                filename: result.new_filename,
                url: result.url,
                video_url: result.url
              }
            : v;

        setVideos(prevVideos => prevVideos.map(updateVideo));
        setFilteredVideos(prevVideos => prevVideos.map(updateVideo));
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

    // Get the correct filename
    const filename = video.filename || video.name || `${videoSessionId}.mp4`;

    if (!confirm(`Are you sure you want to delete this video?`)) return;

    try {
      const response = await fetch('http://localhost:8000/api/videos/delete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          filename: filename,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('Delete response:', result);

      if (result.success) {
        // Remove the video from both lists
        setVideos(prevVideos => prevVideos.filter(v => v.session_id !== videoSessionId));
        setFilteredVideos(prevVideos => prevVideos.filter(v => v.session_id !== videoSessionId));
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

      {/* Topic Filter */}
      {topics.length > 0 && (
        <div className="w-full max-w-7xl">
          <div className="flex items-center gap-4">
            <label htmlFor="topic-filter" className="text-sm font-medium">
              Filter by Topic:
            </label>
            <Select
              value={selectedTopicId || "all"}
              onValueChange={(value) => setSelectedTopicId(value === "all" ? null : value)}
            >
              <SelectTrigger id="topic-filter" className="w-[200px]">
                <SelectValue placeholder="All Topics" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Topics</SelectItem>
                {topics.map((topic) => (
                  <SelectItem key={topic.id} value={topic.id}>
                    {topic.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedTopicId && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedTopicId(null)}
              >
                Clear Filter
              </Button>
            )}
            <span className="text-sm text-muted-foreground ml-auto">
              {filteredVideos.length} {filteredVideos.length === 1 ? 'video' : 'videos'}
            </span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 w-full max-w-7xl">
        {filteredVideos.length > 0 ? (
          filteredVideos.map(video => {
            const videoUrl = video.video_url || video.url;
            const videoName = video.filename || video.name || 'Untitled';

            return (
            <Card key={video.session_id} className="overflow-hidden">
              <video src={videoUrl} controls className="w-full" />
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
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <p className="font-semibold truncate">{videoName.replace('.mp4', '')}</p>
                        {video.topics && (
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 whitespace-nowrap">
                            {video.topics.name}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {new Date(video.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => startEditing(video.session_id, videoName)}
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
            );
          })
        ) : (
          <div className="col-span-full text-center text-muted-foreground">
            <p>No videos found.</p>
          </div>
        )}
      </div>
    </div>
  );
}
