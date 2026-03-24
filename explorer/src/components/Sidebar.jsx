import SearchBar from './SearchBar';
import ProductList from './ProductList';

function FilenameParts({ filename }) {
  if (!filename) return null;
  const dotIdx = filename.lastIndexOf('.');
  if (dotIdx <= 0) return <>{filename}</>;
  const stem = filename.slice(0, dotIdx);
  const ext = filename.slice(dotIdx);
  return (
    <>
      <span className="csv-upload-filename-stem">{stem}</span>
      <span className="csv-upload-filename-ext">{ext}</span>
    </>
  );
}

export default function Sidebar({ products, totalCount, selectedId, onSelect, query, onSearchChange, sortAlpha, onToggleSort, uploadState, onUploadCsv, onApplyUpload, onClearUpload }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <h1 className="sidebar-title">COS Style Explorer</h1>
          <div className="sidebar-status">
            <span className="status-dot" aria-hidden="true" />
            <span className="mono-label">{totalCount} items</span>
          </div>
        </div>
        <div className="csv-upload-control">
          {uploadState.status === 'idle' && (
            <button className="csv-upload-button" onClick={onUploadCsv}>
              Upload CSV
            </button>
          )}
          {uploadState.status === 'loading' && (
            <div className="csv-upload-status">
              <span className="status-dot" aria-hidden="true" />
              <span className="mono-label">Parsing CSV&hellip;</span>
            </div>
          )}
          {uploadState.status === 'parsed' && (
            <div className="csv-upload-parsed">
              <div className="csv-upload-status">
                <span className="csv-upload-filename mono-label" title={uploadState.filename}>
                  <FilenameParts filename={uploadState.filename} />
                </span>
                <span className="mono-label">
                  {uploadState.matchedCount}/{uploadState.totalCsvProducts} matched
                </span>
                <button
                  className="csv-upload-clear"
                  onClick={onClearUpload}
                  aria-label="Discard uploaded CSV"
                >
                  &times;
                </button>
              </div>
              <button className="csv-upload-apply" onClick={onApplyUpload}>
                Apply recommendations
              </button>
            </div>
          )}
          {uploadState.status === 'applied' && (
            <div className="csv-upload-status">
              <span className="csv-upload-filename mono-label" title={uploadState.filename}>
                <FilenameParts filename={uploadState.filename} />
              </span>
              <span className="csv-upload-active mono-label">Active</span>
              <button
                className="csv-upload-clear"
                onClick={onClearUpload}
                aria-label="Clear uploaded CSV and revert"
              >
                &times;
              </button>
            </div>
          )}
          {uploadState.status === 'error' && (
            <div className="csv-upload-status">
              <span className="csv-upload-error mono-label">{uploadState.error}</span>
              <button
                className="csv-upload-clear"
                onClick={onClearUpload}
                aria-label="Dismiss error"
              >
                &times;
              </button>
            </div>
          )}
        </div>
        <SearchBar query={query} onChange={onSearchChange} />
      </div>
      <ProductList
        products={products}
        totalCount={totalCount}
        selectedId={selectedId}
        onSelect={onSelect}
        sortAlpha={sortAlpha}
        onToggleSort={onToggleSort}
      />
    </aside>
  );
}
