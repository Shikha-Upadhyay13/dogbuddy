"use client";

import AuthGate from "@/components/AuthGate";
import BottomNav from "@/components/BottomNav";
import ChatBox from "@/components/ChatBox";

export default function ChatPage() {
  return (
    <AuthGate>
      <ChatBox />
      <BottomNav />
    </AuthGate>
  );
}
