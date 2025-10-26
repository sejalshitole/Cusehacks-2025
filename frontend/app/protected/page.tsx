"use client";

import { useEffect } from "react";
import { toast } from "sonner";
import CalendarWrapper from "@/components/calendar-wrapper";

export default function ProtectedPage() {


  return (
    <div className="flex-1 w-full flex flex-col gap-12">
      <div className="max-w-4xl">
        <CalendarWrapper />
      </div>
    </div>
  );
}

