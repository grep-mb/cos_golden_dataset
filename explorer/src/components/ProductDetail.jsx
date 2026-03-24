import { useEffect, useRef } from 'react';
import ImageGallery from './ImageGallery';
import RecommendedProducts from './RecommendedProducts';
import PipelineRecommendations from './PipelineRecommendations';
import BaselineRecommendations from './BaselineRecommendations';

export default function ProductDetail({ product, onBack }) {
  const mainRef = useRef(null);

  useEffect(() => {
    if (product && mainRef.current) {
      mainRef.current.scrollTop = 0;
    }
  }, [product]);

  if (!product) {
    return (
      <main className="main-content empty-state">
        <div className="bg-tech-grid" aria-hidden="true" />
        <div className="empty-state-content">
          <div className="sec-label">[STYLE.EXPLORER]</div>
          <h2>Select a product<br />to inspect.</h2>
          <p>Browse COS products and their &ldquo;Style with&rdquo; recommendations.</p>
        </div>
        <div className="empty-state-watermark" aria-hidden="true">COS</div>
      </main>
    );
  }

  return (
    <main className="main-content" ref={mainRef}>
      <button className="back-button" onClick={onBack} aria-label="Back to product list">
        <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path d="M12.5 15L7.5 10L12.5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        All products
      </button>

      <div className="product-detail-header">
        <div className="product-detail-meta">
          <span className={`section-badge ${product.section}`}>
            {product.section}
          </span>
          <span className="product-id mono-label">{product.source_product_id}</span>
        </div>
        <h2 className="product-detail-name">{product.source_product_name}</h2>
        <a
          href={product.source_product_url}
          target="_blank"
          rel="noopener noreferrer"
          className="product-detail-link"
        >
          View on COS &rarr;
          <span className="sr-only">(opens in new tab)</span>
        </a>
      </div>

      <div className="product-detail-content">
        <div className="product-detail-left">
          <ImageGallery
            key={product.source_product_id}
            images={product.source_product_images}
            productName={product.source_product_name}
          />
        </div>
        <div className="product-detail-right">
          <RecommendedProducts products={product.recommended_products} />
          <PipelineRecommendations looks={product.pipeline_recommendations} />
          <BaselineRecommendations looks={product.baseline_recommendations} />
        </div>
      </div>
    </main>
  );
}
