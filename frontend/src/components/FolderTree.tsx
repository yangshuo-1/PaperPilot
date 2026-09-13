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
  function renderTree(parentId: string | null): React.ReactNode {
    const children = folders.filter((folder) => folder.parent_id === parentId);
    if (children.length === 0 && parentId === null) return <ul className="folderTree"><li><div className="folderEmpty">尚未创建文件夹</div></li></ul>;
    return <ul className="folderTree">{children.map((folder) => <li key={folder.id}>
      <div className={cls("folderRow", selected === folder.id && "selected")}>
        {editing === folder.id ? <input defaultValue={folder.name} autoFocus onBlur={(event) => onRename(folder, event.target.value || folder.name)} onKeyDown={(event) => { if (event.key === "Enter") onRename(folder, (event.target as HTMLInputElement).value || folder.name); }} /> : <button type="button" className="folderItem" onClick={() => onSelect(folder.id)}><span className="name">{folder.name}</span><span className="count">{countFor(folder.id)}</span></button>}
        <div className="folderHints"><button type="button" title="重命名" onClick={() => setEditing(folder.id)}>✎</button><button type="button" title="新建子文件夹" onClick={() => onSubfolder(folder.id)}>＋</button><button type="button" title="删除" onClick={() => onDelete(folder)}>🗑</button></div>
      </div>
      {renderTree(folder.id)}
    </li>)}</ul>;
  }
  return <div>{renderTree(null)}</div>;
}
