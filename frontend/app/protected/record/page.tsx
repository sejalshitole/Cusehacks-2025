'use client';

import { Button } from "@/components/ui/button";
import { useEffect, useRef, useState } from "react";

export default function RecordPage() {
  const [isRecording, setIsRecording] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (isRecording) {
      const newWs = new WebSocket('ws://localhost:8000/ws/video');
      newWs.onopen = () => {
        console.log('WebSocket connected');
        // You would typically send auth info here
      };
      setWs(newWs);

      navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        .then(stream => {
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
          }
          // TODO: Send stream to backend via WebSocket
        })
        .catch(err => console.error('Error accessing media devices:', err));

      return () => {
        newWs.close();
        setWs(null);
      };
    } else if (ws) {
      ws.close();
    }
  }, [isRecording]);

  const handleToggleRecording = () => {
    setIsRecording(prev => !prev);
  };

  return (
    <div className="flex flex-col items-center gap-8">
      <h1 className="text-3xl font-bold">Record Session</h1>
      <div className="w-full max-w-4xl aspect-video bg-muted rounded-md">
        <video ref={videoRef} autoPlay muted className="w-full h-full rounded-md" />
      </div>
      <Button onClick={handleToggleRecording} size="lg">
        {isRecording ? 'Stop Recording' : 'Start Recording'}
      </Button>
    </div>
  );
}
