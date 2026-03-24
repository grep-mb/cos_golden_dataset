import Papa from 'papaparse';

/**
 * Parse a recommendations CSV into the pipeline_recommendations shape
 * used by the explorer dataset.
 *
 * @param {string} csvText - Raw CSV content
 * @param {Object} catalogImages - product_id → image URL lookup
 * @param {Map} productInfoLookup - product_id → { product_name, product_url }
 * @returns {{ recommendations: Map<string, Array>, totalCsvProducts: number }}
 */
export function parsePipelineCsv(csvText, catalogImages, productInfoLookup) {
  // Strip UTF-8 BOM that Windows-generated CSVs may prepend
  const text = csvText.replace(/^\uFEFF/, '');

  const { data: rows, errors } = Papa.parse(text, {
    header: true,
    skipEmptyLines: true,
  });

  if (errors.length > 0 && rows.length === 0) {
    throw new Error(`CSV parse failed: ${errors[0].message}`);
  }

  // Group rows by source product ID (multiple cutouts per product)
  const byProduct = new Map();

  for (const row of rows) {
    const productId = (row.sourceItemId || '').replace('product#', '').trim();
    if (!productId) continue;

    const category = (row.category || '').trim();
    const recIds = (row.itemRecommendations || '')
      .split(',')
      .map(s => s.trim())
      .filter(Boolean);
    const scores = (row.recommendationScores || '')
      .split(',')
      .map(s => parseFloat(s.trim()))
      .filter(n => !isNaN(n));

    if (!byProduct.has(productId)) {
      byProduct.set(productId, []);
    }

    byProduct.get(productId).push({
      category,
      products: recIds.map((recId, idx) => {
        const info = productInfoLookup.get(recId);
        const catalogImg = catalogImages[recId];
        return {
          product_id: recId,
          product_name: info?.product_name || '',
          product_url: info?.product_url || '',
          product_images: catalogImg ? [catalogImg] : [],
          score: scores[idx] ?? null,
        };
      }),
    });
  }

  return { recommendations: byProduct, totalCsvProducts: byProduct.size };
}
