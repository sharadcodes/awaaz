import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  controlJob,
  createCollection as apiCreateCollection,
  createJob,
  createTextDocument,
  deleteCollection as apiDeleteCollection,
  deleteDocument as apiDeleteDocument,
  getCoverUrl,
  listBackends,
  listCollections,
  listDocuments,
  listJobs,
  updateCollection as apiUpdateCollection,
  updateDocument,
  uploadDocument,
} from './api/client';
import { GenerationForm } from './components/GenerationForm';
import { JobCard } from './components/JobCard';
import { Modal } from './components/Modal';
import { NewDocument } from './components/NewDocument';
import { SettingsModal } from './components/SettingsModal';
import type { Backend, Collection, Document, Job, JobAction, JobRequest } from './types';

function readableError(error: unknown): string {
  return error instanceof Error ? error.message : 'Unexpected error';
}

function formatDescription(text: string): string {
  const trimmed = text.slice(0, 200).replace(/\s+/g, ' ').trim();
  return trimmed.length === 200 ? `${trimmed}…` : trimmed;
}

type View = 'library' | 'explore';

interface Filter {
  type: 'collection' | 'author' | 'series' | 'tag';
  value: string;
  collectionId?: string;
}

function aggregate(documents: Document[], key: 'author' | 'series' | 'tags'): [string, number][] {
  const counts = new Map<string, number>();
  for (const document of documents) {
    if (key === 'tags') {
      for (const tag of (document.tags ?? '').split(',')) {
        const trimmed = tag.trim();
        if (trimmed) {
          counts.set(trimmed, (counts.get(trimmed) ?? 0) + 1);
        }
      }
    } else {
      const value = document[key];
      if (value) {
        counts.set(value, (counts.get(value) ?? 0) + 1);
      }
    }
  }
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function latestJobByDocument(jobs: Job[]): Map<string, Job> {
  const sorted = [...jobs].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  const map = new Map<string, Job>();
  for (const job of sorted) {
    if (!map.has(job.document_id)) {
      map.set(job.document_id, job);
    }
  }
  return map;
}

function filterDocuments(documents: Document[], filter: Filter | null, query: string): Document[] {
  let result = documents;
  if (filter) {
    switch (filter.type) {
      case 'collection':
        result = result.filter((document) => document.collection_names.includes(filter.value));
        break;
      case 'author':
        result = result.filter((document) => document.author === filter.value);
        break;
      case 'series':
        result = result.filter((document) => document.series === filter.value);
        break;
      case 'tag':
        result = result.filter((document) =>
          (document.tags ?? '')
            .split(',')
            .map((tag) => tag.trim())
            .includes(filter.value),
        );
        break;
    }
  }
  const trimmed = query.trim().toLowerCase();
  if (trimmed) {
    result = result.filter(
      (document) =>
        document.title.toLowerCase().includes(trimmed) ||
        (document.author ?? '').toLowerCase().includes(trimmed) ||
        (document.series ?? '').toLowerCase().includes(trimmed) ||
        (document.tags ?? '').toLowerCase().includes(trimmed),
    );
  }
  return result;
}

export default function App() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [backends, setBackends] = useState<Backend[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [view, setView] = useState<View>('library');
  const [filter, setFilter] = useState<Filter | null>(null);
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null);
  const [chipCategory, setChipCategory] = useState<'all' | 'collections' | 'authors' | 'series' | 'tags'>('all');
  const [chipFilter, setChipFilter] = useState('');
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [managingCollectionId, setManagingCollectionId] = useState<string | null>(null);
  const [creatingCollection, setCreatingCollection] = useState(false);
  const [renamingCollection, setRenamingCollection] = useState<{ id: string; name: string } | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [voicePreferences, setVoicePreferences] = useState<Record<string, string>>(() => {
    try {
      const saved = window.localStorage.getItem('awaaz_voice_preferences');
      return saved ? (JSON.parse(saved) as Record<string, string>) : {};
    } catch {
      return {};
    }
  });

  const selected = useMemo(
    () => documents.find((document) => document.id === selectedDocId) ?? null,
    [documents, selectedDocId],
  );

  const latestJobs = useMemo(() => latestJobByDocument(jobs), [jobs]);
  const authors = useMemo(() => aggregate(documents, 'author'), [documents]);
  const series = useMemo(() => aggregate(documents, 'series'), [documents]);
  const tags = useMemo(() => aggregate(documents, 'tags'), [documents]);

  const filteredDocuments = useMemo(
    () => filterDocuments(documents, filter, searchQuery),
    [documents, filter, searchQuery],
  );

  const activeJobs = useMemo(
    () => jobs.filter((job) => !['completed', 'cancelled'].includes(job.status)).length,
    [jobs],
  );

  const refreshJobs = useCallback(async () => {
    setJobs(await listJobs());
  }, []);

  const load = useCallback(async () => {
    try {
      const [nextDocuments, nextJobs, nextBackends, nextCollections] = await Promise.all([
        listDocuments(),
        listJobs(),
        listBackends(),
        listCollections(),
      ]);
      setDocuments(nextDocuments);
      setJobs(nextJobs);
      setBackends(nextBackends);
      setCollections(nextCollections);
      setError(null);
    } catch (loadError) {
      setError(readableError(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(() => void refreshJobs().catch(() => undefined), 2000);
    return () => window.clearInterval(timer);
  }, [refreshJobs]);

  useEffect(() => {
    setDraft(selected?.text ?? '');
  }, [selected]);

  useEffect(() => {
    if (!filter) {
      setChipCategory('all');
      return;
    }
    switch (filter.type) {
      case 'collection':
        setChipCategory('collections');
        break;
      case 'author':
        setChipCategory('authors');
        break;
      case 'series':
        setChipCategory('series');
        break;
      case 'tag':
        setChipCategory('tags');
        break;
    }
  }, [filter]);

  async function run(operation: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await operation();
    } catch (operationError) {
      setError(readableError(operationError));
    } finally {
      setBusy(false);
    }
  }

  async function addDocument(operation: () => Promise<Document>) {
    await run(async () => {
      const document = await operation();
      setDocuments((current) => [document, ...current]);
      setSelectedDocId(document.id);
      setShowUpload(false);
    });
  }

  const handleCreateText = (title: string, text: string) =>
    void addDocument(() => createTextDocument(title, text));

  const handleUpload = (file: File, title?: string) =>
    void addDocument(() => uploadDocument(file, title));

  const handleSave = () => {
    if (!selected) return;
    void run(async () => {
      const updated = await updateDocument(selected, draft);
      setDocuments((current) =>
        current.map((document) => (document.id === updated.id ? updated : document)),
      );
    });
  };

  const handleCreateJob = (settings: JobRequest) => {
    if (!selected) return;
    void run(async () => {
      const job = await createJob(selected.id, settings);
      setJobs((current) => [job, ...current]);
    });
  };

  const handleJobAction = (jobId: string, action: JobAction) => {
    void run(async () => {
      const updated = await controlJob(jobId, action);
      setJobs((current) => current.map((jobItem) => (jobItem.id === updated.id ? updated : jobItem)));
    });
  };

  const handleCollectionCreate = (name: string) => {
    void run(async () => {
      const collection = await apiCreateCollection(name);
      setCollections((current) => [collection, ...current]);
      setCreatingCollection(false);
    });
  };

  const handleCollectionRename = (id: string, name: string) => {
    void run(async () => {
      const collection = collections.find((item) => item.id === id);
      if (!collection || name === collection.name) return;
      const memberIds = documents
        .filter((document) => document.collection_names.includes(collection.name))
        .map((document) => document.id);
      const updated = await apiUpdateCollection(id, { name, document_ids: memberIds });
      setCollections((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setDocuments(await listDocuments());
    });
  };

  const handleCollectionDelete = (id: string) => {
    void run(async () => {
      await apiDeleteCollection(id);
      setCollections((current) => current.filter((item) => item.id !== id));
      if (selectedCollectionId === id) {
        setSelectedCollectionId(null);
        setFilter(null);
      }
    });
  };

  const handleDocumentDelete = (documentId: string) => {
    void run(async () => {
      await apiDeleteDocument(documentId);
      setDocuments((current) => current.filter((item) => item.id !== documentId));
      setJobs((current) => current.filter((item) => item.document_id !== documentId));
      setSelectedDocId(null);
    });
  };

  const handleSelectCollection = (id: string) => {
    const collection = collections.find((item) => item.id === id);
    if (!collection) return;
    setSelectedCollectionId(id);
    setFilter({ type: 'collection', value: collection.name, collectionId: collection.id });
    setView('library');
    setSidebarOpen(false);
  };

  const handleClearFilter = () => {
    setFilter(null);
    setSelectedCollectionId(null);
    setSearchQuery('');
    setChipFilter('');
    setChipCategory('all');
  };

  const handleChipCategory = (category: typeof chipCategory) => {
    setChipCategory(category);
    setChipFilter('');
    if (category === 'all') {
      setFilter(null);
      setSelectedCollectionId(null);
    }
  };

  const categoryValues = useMemo<[string, number][]>(() => {
    switch (chipCategory) {
      case 'collections':
        return collections.map((collection) => [collection.name, collection.document_count]);
      case 'authors':
        return authors;
      case 'series':
        return series;
      case 'tags':
        return tags;
      default:
        return [];
    }
  }, [chipCategory, collections, authors, series, tags]);

  const filteredCategoryValues = useMemo(() => {
    const trimmed = chipFilter.trim().toLowerCase();
    if (!trimmed) return categoryValues;
    return categoryValues.filter(([value]) => value.toLowerCase().includes(trimmed));
  }, [categoryValues, chipFilter]);

  const handleCollectionSave = (collectionId: string, documentIds: string[]) => {
    void run(async () => {
      const collection = collections.find((item) => item.id === collectionId);
      if (!collection) return;
      const updated = await apiUpdateCollection(collectionId, {
        name: collection.name,
        document_ids: documentIds,
      });
      setCollections((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setDocuments(await listDocuments());
      setManagingCollectionId(null);
    });
  };

  const handleSelectValueChip = (value: string) => {
    let nextFilter: Filter;
    let nextCollectionId: string | null = null;
    switch (chipCategory) {
      case 'collections': {
        const collection = collections.find((item) => item.name === value);
        nextCollectionId = collection?.id ?? null;
        nextFilter = { type: 'collection', value, collectionId: nextCollectionId ?? undefined };
        break;
      }
      case 'authors':
        nextFilter = { type: 'author', value };
        break;
      case 'series':
        nextFilter = { type: 'series', value };
        break;
      case 'tags':
        nextFilter = { type: 'tag', value };
        break;
      default:
        return;
    }
    setFilter(nextFilter);
    setSelectedCollectionId(nextCollectionId);
    setView('library');
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <button
            className="mobile-menu-button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <a className="brand" href="#top" aria-label="Awaaz home">
            <img src="/logo.png" alt="Awaaz Logo" className="brand-logo" />
          </a>
        </div>

        <div className="topbar-search">
          <input
            type="search"
            placeholder="Search your library"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            aria-label="Search library"
          />
        </div>

        <div className="topbar-right">
          <div className="system-status">
            <span className={error ? 'signal signal-error' : 'signal'} />
            <span className="status-label">{error ? 'Needs attention' : 'System ready'}</span>
            {activeJobs > 0 && <span className="status-pill">{activeJobs} active</span>}
          </div>
          <a
            href="https://github.com/sharadcodes/awaaz"
            target="_blank"
            rel="noopener noreferrer"
            className="topbar-icon-button"
            aria-label="Star Awaaz on GitHub"
            title="Star us on GitHub"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.579.688.481C19.137 20.162 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
            </svg>
          </a>
          <button
            className="topbar-icon-button"
            onClick={() => setSettingsOpen(true)}
            aria-label="Settings"
            title="Settings"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.1.608 2.296.07 2.572-1.065z"
              />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>
      </header>

      <div className="app-body">
        {sidebarOpen && (
          <div
            className="sidebar-backdrop"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
        <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
          <nav className="sidebar-nav">
            <button
              className="upload-button primary-button"
              onClick={() => setShowUpload(true)}
            >
              <svg
                className="upload-icon-plus"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              <span>Upload content</span>
            </button>

            <div className="nav-section">
              <span className="nav-section-title">Library</span>
              <button
                className={`nav-item ${view === 'library' && !filter ? 'active' : ''}`}
                onClick={() => {
                  setView('library');
                  setFilter(null);
                  setSelectedCollectionId(null);
                  setSidebarOpen(false);
                }}
              >
                <span className="nav-item-label">
                  <svg
                    className="nav-item-icon"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                    />
                  </svg>
                  <span>Library</span>
                </span>
                <span className="count">{documents.length}</span>
              </button>
            </div>

            <div className="nav-section collections-section">
              <div className="section-header">
                <span className="nav-section-title">Collections</span>
                <button
                  className="icon-button"
                  aria-label="Create collection"
                  onClick={() => setCreatingCollection(true)}
                >
                  +
                </button>
              </div>
              <div className="collection-list">
                {collections.map((collection) => {
                  const isSelected = selectedCollectionId === collection.id;
                  return (
                    <div key={collection.id} className={`collection-item ${isSelected ? 'active' : ''}`}>
                      <div
                        className="collection-row"
                        onClick={() => handleSelectCollection(collection.id)}
                      >
                        {renamingCollection?.id === collection.id ? (
                          <input
                            className="collection-rename-input"
                            value={renamingCollection.name}
                            onChange={(event) =>
                              setRenamingCollection({
                                id: collection.id,
                                name: event.target.value,
                              })
                            }
                            onBlur={() => {
                              const trimmed = renamingCollection.name.trim();
                              if (trimmed && trimmed !== collection.name) {
                                handleCollectionRename(collection.id, trimmed);
                              }
                              setRenamingCollection(null);
                            }}
                            onKeyDown={(event) => {
                              if (event.key === 'Enter') {
                                (event.currentTarget as HTMLInputElement).blur();
                              } else if (event.key === 'Escape') {
                                setRenamingCollection(null);
                              }
                            }}
                            onClick={(event) => event.stopPropagation()}
                            autoFocus
                          />
                        ) : (
                          <span
                            className="collection-name"
                            onDoubleClick={(event) => {
                              event.stopPropagation();
                              setRenamingCollection({ id: collection.id, name: collection.name });
                            }}
                          >
                            {collection.name}
                          </span>
                        )}
                        <span className="count">{collection.document_count}</span>
                        <button
                          className="collection-manage"
                          aria-label="Manage books in collection"
                          title="Manage books"
                          onClick={(event) => {
                            event.stopPropagation();
                            setManagingCollectionId(collection.id);
                          }}
                        >
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                          </svg>
                        </button>
                        <button
                          className="collection-delete"
                          aria-label="Delete collection"
                          onClick={(event) => {
                            event.stopPropagation();
                            if (window.confirm(`Delete collection "${collection.name}"?`)) {
                              handleCollectionDelete(collection.id);
                            }
                          }}
                        >
                          ×
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </nav>
          <div className="sidebar-footer">
            <span>
              Made with ♥ by{' '}
              <a
                href="https://github.com/sharadcodes"
                target="_blank"
                rel="noopener noreferrer"
              >
                Sharad Raj Singh Maurya
              </a>
            </span>
          </div>
        </aside>

        <main className="main">
          {error && (
            <div className="error-banner" role="alert">
              <strong>Something stopped.</strong> {error}
              <button className="text-button" onClick={() => void load()}>
                Retry
              </button>
            </div>
          )}

          <div className="library-header">
            <div>
              <h1>Library</h1>
              <p className="subtitle">
                {filteredDocuments.length} {filteredDocuments.length === 1 ? 'title' : 'titles'}
              </p>
            </div>
            <button className="primary-button add-button" onClick={() => setShowUpload(true)}>
              + Add book
            </button>
          </div>

          {(filter || searchQuery) && (
            <div className="active-filter-bar">
              {searchQuery && (
                <span className="active-filter-label">
                  Search: <strong>&ldquo;{searchQuery}&rdquo;</strong>
                </span>
              )}
              {filter && (
                <span className="active-filter-label">
                  Showing {filter.type}: <strong>{filter.value}</strong>
                </span>
              )}
              <button className="text-button" onClick={handleClearFilter}>
                Clear Filter
              </button>
            </div>
          )}

          <div className="filter-bar">
            <div className="filter-bar-row">
              <div className="filter-chips">
                <button
                  className={chipCategory === 'all' ? 'active' : ''}
                  onClick={() => handleChipCategory('all')}
                >
                  All titles
                </button>
                <button
                  className={chipCategory === 'collections' ? 'active' : ''}
                  onClick={() => handleChipCategory('collections')}
                >
                  Collections
                </button>
                <button
                  className={chipCategory === 'authors' ? 'active' : ''}
                  onClick={() => handleChipCategory('authors')}
                >
                  Authors
                </button>
                <button
                  className={chipCategory === 'series' ? 'active' : ''}
                  onClick={() => handleChipCategory('series')}
                >
                  Series
                </button>
                <button
                  className={chipCategory === 'tags' ? 'active' : ''}
                  onClick={() => handleChipCategory('tags')}
                >
                  Tags
                </button>
              </div>
              {chipCategory !== 'all' && (
                <div className="filter-input-wrap">
                  <input
                    className="filter-input"
                    type="text"
                  placeholder={`Filter ${chipCategory}…`}
                  value={chipFilter}
                  onChange={(event) => setChipFilter(event.target.value)}
                />
              </div>
            )}
            </div>
            {chipCategory !== 'all' && (
              <div className="value-chips">
                {filteredCategoryValues.map(([value, count]) => {
                  const isActive =
                    filter?.value === value &&
                    ((chipCategory === 'collections' && filter.type === 'collection') ||
                      (chipCategory === 'authors' && filter.type === 'author') ||
                      (chipCategory === 'series' && filter.type === 'series') ||
                      (chipCategory === 'tags' && filter.type === 'tag'));
                  return (
                    <button
                      key={value}
                      className={isActive ? 'active' : ''}
                      onClick={() => handleSelectValueChip(value)}
                    >
                      {value}
                      <span>{count}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <section className="library-content">
            {loading ? (
              <p className="empty-state">Loading library…</p>
            ) : filteredDocuments.length === 0 ? (
              <div className="empty-state card">
                <p>
                  {searchQuery || filter
                    ? 'No titles match this filter.'
                    : 'Your imported books will appear here.'}
                </p>
              </div>
            ) : (
              <div className="library-list">
                {filteredDocuments.map((document) => (
                  <BookRow
                    key={document.id}
                    document={document}
                    job={latestJobs.get(document.id)}
                    onClick={() => setSelectedDocId(document.id)}
                  />
                ))}
              </div>
            )}
          </section>

          {selected && (
            <DetailModal
              document={selected}
              draft={draft}
              setDraft={setDraft}
              backends={backends}
              jobs={jobs}
              busy={busy}
              voicePreferences={voicePreferences}
              onSave={handleSave}
              onGenerate={handleCreateJob}
              onJobAction={handleJobAction}
              onDelete={handleDocumentDelete}
              onClose={() => setSelectedDocId(null)}
            />
          )}
        </main>
      </div>

      {showUpload && (
        <UploadModal
          busy={busy}
          onClose={() => setShowUpload(false)}
          onCreateText={handleCreateText}
          onUpload={handleUpload}
        />
      )}
      {settingsOpen && (
        <SettingsModal
          backends={backends}
          voicePreferences={voicePreferences}
          onClose={() => setSettingsOpen(false)}
          onSave={(next) => {
            setVoicePreferences(next);
            try {
              window.localStorage.setItem('awaaz_voice_preferences', JSON.stringify(next));
            } catch {
              // ignore storage errors
            }
          }}
        />
      )}
      {managingCollectionId && (
        <CollectionManageModal
          collection={collections.find((item) => item.id === managingCollectionId)!}
          documents={documents}
          busy={busy}
          onClose={() => setManagingCollectionId(null)}
          onSave={handleCollectionSave}
        />
      )}
      {creatingCollection && (
        <CollectionCreateModal
          busy={busy}
          onClose={() => setCreatingCollection(false)}
          onCreate={handleCollectionCreate}
        />
      )}
    </div>
  );
}

interface BookRowProps {
  document: Document;
  job?: Job;
  onClick: () => void;
}

function formatTimeRemaining(job: Job): string {
  // ETA is only meaningful while actively running. Show a status label
  // for other states instead of a misleading number.
  if (job.status === 'paused') return 'Paused';
  if (job.status === 'queued') return 'Queued';
  if (job.status === 'failed') return 'Failed';
  if (job.status === 'assembling') return 'Assembling…';
  if (job.status === 'completed') return 'Done';
  if (job.status === 'cancelled') return 'Cancelled';
  if (job.status !== 'running') return '—';

  const processed = job.progress.processed;
  const remaining = job.progress.total - processed;
  if (processed <= 0 || remaining <= 0) return '—';

  // Use the active processing window (created_at → updated_at) rather than
  // created_at → now. updated_at is bumped on every chunk state change, so
  // this excludes idle time after the last update (e.g. paused, stalled, or
  // time spent on the in-flight chunk that hasn't reported yet).
  const createdMs = new Date(job.created_at).getTime();
  const updatedMs = new Date(job.updated_at).getTime();
  const activeMs = Math.max(updatedMs - createdMs, 0);
  if (activeMs <= 0) return '—';

  // Rate is based on all processed chunks (completed + failed). Failed
  // chunks still consumed synthesis time, so they belong in the denominator.
  // remaining excludes failed chunks since they aren't retried in this job.
  const msPerChunk = activeMs / processed;
  const remainingMs = msPerChunk * remaining;
  const minutes = Math.round(remainingMs / 60000);

  if (minutes < 1) return '<1m left';
  if (minutes < 60) return `${minutes}m left`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m left`;
}

function BookRow({ document: doc, job, onClick }: BookRowProps) {
  const percent = Math.round(job?.progress.percent ?? 0);
  const description = doc.text ? formatDescription(doc.text) : '';
  const hasCover = doc.cover_path != null && doc.cover_path !== '';
  const initial = doc.title.trim().charAt(0).toUpperCase() || '?';

  return (
    <article className="library-item" onClick={onClick}>
      <div className="library-item-cover">
        {hasCover ? (
          <img
            src={getCoverUrl(doc.id)}
            alt=""
            loading="lazy"
            onError={(event) => {
              (event.currentTarget as HTMLImageElement).style.display = 'none';
            }}
          />
        ) : (
          <span className="library-item-cover-placeholder" aria-hidden="true">
            {initial}
          </span>
        )}
        <span className="cover-reflection" aria-hidden="true" />
      </div>
      <div className="library-item-body">
        {doc.author && <span className="library-item-author">{doc.author}</span>}
        <span className="library-item-title">{doc.title}</span>
        {description && <span className="library-item-desc">{description}</span>}
        {job && job.status !== 'cancelled' && (
          <div className="library-item-progress">
            <span className="progress-bar" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
              <span className="progress-bar-fill" style={{ width: `${percent}%` }} />
            </span>
            <span className="library-item-progress-pct">{percent}%</span>
            <span className="library-item-progress-time">{formatTimeRemaining(job)}</span>
          </div>
        )}
      </div>
    </article>
  );
}

interface DetailModalProps {
  document: Document;
  draft: string;
  setDraft: (value: string) => void;
  backends: Backend[];
  jobs: Job[];
  busy: boolean;
  voicePreferences: Record<string, string>;
  onSave: () => void;
  onGenerate: (settings: JobRequest) => void;
  onJobAction: (jobId: string, action: JobAction) => void;
  onDelete: (documentId: string) => void;
  onClose: () => void;
}

function DetailModal({
  document: doc,
  draft,
  setDraft,
  backends,
  jobs,
  busy,
  voicePreferences,
  onSave,
  onGenerate,
  onJobAction,
  onDelete,
  onClose,
}: DetailModalProps) {
  const documentJobs = useMemo(
    () =>
      jobs
        .filter((job) => job.document_id === doc.id)
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [jobs, doc.id],
  );

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal detail-modal" onClick={(event) => event.stopPropagation()}>
        <button className="modal-close detail-close" onClick={onClose} aria-label="Close">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <div className="detail-header">
          <div className="detail-cover">
            <img
              src={getCoverUrl(doc.id)}
              alt=""
              onError={(event) => {
                (event.currentTarget as HTMLImageElement).style.display = 'none';
              }}
            />
            <div className="cover-fallback" aria-hidden="true" />
          </div>
          <div className="detail-title">
            <h2>{doc.title}</h2>
            <p className="detail-author">
              {doc.author || 'Unknown author'}
              {doc.series && ` · ${doc.series}`}
            </p>
            <p className="detail-meta">
              {doc.word_count.toLocaleString()} words
              {doc.tags && ` · ${doc.tags}`}
              {doc.collection_names.length > 0 && ` · ${doc.collection_names.join(', ')}`}
            </p>
            <div className="detail-actions">
              <button
                className="primary-button"
                disabled={busy || draft === doc.text || !draft.trim()}
                onClick={onSave}
              >
                Save revision
              </button>
              <button
                className="text-button danger"
                disabled={busy}
                onClick={() => {
                  if (window.confirm(`Delete "${doc.title}"? This cannot be undone.`)) {
                    onDelete(doc.id);
                  }
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>

        <div className="detail-workspace">
          <div className="editor-area">
            <label className="editor-label">Manuscript text</label>
            <textarea
              aria-label="Manuscript editor"
              className="manuscript-editor"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              spellCheck="true"
            />
            <div className="editor-meta">
              <span>{draft.length.toLocaleString()} characters</span>
              <span>
                {draft.trim() ? draft.trim().split(/\s+/).length.toLocaleString() : 0} words
              </span>
              <span>
                {draft.split(/\n\s*\n/).filter(Boolean).length.toLocaleString()} paragraphs
              </span>
            </div>
          </div>

          <div className="generation-area">
            <h3>Voice settings</h3>
            <GenerationForm
              backends={backends}
              disabled={busy}
              onSubmit={onGenerate}
              text={draft}
              voicePreferences={voicePreferences}
            />
          </div>
        </div>

        {documentJobs.length > 0 && (
          <div className="detail-jobs">
            <h3>Jobs for this title</h3>
            <div className="job-grid">
              {documentJobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  title={doc.title}
                  onAction={onJobAction}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface UploadModalProps {
  busy: boolean;
  onClose: () => void;
  onCreateText: (title: string, text: string) => void;
  onUpload: (file: File, title?: string) => void;
}

function UploadModal({ busy, onClose, onCreateText, onUpload }: UploadModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal upload-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>Upload content</h2>
            <p className="modal-subtitle">Import an EPUB/TXT file or paste raw text.</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <NewDocument busy={busy} onCreate={onCreateText} onUpload={onUpload} />
      </div>
    </div>
  );
}

interface CollectionManageModalProps {
  collection: Collection;
  documents: Document[];
  busy: boolean;
  onClose: () => void;
  onSave: (collectionId: string, documentIds: string[]) => void;
}

interface CollectionCreateModalProps {
  busy: boolean;
  onClose: () => void;
  onCreate: (name: string) => void;
}

function CollectionCreateModal({ busy, onClose, onCreate }: CollectionCreateModalProps) {
  const [name, setName] = useState('');
  const trimmed = name.trim();
  const handleSubmit = () => {
    if (!trimmed) return;
    onCreate(trimmed);
  };

  return (
    <Modal
      title="Create collection"
      onClose={onClose}
      footer={
        <>
          <button className="text-button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="primary-button" disabled={busy || !trimmed} onClick={handleSubmit}>
            {busy ? 'Creating…' : 'Create'}
          </button>
        </>
      }
    >
      <div className="collection-create-field">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Collection name"
          autoFocus
          onKeyDown={(event) => {
            if (event.key === 'Enter' && trimmed) {
              handleSubmit();
            } else if (event.key === 'Escape') {
              onClose();
            }
          }}
        />
      </div>
    </Modal>
  );
}

function CollectionManageModal({ collection, documents, busy, onClose, onSave }: CollectionManageModalProps) {
  const [search, setSearch] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    () =>
      new Set(
        documents
          .filter((document) => document.collection_names.includes(collection.name))
          .map((document) => document.id),
      ),
  );

  const filtered = useMemo(() => {
    const trimmed = search.trim().toLowerCase();
    if (!trimmed) return documents;
    return documents.filter(
      (document) =>
        document.title.toLowerCase().includes(trimmed) ||
        (document.author ?? '').toLowerCase().includes(trimmed) ||
        (document.series ?? '').toLowerCase().includes(trimmed),
    );
  }, [documents, search]);

  const toggle = (documentId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(documentId)) {
        next.delete(documentId);
      } else {
        next.add(documentId);
      }
      return next;
    });
  };

  return (
    <Modal
      title="Manage collection"
      subtitle={collection.name}
      onClose={onClose}
      footer={
        <>
          <button className="text-button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            className="primary-button"
            disabled={busy}
            onClick={() => onSave(collection.id, Array.from(selectedIds))}
          >
            {busy ? 'Saving…' : 'Save'}
          </button>
        </>
      }
    >
      <div className="collection-manage-search">
        <input
          type="search"
          placeholder="Search books…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          autoFocus
        />
      </div>
      <div className="collection-manage-list">
        {filtered.length === 0 ? (
          <p className="empty-state">No books match your search.</p>
        ) : (
          filtered.map((document) => (
            <label key={document.id} className="collection-manage-row">
              <input
                type="checkbox"
                checked={selectedIds.has(document.id)}
                onChange={() => toggle(document.id)}
              />
              <span className="collection-manage-title">{document.title}</span>
              {document.author && (
                <span className="collection-manage-meta">{document.author}</span>
              )}
            </label>
          ))
        )}
      </div>
    </Modal>
  );
}
