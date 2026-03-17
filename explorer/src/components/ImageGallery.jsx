import { useState } from 'react';

const FALLBACK = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="400" height="500" fill="%23f0f0f0"><rect width="400" height="500"/><text x="50%" y="50%" fill="%23999" font-size="14" text-anchor="middle" dominant-baseline="middle">Image unavailable</text></svg>';

export default function ImageGallery({ images }) {
  const [selected, setSelected] = useState(0);

  if (!images || images.length === 0) return null;

  return (
    <div className="image-gallery">
      <div className="image-hero">
        <img
          src={images[selected]}
          alt={`Product image ${selected + 1}`}
          onError={e => { e.target.src = FALLBACK; }}
        />
      </div>
      {images.length > 1 && (
        <div className="image-thumbnails">
          {images.map((url, i) => (
            <button
              key={i}
              className={`image-thumb${i === selected ? ' active' : ''}`}
              onClick={() => setSelected(i)}
            >
              <img
                src={url}
                alt={`Thumbnail ${i + 1}`}
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
