import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const inputPath = join(__dirname, '../../data/golden_dataset.jsonl');
const imagesDir = join(__dirname, '../../data/images');
const recThumbDir = join(__dirname, '../../data/rec-thumbnails');
const outputDir = join(__dirname, '../src/data');
const outputPath = join(outputDir, 'golden_dataset.json');

mkdirSync(outputDir, { recursive: true });

const lines = readFileSync(inputPath, 'utf-8')
  .split('\n')
  .filter(line => line.trim());

const data = lines.map(line => {
  const record = JSON.parse(line);
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
  return record;
});

writeFileSync(outputPath, JSON.stringify(data));
console.log(`Converted ${data.length} products to ${outputPath}`);
