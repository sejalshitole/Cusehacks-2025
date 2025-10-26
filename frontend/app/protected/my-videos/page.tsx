'use client';

import { createClient } from "@/lib/supabase/client";
import { useEffect, useState } from "react";

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

  useEffect(() => {
    const fetchVideos = async () => {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();

      if (user) {
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

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div className="flex flex-col items-center gap-8">
      <h1 className="text-3xl font-bold">My Videos</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 w-full">
        {videos.length > 0 ? (
          videos.map(video => (
            <div key={video.session_id} className="border rounded-md overflow-hidden">
              <video src={video.url} controls className="w-full" />
              <div className="p-4">
                <p className="font-semibold">{video.name}</p>
                <p className="text-sm text-muted-foreground">
                  {new Date(video.created_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))
        ) : (
          <p>No videos found.</p>
        )}
      </div>
    </div>
  );
}
