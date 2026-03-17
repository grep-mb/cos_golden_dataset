export default function ProductList({ products, totalCount, selectedId, onSelect, sortAlpha, onToggleSort }) {
  const countLabel = products.length === totalCount
    ? `${totalCount} products`
    : `${products.length} / ${totalCount}`;

  return (
    <div className="product-list">
      <div className="product-list-count" aria-live="polite">
        <span className="accent-dash mono-label">{countLabel}</span>
        <button
          className={`sort-toggle${sortAlpha ? ' active' : ''}`}
          onClick={onToggleSort}
          aria-label={sortAlpha ? 'Sort by default order' : 'Sort alphabetically'}
          title={sortAlpha ? 'Default order' : 'Sort A–Z'}
        >
          A–Z
        </button>
      </div>

      <div role="listbox" aria-label="Product list">
        {products.length === 0 ? (
          <div className="product-list-empty mono-label">No products found</div>
        ) : (
          products.map(product => {
            const isSelected = selectedId === product.source_product_id;
            return (
              <button
                key={product.source_product_id}
                role="option"
                aria-selected={isSelected}
                className={`product-list-item${isSelected ? ' selected' : ''}`}
                onClick={() => onSelect(product)}
              >
                <div className="product-list-item-header">
                  <span className={`section-badge ${product.section}`}>
                    {product.section}
                  </span>
                  <span className="product-id mono-label">{product.source_product_id}</span>
                </div>
                <div className="product-name">{product.source_product_name}</div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
