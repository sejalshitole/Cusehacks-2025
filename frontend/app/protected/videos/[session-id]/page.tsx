"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface FeedbackSegment {
  feedback_text?: string;
  start_seconds?: number;
  end_seconds?: number;
  created_at?: string;
}

export default function SessionDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params?.["session-id"] as string | undefined;

  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackSegment[]>([]);
  const [reportMd, setReportMd] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"feedback" | "report">("feedback");

  useEffect(() => {
    if (!sessionId) return;

    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const supabase = createClient();

        // 1) get current user (to build storage path)
        const { data: authData } = await supabase.auth.getUser();
        const user = (authData as any)?.user;

        // 2) Construct public URL for video
        if (user && user.id) {
          try {
            const pub = supabase.storage.from("videos").getPublicUrl(`${user.id}/${sessionId}.mp4`);
            const candidateUrl = (pub as any)?.data?.publicUrl ?? (pub as any)?.publicUrl ?? (pub as any)?.data;
            setVideoUrl(candidateUrl ?? null);
          } catch (e) {
            console.warn("Failed to get public URL", e);
          }
        }

        // 3) Fetch AI realtime feedback from backend
        try {
          const fbRes = await fetch(`http://localhost:8000/api/feedback/${sessionId}`);
          if (fbRes.ok) {
            const fbJson = await fbRes.json();
            setFeedback(fbJson.feedback ?? []);
          } else {
            console.warn("Failed to fetch feedback", fbRes.status);
          }
        } catch (e) {
          console.warn("Feedback fetch error", e);
        }

        // 4) Fetch detailed report from Supabase table `video_reports`
        try {
          const { data: reports, error: reportError } = await supabase
            .from("video_reports")
            .select("*")
            .eq("session_id", sessionId)
            .order("created_at", { ascending: false })
            .limit(1);

          if (reportError) {
            console.warn("reportError", reportError);
          } else if (reports && reports.length > 0) {
            setReportMd((reports as any)[0].report_md || null);
          }
        } catch (e) {
          console.warn("Error fetching report", e);
        }

      } catch (err: any) {
        console.error(err);
        setError(err?.message ?? String(err));
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [sessionId]);

  return (
    <div className="p-6 max-w-7xl  min-h-screen">
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" onClick={() => router.back()}>Back</Button>
        <h1 className="text-2xl font-semibold">Session: {sessionId}</h1>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">Loading...</div>
      ) : error ? (
        <div className="text-red-600">Error: {error}</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* Left: Video */}
          <div className="lg:pr-2">
            <Card className="h-full">
              <CardContent>
                {videoUrl ? (
                  <video src={videoUrl} controls className="w-full rounded-md max-h-[65vh] object-contain" />
                ) : (
                  <div className="bg-muted p-12 rounded-md text-center">No video URL available</div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right: Tabs for Feedback / Report */}
          <div className="lg:pl-2 flex flex-col">
            <div className="flex items-end gap-3 mb-4 border-b pb-3">
              <button
                onClick={() => setActiveTab("feedback")}
                className={`px-4 py-2 -mb-1 rounded-t-md font-medium ${activeTab === "feedback" ? "border-b-2 border-primary text-primary" : "text-muted-foreground hover:text-foreground"}`}>
                AI Feedback
              </button>
              <button
                onClick={() => setActiveTab("report")}
                className={`px-4 py-2 -mb-1 rounded-t-md font-medium ${activeTab === "report" ? "border-b-2 border-primary text-primary" : "text-muted-foreground hover:text-foreground"}`}>
                Detailed Report
              </button>
            </div>

            <div className="space-y-4">
              {activeTab === "feedback" ? (
                <Card className="h-full">
                  <CardContent className="p-4">
                    <h3 className="text-lg font-medium mb-3">AI Feedback Segments</h3>
                    {feedback && feedback.length > 0 ? (
                      <div className="space-y-3">
                        {feedback.map((fb, idx) => (
                          <div key={idx} className="p-4 border rounded-lg bg-muted/5">
                            <div className="text-sm text-muted-foreground mb-1">{fb.start_seconds ?? "0.00"}s — {fb.end_seconds ?? "0.00"}s</div>
                            <div className="mt-1">{fb.feedback_text ?? "(no text)"}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">No AI feedback segments saved for this session.</div>
                    )}
                  </CardContent>
                </Card>
              ) : (
                <Card className="h-full">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-medium mb-2">Detailed Report</h3>
                    </div>
                    {reportMd ? (
                      <div className="prose max-w-none overflow-auto max-h-[65vh]">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportMd}</ReactMarkdown>
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">No detailed report yet. Analysis may be in progress.</div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
