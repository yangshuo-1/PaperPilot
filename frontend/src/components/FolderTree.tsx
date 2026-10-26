import type { ReactNode } from "react";
import type { Folder } from "../api";
import { cls } from "./utils";

type Props = {
  folders: Folder[];
  selected: string | null;
  countFor: (id: string) => number;
  editing: string | null;
  setEditing: (id: string | null) => void;
  onSelect: (id: string) => void;
  onRename: (folder: Folder, name: string) => void;
  onDelete: (folder: Folder) => void;
  onSubfolder: (id: string) => void;
};

export function FolderTree({ folders, selected, countFor, editing, setEditing, onSelect, onRename, onDelete, onSubfolder }: Props) {
  function renderTree(parentId: string | null): ReactNode {
    const children = folders.filter((folder) => folder.parent_id === parentId);
    if (children.length === 0 && parentId === null) {
      return (
        <ul className="folderTree">
          <li>
            <div className="folderEmpty">尚未创建文件夹</div>
          </li>
        </ul>
      );
    }
    return (
      <ul className="folderTree">
        {children.map((folder) => (
          <li key={folder.id}>
            <div className={cls("folderRow", selected === folder.id && "selected")}>
              {editing === folder.id ? (
                <input
                  defaultValue={folder.name}
                  autoFocus
                  aria-label={`重命名文件夹：${folder.name}`}
                  autoComplete="off"
                  onBlur={(event) => onRename(folder, event.target.value || folder.name)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") onRename(folder, (event.target as HTMLInputElement).value || folder.name);
                    if (event.key === "Escape") setEditing(null);
                  }}
                />
              ) : (
                <button type="button" className="folderItem" onClick={() => onSelect(folder.id)}>
                  <span className="name">{folder.name}</span>
                  <span className="count">{countFor(folder.id)}</span>
                </button>
              )}
              <div className="folderHints">
                <button type="button" title="重命名" aria-label={`重命名文件夹：${folder.name}`} onClick={() => setEditing(folder.id)}>
                  <svg className="folderHintIcon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M11.3 2.7l2 2L5.6 12.4l-2.7.7.7-2.7z" /></svg>
                </button>
                <button type="button" title="新建子文件夹" aria-label={`在 ${folder.name} 下新建子文件夹`} onClick={() => onSubfolder(folder.id)}>
                  <svg className="folderHintIcon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true"><path d="M8 3v10M3 8h10" /></svg>
                </button>
                <button type="button" title="删除" aria-label={`删除文件夹：${folder.name}`} onClick={() => onDelete(folder)}>
                  <svg className="folderHintIcon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3.5 4.5h9M6.5 4.5V3h3v1.5M5 4.5l.6 8h4.8l.6-8M6.8 6.8v3.6M9.2 6.8v3.6" /></svg>
                </button>
              </div>
            </div>
            {renderTree(folder.id)}
          </li>
        ))}
      </ul>
    );
  }
  return <div>{renderTree(null)}</div>;
}
