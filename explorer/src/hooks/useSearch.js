import Fuse from 'fuse.js';
import { useMemo, useState } from 'react';

const ID_PATTERN = /^\d{5,}$/;

export function useSearch(products) {
  const [query, setQuery] = useState('');

  const fuse = useMemo(() => new Fuse(products, {
    keys: [
      { name: 'source_product_name', weight: 0.7 },
      { name: 'source_product_id', weight: 0.3 },
    ],
    threshold: 0.4,
    includeScore: true,
    minMatchCharLength: 2,
  }), [products]);

  const results = useMemo(() => {
    const q = query.trim();
    if (!q) return products;

    // For numeric queries (product IDs), use exact prefix matching
    if (ID_PATTERN.test(q)) {
      const exact = products.filter(p => p.source_product_id === q);
      if (exact.length > 0) return exact;
      return products.filter(p => p.source_product_id.includes(q));
    }

    return fuse.search(q).map(r => r.item);
  }, [query, fuse, products]);

  return { query, setQuery, results };
}
