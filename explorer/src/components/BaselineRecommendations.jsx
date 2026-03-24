const FALLBACK = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="120" height="150" fill="%23f0f0f0"><rect width="120" height="150"/><text x="50%" y="50%" fill="%23999" font-size="11" text-anchor="middle" dominant-baseline="middle">No image</text></svg>';

export default function BaselineRecommendations({ looks }) {
  if (!looks || looks.length === 0) return null;

  const totalProducts = looks.reduce((sum, look) => sum + look.products.length, 0);

  return (
    <section className="baseline-section" aria-label="Baseline recommendations">
      <h3 className="recommended-title sec-label">
        [Baseline] &mdash; {totalProducts} item{totalProducts !== 1 ? 's' : ''} across {looks.length} look{looks.length !== 1 ? 's' : ''}
      </h3>
      {looks.map((look, idx) => (
        <div key={look.look_id} className="look-group">
          <div className="look-group-label mono-label">Look {idx + 1}</div>
          <ul className="recommended-list">
            {look.products.map(product => (
              <li key={product.product_id} className="recommended-item">
                <div className="recommended-image">
                  <img
                    src={product.product_images?.[0] || FALLBACK}
                    alt={product.product_name || product.product_id}
                    onError={e => { e.target.src = FALLBACK; }}
                    loading="lazy"
                  />
                </div>
                <div className="recommended-body">
                  <div className="recommended-info">
                    {product.product_name && (
                      <span className="recommended-name">{product.product_name}</span>
                    )}
                    <span className="product-id mono-label">{product.product_id}</span>
                  </div>
                  {product.product_url && (
                    <a
                      href={product.product_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="recommended-link"
                    >
                      View on COS &rarr;
                      <span className="sr-only">(opens in new tab)</span>
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
