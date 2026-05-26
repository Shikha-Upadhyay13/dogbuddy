"use client";

import AuthGate from "@/components/AuthGate";
import BottomNav from "@/components/BottomNav";
import ChatBox from "@/components/ChatBox";
import TopNav from "@/components/TopNav";

export default function ChatPage() {
  return (
    <AuthGate>
      <TopNav />
      <ChatBox />
      <BottomNav />
    </AuthGate>
  );
}
