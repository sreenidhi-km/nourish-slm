import React, { useState } from 'react';
import { ImageOff } from 'lucide-react';

interface FoodImageProps {
  src?: string | null;
  alt: string;
  className?: string;
  style?: React.CSSProperties;
}

/** Recipe photo with a loading placeholder and a graceful fallback when the image cannot load. */
export const FoodImage: React.FC<FoodImageProps> = ({ src, alt, className, style }) => {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(!src);

  return (
    <div className={`food-img ${className || ''}`} style={style}>
      {!loaded && !failed && <div className="skeleton" aria-hidden="true" />}
      {failed ? (
        <div className="food-img-fallback" role="img" aria-label={`${alt} (photo unavailable)`}>
          <ImageOff size={20} />
          <span>Photo unavailable</span>
        </div>
      ) : (
        <img
          src={src || ''}
          alt={alt}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          style={{ opacity: loaded ? 1 : 0 }}
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
};
