const FALLBACK = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="120" height="150" fill="%23f0f0f0"><rect width="120" height="150"/><text x="50%" y="50%" fill="%23999" font-size="11" text-anchor="middle" dominant-baseline="middle">No image</text></svg>';

export default function PipelineRecommendations({ looks }) {
  if (!looks || looks.length === 0) return null;

  const MAX_PER_CUTOUT = 3;
  const totalProducts = looks.reduce((sum, look) => sum + Math.min(look.products.length, MAX_PER_CUTOUT), 0);

  return (
    <section className="baseline-section" aria-label="Pipeline recommendations">
      <h3 className="recommended-title sec-label">
        [Recommendations] &mdash; top {MAX_PER_CUTOUT} per cutout across {looks.length} cutout{looks.length !== 1 ? 's' : ''}
      </h3>
      {looks.map((look, idx) => (
        <div key={`${look.category}-${idx}`} className="look-group">
          <div className="look-group-label mono-label">{look.category}</div>
          <ul className="recommended-list">
            {look.products.slice(0, MAX_PER_CUTOUT).map(product => (
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
                    {product.score != null && (
                      <span className="score-label mono-label">{product.score.toFixed(3)}</span>
                    )}
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
