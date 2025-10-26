'use client'

import { useEffect } from 'react'
import { createClient } from "@/lib/supabase/client";

import { Toaster, toast } from "sonner"


export default function RealtimeToastListener() {
  useEffect(() => {
    const supabaseClient = createClient()
    let userId: string | null = null;
    
    // Get current user ID
    supabaseClient.auth.getUser().then(({ data: { user } }) => {
        if (user) {
            userId = user.id;
            console.log("RealtimeToastListener listening for user ID:", userId);
        }
    });

    const channel = supabaseClient
      .channel('user-inserts')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'video_reports' },
        (payload) => {
          const newRow = payload.new
          if (newRow.user_id === userId) {
            toast.success('The AI has finished processing your video! Check your reports.')
          }
        }
      )
      .subscribe()

    return () => {
      supabaseClient.removeChannel(channel)
    }
  }, [])

  return <Toaster position="top-right" />
}
