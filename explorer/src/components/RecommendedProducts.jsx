export default function RecommendedProducts({ products }) {
  if (!products || products.length === 0) return null;

  return (
    <div className="recommended">
      <h3 className="recommended-title">
        Style with ({products.length})
      </h3>
      <div className="recommended-list">
        {products.map(product => (
          <div key={product.product_id} className="recommended-item">
            <div className="recommended-info">
              <span className="recommended-name">{product.product_name}</span>
              <span className="product-id">{product.product_id}</span>
            </div>
            <a
              href={product.product_url}
              target="_blank"
              rel="noopener noreferrer"
              className="recommended-link"
            >
              View on COS &rarr;
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
