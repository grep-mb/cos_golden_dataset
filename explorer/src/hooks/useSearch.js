import Fuse from 'fuse.js';
import { useMemo, useState } from 'react';

const ID_PATTERN = /^\d{5,}$/;

export function useSearch(products, sortAlpha = false) {
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
    let items;
    if (!q) {
      items = products;
    } else if (ID_PATTERN.test(q)) {
      const exact = products.filter(p => p.source_product_id === q);
      if (exact.length > 0) items = exact;
      else items = products.filter(p => p.source_product_id.includes(q));
    } else {
      items = fuse.search(q).map(r => r.item);
    }

    if (sortAlpha) {
      return [...items].sort((a, b) =>
        a.source_product_name.localeCompare(b.source_product_name)
      );
    }
    return items;
  }, [query, fuse, products, sortAlpha]);

  return { query, setQuery, results };
}
