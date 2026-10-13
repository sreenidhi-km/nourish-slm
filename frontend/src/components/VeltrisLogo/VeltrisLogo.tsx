import React from 'react';
import logoDark from '../../assets/veltris-logo.png';
import logoLight from '../../assets/veltris-logo-light.png';
import markDark from '../../assets/veltris-mark.png';
import markLight from '../../assets/veltris-mark-light.png';

interface VeltrisLogoProps {
  /** Rendered height in px (width follows the logo's aspect ratio). */
  height?: number;
  /** "full" = mark + VELTRIS wordmark + tagline, "mark" = icon only. */
  variant?: 'full' | 'mark';
  style?: React.CSSProperties;
}

/**
 * Veltris brand logo. Shows the navy logo in light mode and a white-text
 * version in dark mode (switched by the [data-theme] attribute via CSS).
 */
export const VeltrisLogo: React.FC<VeltrisLogoProps> = ({ height = 32, variant = 'full', style }) => {
  const light = variant === 'full' ? logoDark : markDark;   // used on light backgrounds
  const dark = variant === 'full' ? logoLight : markLight;  // used on dark backgrounds
  const common: React.CSSProperties = { height, width: 'auto', display: 'block', ...style };
  return (
    <>
      <img src={light} alt="Veltris" className="veltris-logo-for-light" style={common} />
      <img src={dark} alt="Veltris" className="veltris-logo-for-dark" style={common} />
    </>
  );
};
