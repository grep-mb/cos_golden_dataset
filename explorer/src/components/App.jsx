import { useState, useEffect } from 'react';
import baseDataset from '../data/golden_dataset.json';
import { useSearch } from '../hooks/useSearch';
import { useCsvUpload } from '../hooks/useCsvUpload';
import Sidebar from './Sidebar';
import ProductDetail from './ProductDetail';

export default function App() {
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [sortAlpha, setSortAlpha] = useState(true);
  const { dataset, uploadState, triggerUpload, applyUpload, clearUpload } = useCsvUpload(baseDataset);
  const { query, setQuery, results } = useSearch(dataset, sortAlpha);

  // When the dataset changes (CSV upload/clear), refresh the selected product
  // so the detail view reflects the new pipeline recommendations
  useEffect(() => {
    if (!selectedProduct) return;
    const updated = dataset.find(p => p.source_product_id === selectedProduct.source_product_id);
    if (updated) setSelectedProduct(updated);
  }, [dataset]);

  return (
    <div className={`app${selectedProduct ? ' has-detail' : ''}`}>
      <div className="bg-noise" />
      <Sidebar
        products={results}
        totalCount={dataset.length}
        selectedId={selectedProduct?.source_product_id}
        onSelect={setSelectedProduct}
        query={query}
        onSearchChange={setQuery}
        sortAlpha={sortAlpha}
        onToggleSort={() => setSortAlpha(s => !s)}
        uploadState={uploadState}
        onUploadCsv={triggerUpload}
        onApplyUpload={applyUpload}
        onClearUpload={clearUpload}
      />
      <ProductDetail product={selectedProduct} onBack={() => setSelectedProduct(null)} />
    </div>
  );
}
