import type { SessionMessage } from "../api";
import { formatDateTime } from "./utils";

type SessionMessagesProps = {
  messages: SessionMessage[];
  draft: string;
  loading: boolean;
  sending: boolean;
  error: string;
  notice: string;
  onDraftChange: (value: string) => void;
  onSend: () => void;
};

export function SessionMessagesPanel({ messages, draft, loading, sending, error, notice, onDraftChange, onSend }: SessionMessagesProps) {
  return <div className="sessionMessages projectLink">
    <div className="annotationHeader"><h4>消息历史</h4><span className="chip">{messages.length}</span></div>
    {loading ? <p className="muted" role="status" aria-live="polite">正在加载消息历史…</p> : messages.length ? <div role="log" aria-label="Session 消息历史" aria-live="polite">
      {messages.map((message) => <div className="projectLink" key={message.id}>
        <b>{message.role === "user" ? "你" : message.role}</b>
        <p>{message.content}</p>
        <small><time dateTime={message.created_at}>{formatDateTime(message.created_at)}</time></small>
      </div>)}
    </div> : <p className="muted">暂无消息历史。发送第一条消息开始记录。</p>}
    {error && <p className="errorBanner" role="alert">{error}</p>}
    {notice && <p className="notice" role="status">{notice}</p>}
    <div className="formStack">
      <textarea aria-label="发送 Session 消息" value={draft} onChange={(event) => onDraftChange(event.target.value)} placeholder="记录问题、决定或下一步…" rows={3} />
      <button type="button" className="primaryBtn" disabled={sending || !draft.trim()} onClick={onSend}>{sending ? "保存中…" : "发送消息"}</button>
    </div>
  </div>;
}
