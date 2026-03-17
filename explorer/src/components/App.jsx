import { useState } from 'react';
import dataset from '../data/golden_dataset.json';
import { useSearch } from '../hooks/useSearch';
import Sidebar from './Sidebar';
import ProductDetail from './ProductDetail';

export default function App() {
  const [selectedProduct, setSelectedProduct] = useState(null);
  const { query, setQuery, results } = useSearch(dataset);

  return (
    <div className="app">
      <div className="bg-noise" />
      <Sidebar
        products={results}
        totalCount={dataset.length}
        selectedId={selectedProduct?.source_product_id}
        onSelect={setSelectedProduct}
        query={query}
        onSearchChange={setQuery}
      />
      <ProductDetail product={selectedProduct} />
    </div>
  );
}
