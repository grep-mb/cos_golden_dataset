import { useState } from 'react';

const FALLBACK = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="400" height="500" fill="%23f0f0f0"><rect width="400" height="500"/><text x="50%" y="50%" fill="%23999" font-size="14" text-anchor="middle" dominant-baseline="middle">Image unavailable</text></svg>';

export default function ImageGallery({ images, productName }) {
  const [selected, setSelected] = useState(0);

  if (!images || images.length === 0) return null;

  const label = productName || 'Product';

  return (
    <div className="image-gallery" role="group" aria-label={`${label} images`}>
      <div className="image-hero">
        <img
          src={images[selected]}
          alt={`${label} — image ${selected + 1} of ${images.length}`}
          onError={e => { e.target.src = FALLBACK; }}
        />
      </div>
      {images.length > 1 && (
        <div className="image-thumbnails" role="group" aria-label="Image thumbnails">
          {images.map((url, i) => (
            <button
              key={i}
              className={`image-thumb${i === selected ? ' active' : ''}`}
              onClick={() => setSelected(i)}
              aria-label={`View image ${i + 1} of ${images.length}`}
              aria-pressed={i === selected}
            >
              <img
                src={url}
                alt=""
                loading="lazy"
                onError={e => { e.target.src = FALLBACK; }}
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
