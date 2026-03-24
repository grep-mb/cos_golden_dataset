const FALLBACK = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="120" height="150" fill="%23f0f0f0"><rect width="120" height="150"/><text x="50%" y="50%" fill="%23999" font-size="11" text-anchor="middle" dominant-baseline="middle">No image</text></svg>';

export default function RecommendedProducts({ products, title = 'Style.With' }) {
  if (!products || products.length === 0) return null;

  return (
    <section className="recommended" aria-label="Recommended products">
      <h3 className="recommended-title sec-label">
        [{title}] &mdash; {products.length} item{products.length !== 1 ? 's' : ''}
      </h3>
      <ul className="recommended-list">
        {products.map(product => (
          <li key={product.product_id} className="recommended-item">
            <div className="recommended-image">
              <img
                src={product.product_images?.[0] || FALLBACK}
                alt={product.product_name}
                onError={e => { e.target.src = FALLBACK; }}
                loading="lazy"
              />
            </div>
            <div className="recommended-body">
              <div className="recommended-info">
                <span className="recommended-name">{product.product_name}</span>
                <span className="product-id mono-label">{product.product_id}</span>
              </div>
              <a
                href={product.product_url}
                target="_blank"
                rel="noopener noreferrer"
                className="recommended-link"
              >
                View on COS &rarr;
                <span className="sr-only">(opens in new tab)</span>
              </a>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
