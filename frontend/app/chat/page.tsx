"use client";

import AuthGate from "@/components/AuthGate";
import BottomNav from "@/components/BottomNav";
import ChatBox from "@/components/ChatBox";
import Sidebar from "@/components/Sidebar";

export default function ChatPage() {
  return (
    <AuthGate>
      <Sidebar />
      <ChatBox />
      <BottomNav />
    </AuthGate>
  );
}
