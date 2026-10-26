import { useState } from "react";
import type { Paper, ReadStatus } from "../api";
import { useClickOutside } from "../hooks/useClickOutside";
import { usePaperMutations } from "../hooks/usePaperMutations";
import { cls, statusLabel, statusTone } from "./utils";

const READ_LABELS: Record<ReadStatus, string> = { unread: "未读", reading: "阅读中", read: "已读" };

export function StatusBadge({ status }: { status: string }) {
  return <span className={`statusBadge ${statusTone(status)}`}>{statusLabel(status)}</span>;
}

function Star({ on, label, onClick }: { on: boolean; label: string; onClick: (event: React.MouseEvent) => void }) {
  return (
    <button
      type="button"
      className={cls("star", on && "on")}
      title={on ? "取消星标" : "星标"}
      aria-label={label}
      aria-pressed={on}
      onClick={(event) => {
        event.stopPropagation();
        onClick(event);
      }}
    >
      <span aria-hidden="true">{on ? "★" : "☆"}</span>
    </button>
  );
}

export function StarToggle({ paper, onChange }: { paper: Paper; onChange: (paper: Paper) => void }) {
  const { toggleStar } = usePaperMutations(paper, onChange);
  return <Star on={paper.starred} label={paper.starred ? `取消星标：${paper.title}` : `星标：${paper.title}`} onClick={() => void toggleStar()} />;
}

export function StatusControl({ paper, onChange }: { paper: Paper; onChange: (paper: Paper) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useClickOutside(() => setOpen(false));
  const { setReadStatus } = usePaperMutations(paper, onChange);
  const statuses: ReadStatus[] = ["unread", "reading", "read"];
  return (
    <div className="popover-wrap" ref={ref}>
      <button
        type="button"
        className={cls("statusBadge", paper.read_status)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={`阅读状态：${READ_LABELS[paper.read_status]}，点击更改`}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="statusDot" aria-hidden="true" />
        {READ_LABELS[paper.read_status]}
      </button>
      {open && (
        <div className="popover right">
          {statuses.map((status) => (
            <button
              type="button"
              key={status}
              className={cls("statusOption", paper.read_status === status && "selected")}
              onClick={async () => {
                await setReadStatus(status);
                setOpen(false);
              }}
            >
              <span className="statusDot" aria-hidden="true" />
              {READ_LABELS[status]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function TagEditor({ paper, allTags, onChange }: { paper: Paper; allTags: string[]; onChange: (paper: Paper) => void }) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState("");
  const ref = useClickOutside(() => setOpen(false));
  const { addTag } = usePaperMutations(paper, onChange);
  async function add(tag: string) {
    await addTag(tag);
    setPending("");
    setOpen(false);
  }
  return (
    <div className="popover-wrap" ref={ref}>
      <button type="button" className="addTagBtn" aria-haspopup="true" aria-expanded={open} aria-label="添加标签" onClick={() => setOpen((value) => !value)}>
        + 标签
      </button>
      {open && (
        <div className="popover">
          <h4>添加标签</h4>
          {allTags
            .filter((tag) => !paper.tags.includes(tag))
            .map((tag) => (
              <button type="button" key={tag} className="tagOption" onClick={() => void add(tag)}>
                <span>{tag}</span>
              </button>
            ))}
          <input
            type="text"
            aria-label="新标签名称"
            placeholder="新标签…"
            autoComplete="off"
            spellCheck={false}
            value={pending}
            onChange={(event) => setPending(event.target.value)}
            onKeyDown={(event) => {
              const value = pending.trim();
              if (event.key === "Enter" && value && !paper.tags.includes(value)) void add(value);
            }}
          />
        </div>
      )}
    </div>
  );
}
