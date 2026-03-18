import SearchBar from './SearchBar';
import ProductList from './ProductList';

export default function Sidebar({ products, totalCount, selectedId, onSelect, query, onSearchChange, sortAlpha, onToggleSort }) {
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
