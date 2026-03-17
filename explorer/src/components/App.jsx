import { useState } from 'react';
import dataset from '../data/golden_dataset.json';
import { useSearch } from '../hooks/useSearch';
import Sidebar from './Sidebar';
import ProductDetail from './ProductDetail';

export default function App() {
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [sortAlpha, setSortAlpha] = useState(true);
  const { query, setQuery, results } = useSearch(dataset, sortAlpha);

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
      />
      <ProductDetail product={selectedProduct} onBack={() => setSelectedProduct(null)} />
    </div>
  );
}
