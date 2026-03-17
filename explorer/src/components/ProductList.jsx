export default function ProductList({ products, totalCount, selectedId, onSelect }) {
  return (
    <div className="product-list">
      <div className="product-list-count" aria-live="polite">
        {products.length === totalCount
          ? `${totalCount} products`
          : `${products.length} of ${totalCount} products`}
      </div>
      <div role="listbox" aria-label="Product list">
        {products.map(product => {
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
                <span className="product-id">{product.source_product_id}</span>
              </div>
              <div className="product-name">{product.source_product_name}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
