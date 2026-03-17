import ImageGallery from './ImageGallery';
import RecommendedProducts from './RecommendedProducts';

export default function ProductDetail({ product }) {
  if (!product) {
    return (
      <main className="main-content empty-state">
        <p>Select a product from the sidebar to view details.</p>
      </main>
    );
  }

  return (
    <main className="main-content">
      <div className="product-detail-header">
        <div className="product-detail-meta">
          <span className={`section-badge ${product.section}`}>
            {product.section}
          </span>
          <span className="product-id">{product.source_product_id}</span>
        </div>
        <h2 className="product-detail-name">{product.source_product_name}</h2>
        <a
          href={product.source_product_url}
          target="_blank"
          rel="noopener noreferrer"
          className="product-detail-link"
        >
          View on COS &rarr;
        </a>
      </div>

      <ImageGallery images={product.source_product_images} productName={product.source_product_name} />
      <RecommendedProducts products={product.recommended_products} />
    </main>
  );
}
