// Shared chat-thread helpers used by both ChatBox and Sidebar.
// Each chat is one localStorage key: `dogbuddy_chat_<thread_id>` →
// JSON-serialised array of ChatMessage objects.

export type ChatSummary = {
  threadId: string;
  title: string;
  msgCount: number;
  sortKey: number; // larger = newer
};

export function cacheKeyForThread(threadId: string): string {
  return `dogbuddy_chat_${threadId}`;
}

/**
 * Thread ID format (PRD line 353): staff_{staff_id}_{YYYY_MM_DD}, with an
 * optional `_s<timestamp>` suffix when "+ New chat" creates a fresh thread
 * within the same day.
 */
export function threadIdFor(staffId: number, sessionSuffix?: string): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const base = `staff_${staffId}_${yyyy}_${mm}_${dd}`;
  return sessionSuffix ? `${base}_s${sessionSuffix}` : base;
}

/**
 * List every chat thread for this user from localStorage, newest first.
 * `title` = the first user message's text (truncated). Used by the
 * Sidebar's chat history.
 */
export function listChats(userId: number): ChatSummary[] {
  if (typeof window === "undefined") return [];
  const prefix = `dogbuddy_chat_staff_${userId}_`;
  const results: ChatSummary[] = [];
  for (let i = 0; i < window.localStorage.length; i++) {
    const key = window.localStorage.key(i);
    if (!key || !key.startsWith(prefix)) continue;
    const threadId = key.slice("dogbuddy_chat_".length);
    let msgs: Array<{ role?: string; text?: string }> = [];
    try {
      msgs = JSON.parse(window.localStorage.getItem(key) || "[]");
    } catch {
      continue;
    }
    if (!Array.isArray(msgs)) continue;
    const firstUser = msgs.find((m) => m?.role === "user");
    const title = firstUser?.text?.trim().slice(0, 48) || "New chat";
    const sufMatch = threadId.match(/_s(\d+)$/);
    let sortKey: number;
    if (sufMatch) {
      sortKey = Number(sufMatch[1]);
    } else {
      const dateMatch = threadId.match(/_(\d{4})_(\d{2})_(\d{2})$/);
      sortKey = dateMatch
        ? Number(dateMatch[1] + dateMatch[2] + dateMatch[3])
        : 0;
    }
    results.push({ threadId, title, msgCount: msgs.length, sortKey });
  }
  results.sort((a, b) => b.sortKey - a.sortKey);
  return results;
}

/** Dispatched by ChatBox whenever a chat is created / updated / deleted
 * so the Sidebar can re-read its history list in the same browser tab.
 * (`storage` event only fires cross-tab.) */
export const CHATS_CHANGED_EVENT = "dogbuddy:chats-changed";

export function notifyChatsChanged(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(CHATS_CHANGED_EVENT));
}
