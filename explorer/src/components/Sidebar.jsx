import SearchBar from './SearchBar';
import ProductList from './ProductList';

export default function Sidebar({ products, totalCount, selectedId, onSelect, query, onSearchChange }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="sidebar-title">COS Dataset</h1>
        <SearchBar query={query} onChange={onSearchChange} />
      </div>
      <ProductList
        products={products}
        totalCount={totalCount}
        selectedId={selectedId}
        onSelect={onSelect}
      />
    </aside>
  );
}
