import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const inputPath = join(__dirname, '../../data/golden_dataset.jsonl');
const imagesDir = join(__dirname, '../../data/images');
const recThumbDir = join(__dirname, '../../data/rec-thumbnails');
const baselineThumbDir = join(__dirname, '../../data/baseline-thumbnails');
const outputDir = join(__dirname, '../src/data');
const outputPath = join(outputDir, 'golden_dataset.json');

// Path to the shop-the-look baseline recommendations CSV (double-tab delimited)
const baselineCsvPath = join(__dirname, '../../data/baseline_recommendations.csv');
// Path to the cos-catalog pipeline recommendations CSV
const pipelineCsvPath = join(__dirname, '../../../cos-catalog/recommendations.csv');
// Catalog image lookup: product_id → first image URL (generated from LakeFS catalog)
const catalogImagePath = join(__dirname, '../../data/catalog_image_lookup.json');

mkdirSync(outputDir, { recursive: true });

// --- Load catalog image lookup ---
let catalogImages = {};
if (existsSync(catalogImagePath)) {
  catalogImages = JSON.parse(readFileSync(catalogImagePath, 'utf-8'));
  console.log(`Loaded catalog images for ${Object.keys(catalogImages).length} products`);
} else {
  console.log(`No catalog image lookup at ${catalogImagePath}, pipeline recs will have no images`);
}

// --- Parse baseline recommendations CSV ---
// Format: product_id\t\tattribute_id\t\tattribute_value
// attribute_id is the look_id (e.g. shop_the_look_0)
// attribute_value contains recommended product IDs separated by ;;
const baselineByProduct = new Map();

if (existsSync(baselineCsvPath)) {
  const csvLines = readFileSync(baselineCsvPath, 'utf-8')
    .split('\n')
    .filter(line => line.trim());

  // Skip header row
  for (let i = 1; i < csvLines.length; i++) {
    const cols = csvLines[i].split('\t\t');
    if (cols.length < 3) continue;

    const productId = cols[0].trim();
    const lookId = cols[1].trim();
    const recIds = cols[2].trim().split(';;').filter(Boolean);

    if (!baselineByProduct.has(productId)) {
      baselineByProduct.set(productId, []);
    }
    baselineByProduct.get(productId).push({ look_id: lookId, product_ids: recIds });
  }
  console.log(`Loaded baseline recommendations for ${baselineByProduct.size} products`);
} else {
  console.log(`No baseline CSV found at ${baselineCsvPath}, skipping`);
}

// --- Parse pipeline recommendations CSV (cos-catalog) ---
// Format: sourceItemId,cutoutImagePath,cutoutId,category,color,gender,shapes,itemRecommendations,recommendationScores
// Each row is one cutout of a source product; group rows by product ID as separate "looks".
const pipelineByProduct = new Map();

if (existsSync(pipelineCsvPath)) {
  const csvContent = readFileSync(pipelineCsvPath, 'utf-8');
  const csvLines = csvContent.split('\n').filter(line => line.trim());
  const header = csvLines[0].split(',');
  const srcIdx = header.indexOf('sourceItemId');
  const catIdx = header.indexOf('category');
  const recIdx = header.indexOf('itemRecommendations');
  const scoreIdx = header.indexOf('recommendationScores');

  for (let i = 1; i < csvLines.length; i++) {
    // Use a simple CSV parse that handles quoted fields with commas
    const cols = [];
    let current = '';
    let inQuotes = false;
    for (const ch of csvLines[i]) {
      if (ch === '"') { inQuotes = !inQuotes; continue; }
      if (ch === ',' && !inQuotes) { cols.push(current); current = ''; continue; }
      current += ch;
    }
    cols.push(current);

    const productId = (cols[srcIdx] || '').replace('product#', '').trim();
    if (!productId) continue;

    const category = (cols[catIdx] || '').trim();
    const recIds = (cols[recIdx] || '').split(',').map(s => s.trim()).filter(Boolean);
    const scores = (cols[scoreIdx] || '').split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));

    if (!pipelineByProduct.has(productId)) {
      pipelineByProduct.set(productId, []);
    }
    pipelineByProduct.get(productId).push({
      category,
      product_ids: recIds,
      scores,
    });
  }
  console.log(`Loaded pipeline recommendations for ${pipelineByProduct.size} products`);
} else {
  console.log(`No pipeline CSV found at ${pipelineCsvPath}, skipping`);
}

// --- Parse golden dataset ---
const lines = readFileSync(inputPath, 'utf-8')
  .split('\n')
  .filter(line => line.trim());

// Build a product-info lookup from the golden dataset (both source and recommended products)
// so we can enrich baseline recommendations with names/images if the product appears in the dataset
const productInfoLookup = new Map();

const records = lines.map(line => JSON.parse(line));

for (const record of records) {
  productInfoLookup.set(record.source_product_id, {
    product_name: record.source_product_name,
    product_url: record.source_product_url,
  });
  for (const rp of record.recommended_products) {
    if (!productInfoLookup.has(rp.product_id)) {
      productInfoLookup.set(rp.product_id, {
        product_name: rp.product_name,
        product_url: rp.product_url,
      });
    }
  }
}

const data = records.map(record => {
  // Rewrite CDN image URLs to local paths served via /images/
  // Local images are at: data/images/{product_id}/{0,1,2,...}.jpg
  const pid = record.source_product_id;
  const localDir = join(imagesDir, pid);
  if (existsSync(localDir)) {
    const count = record.source_product_images.length;
    record.source_product_images = [];
    for (let i = 0; i < count; i++) {
      const imgPath = join(localDir, `${i}.jpg`);
      if (existsSync(imgPath)) {
        record.source_product_images.push(`/images/${pid}/${i}.jpg`);
      }
    }
  }
  // Rewrite recommendation image URLs to local thumbnails
  for (const rp of record.recommended_products) {
    const thumbPath = join(recThumbDir, `${rp.product_id}.jpg`);
    if (existsSync(thumbPath)) {
      rp.product_images = [`/rec-thumbnails/${rp.product_id}.jpg`];
    }
  }

  // Merge baseline recommendations
  const baselineLooks = baselineByProduct.get(pid);
  if (baselineLooks) {
    record.baseline_recommendations = baselineLooks.map(look => ({
      look_id: look.look_id,
      products: look.product_ids.map(recId => {
        const info = productInfoLookup.get(recId);
        const thumbPath = join(baselineThumbDir, `${recId}.jpg`);
        const hasThumb = existsSync(thumbPath);
        return {
          product_id: recId,
          product_name: info?.product_name || '',
          product_url: info?.product_url || '',
          product_images: hasThumb ? [`/baseline-thumbnails/${recId}.jpg`] : [],
        };
      }),
    }));
  } else {
    record.baseline_recommendations = [];
  }

  // Merge pipeline recommendations (from cos-catalog recommendations.csv)
  const pipelineLooks = pipelineByProduct.get(pid);
  if (pipelineLooks) {
    record.pipeline_recommendations = pipelineLooks.map(look => ({
      category: look.category,
      products: look.product_ids.map((recId, idx) => {
        const info = productInfoLookup.get(recId);
        const catalogImg = catalogImages[recId];
        return {
          product_id: recId,
          product_name: info?.product_name || '',
          product_url: info?.product_url || '',
          product_images: catalogImg ? [catalogImg] : [],
          score: look.scores[idx] ?? null,
        };
      }),
    }));
  } else {
    record.pipeline_recommendations = [];
  }

  return record;
});

writeFileSync(outputPath, JSON.stringify(data));
console.log(`Converted ${data.length} products to ${outputPath}`);

// Write catalog image lookup to src/data/ so the browser can resolve images for runtime CSV uploads
const catalogImageOutputPath = join(outputDir, 'catalog_image_lookup.json');
writeFileSync(catalogImageOutputPath, JSON.stringify(catalogImages));
console.log(`Wrote catalog image lookup (${Object.keys(catalogImages).length} entries) to ${catalogImageOutputPath}`);
