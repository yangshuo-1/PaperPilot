import { AppShell } from "../components/AppShell";
import { DiscoveryPanel } from "../components/DiscoveryPanel";
import { FolderTree } from "../components/FolderTree";
import { LibraryTable } from "../components/LibraryTable";
import { QuickViewModal } from "../components/QuickViewModal";
import { cls } from "../components/utils";
import { useLibrary } from "../hooks/useLibrary";

const VIEWS = [
  ["all", "全部论文"],
  ["reading", "阅读中"],
  ["starred", "已星标"],
  ["recent", "最近阅读"],
] as const;

export default function LibraryPage() {
  const library = useLibrary();
  const {
    query, setQuery, selectedTags, setSelectedTags, tagCounts, importValue, setImportValue, error, importing,
    view, setView, selectedFolder, setSelectedFolder, folders, layout, setLayout, sortDir, setSortDir,
    selected, setSelected, newFolder, setNewFolder, folderEditing, setFolderEditing, quickviewId, setQuickviewId,
    discovery, discoveryErrors, discoveryDays, setDiscoveryDays, discovering, discoveryOpen, setDiscoveryOpen,
    discoveryReview, reviewingDiscovery, processingDiscovery, refresh, importPaper, discoverPapers, importDiscovered,
    reviewDiscovered, processMustRead, downloadDiscoveryReview, visible, viewCounts, folderCount, toggleSelect,
    toggleSelectAll, batchSet, replacePaper, createFolder, renameFolder, deleteFolder,
  } = library;

  return (
    <AppShell>
      <div className="library">
        <aside className="librarySidebar">
          <div className="sideSection">
            <div className="sideSectionHeader">视图</div>
            <ul className="viewList">
              {VIEWS.map(([key, label]) => (
                <li key={key}>
                  <button
                    type="button"
                    className={cls("viewItem", view === key && selectedFolder == null && "active")}
                    aria-pressed={view === key && selectedFolder == null}
                    onClick={() => {
                      setView(key);
                      setSelectedFolder(null);
                    }}
                  >
                    <span>{label}</span>
                    <span className="count">{viewCounts[key]}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <div className="sideSection">
            <div className="sideSectionHeader">文件夹</div>
            <FolderTree
              folders={folders}
              selected={selectedFolder}
              countFor={folderCount}
              onSelect={(id) => {
                setSelectedFolder(id);
                setView("all");
              }}
              onRename={renameFolder}
              onDelete={deleteFolder}
              editing={folderEditing}
              setEditing={setFolderEditing}
              onSubfolder={setSelectedFolder}
            />
            <div className="newFolderRow">
              <input
                value={newFolder}
                aria-label={selectedFolder ? "新建子文件夹名称" : "新文件夹名称"}
                placeholder={selectedFolder ? "新建子文件夹…" : "新文件夹…"}
                autoComplete="off"
                onChange={(event) => setNewFolder(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void createFolder();
                }}
              />
              <button type="button" className="quietBtn" aria-label="新建文件夹" onClick={() => void createFolder()}>
                +
              </button>
            </div>
          </div>
          <div className="sideSection">
            <div className="sideSectionHeader">展示</div>
            <div className="layoutSwitch" role="group" aria-label="列表展示方式">
              <button type="button" className={cls(layout === "table" && "active")} aria-pressed={layout === "table"} onClick={() => setLayout("table")}>
                表格
              </button>
              <button type="button" className={cls(layout === "card" && "active")} aria-pressed={layout === "card"} onClick={() => setLayout("card")}>
                卡片
              </button>
            </div>
          </div>
        </aside>
        <main className="libraryMain">
          <div className="pageHeader">
            <div>
              <h1>论文库</h1>
              <div className="sub">{visible.length} 篇论文</div>
            </div>
            <div className="headerActions">
              <button type="button" className="refreshBtn" onClick={() => void refresh()}>
                刷新索引
              </button>
            </div>
          </div>
          {error && <div className="errorBanner" role="alert">{error}</div>}
          <div className="toolbar">
            <label className="searchBox">
              <span className="searchIcon" aria-hidden="true">
                <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
                  <circle cx="7" cy="7" r="4.4" />
                  <path d="M10.4 10.4 14 14" />
                </svg>
              </span>
              <span className="srOnly">搜索论文</span>
              <input
                type="search"
                name="paper-search"
                placeholder="搜索标题、arXiv、仓库、标签…"
                autoComplete="off"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <form
              className="importBar"
              onSubmit={(event) => {
                event.preventDefault();
                void importPaper();
              }}
            >
              <input
                value={importValue}
                aria-label="arXiv ID 或 URL"
                name="arxiv-id"
                placeholder="arXiv ID 或 URL，如 2511.21631…"
                autoComplete="off"
                spellCheck={false}
                onChange={(event) => setImportValue(event.target.value)}
              />
              <button type="submit" className="primaryBtn" disabled={importing}>
                {importing ? "导入中…" : "导入"}
              </button>
            </form>
            <div className="importBar discoveryBar">
              <select value={discoveryDays} aria-label="发现时间范围" onChange={(event) => setDiscoveryDays(Number(event.target.value))}>
                <option value={1}>今日</option>
                <option value={3}>近 3 天</option>
                <option value={7}>近 7 天</option>
              </select>
              <button type="button" className="quietBtn" onClick={() => void discoverPapers()} disabled={discovering}>
                {discovering ? "抓取中…" : "发现论文"}
              </button>
            </div>
          </div>
          {discoveryOpen && (
            <DiscoveryPanel
              candidates={discovery}
              errors={discoveryErrors}
              review={discoveryReview}
              reviewing={reviewingDiscovery}
              processing={processingDiscovery}
              onReview={() => void reviewDiscovered()}
              onClose={() => setDiscoveryOpen(false)}
              onImport={(candidate) => void importDiscovered(candidate)}
              onProcess={() => void processMustRead()}
              onDownload={() => void downloadDiscoveryReview()}
            />
          )}
          <div className="tagPanel">
            <span className="tagPanelLabel">标签过滤</span>
            {selectedTags.length > 0 ? (
              <span className="selectedTags">
                {selectedTags.map((tag) => (
                  <span className="dismissChip" key={tag}>
                    {tag}
                    <button type="button" aria-label={`移除标签 ${tag}`} onClick={() => setSelectedTags(selectedTags.filter((item) => item !== tag))}>
                      <span aria-hidden="true">×</span>
                    </button>
                  </span>
                ))}
              </span>
            ) : (
              <span className="muted" style={{ fontSize: 12 }}>
                未选择
              </span>
            )}
            <span style={{ width: 8, display: "inline-block" }} />
            {Object.entries(tagCounts).map(([tag, count]) => (
              <button
                type="button"
                key={tag}
                className={cls("tagPill", selectedTags.includes(tag) && "active")}
                aria-pressed={selectedTags.includes(tag)}
                onClick={() =>
                  setSelectedTags(selectedTags.includes(tag) ? selectedTags.filter((item) => item !== tag) : [...selectedTags, tag])
                }
              >
                {tag} <span className="c">{count}</span>
              </button>
            ))}
          </div>
          {selected.size > 0 && (
            <div className="batchBar">
              <span className="label">{selected.size} 已选</span>
              <span className="sep" />
              <button type="button" className="quietBtn" onClick={() => void batchSet({ starred: true })}>★ 星标</button>
              <button type="button" className="quietBtn" onClick={() => void batchSet({ starred: false })}>☆ 取消星标</button>
              <span className="sep" />
              <button type="button" className="quietBtn" onClick={() => void batchSet({ read_status: "reading" })}>标记阅读中</button>
              <button type="button" className="quietBtn" onClick={() => void batchSet({ read_status: "read" })}>标记已读</button>
              <button type="button" className="quietBtn" onClick={() => void batchSet({ read_status: "unread" })}>标记未读</button>
              <span className="sep" />
              <select
                value=""
                aria-label="批量移动到文件夹"
                onChange={(event) => {
                  if (event.target.value) void batchSet({ folder_id: event.target.value });
                }}
              >
                <option value="">移动到文件夹…</option>
                {folders.map((folder) => (
                  <option key={folder.id} value={folder.id}>{folder.name}</option>
                ))}
              </select>
              <button type="button" className="quietBtn" onClick={() => void batchSet({ folder_id: null })}>移出文件夹</button>
              <span className="sep" />
              <button type="button" className="quietBtn" onClick={() => setSelected(new Set())}>清除选择</button>
            </div>
          )}
          <LibraryTable
            papers={visible}
            layout={layout}
            selected={selected}
            folders={folders}
            tagCounts={tagCounts}
            sortDir={sortDir}
            onToggleSelect={toggleSelect}
            onToggleSelectAll={toggleSelectAll}
            onSort={() => setSortDir(sortDir === "desc" ? "asc" : "desc")}
            onPaperChange={replacePaper}
            onQuickview={setQuickviewId}
          />
          {quickviewId && <QuickViewModal paperId={quickviewId} onClose={() => setQuickviewId(null)} />}
        </main>
      </div>
    </AppShell>
  );
}
