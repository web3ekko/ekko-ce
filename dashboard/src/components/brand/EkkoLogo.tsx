export interface EkkoLogoProps {
  /**
   * Logo variant to display
   * - icon: Pure circular icon (no text)
   * - horizontal: Icon + "EKKO" text side-by-side
   * - vertical: Icon with "EKKO" text stacked below
   */
  variant?: 'icon' | 'horizontal' | 'vertical';

  /**
   * Size of the logo
   * - Predefined: 'sm' (32px), 'md' (48px), 'lg' (96px), 'xl' (128px)
   * - Custom: Number in pixels
   */
  size?: 'sm' | 'md' | 'lg' | 'xl' | number;

  /**
   * Additional CSS classes to apply
   */
  className?: string;

  /**
   * Alt text for accessibility
   * Default: "Ekko logo" for static, "Ekko - Go to dashboard" for interactive
   */
  alt?: string;

  /**
   * Whether the logo is interactive (clickable/focusable)
   */
  interactive?: boolean;

  /**
   * Click handler for interactive logos
   */
  onClick?: () => void;
}

const SIZE_MAP = {
  sm: 32,
  md: 48,
  lg: 96,
  xl: 128,
} as const;

/**
 * EkkoLogo Component
 *
 * Displays the Ekko platform logo with support for multiple variants
 * and responsive sizing. Light mode only (OpenRouter-inspired design).
 * Follows WCAG 2.1 AA accessibility standards.
 *
 * @example
 * ```tsx
 * // Dashboard header - horizontal logo
 * <EkkoLogo variant="horizontal" size="md" interactive onClick={() => navigate('/')} />
 *
 * // Authentication page - vertical logo
 * <EkkoLogo variant="vertical" size="lg" />
 *
 * // Mobile navigation - icon only
 * <EkkoLogo variant="icon" size="sm" />
 * ```
 */
export const EkkoLogo = ({
  variant = 'icon',
  size = 'md',
  className = '',
  alt,
  interactive = false,
  onClick,
}: EkkoLogoProps) => {
  // Calculate numeric size
  const numericSize = typeof size === 'number' ? size : SIZE_MAP[size];

  // Determine logo source path (light mode only)
  const getLogoSrc = () => {
    switch (variant) {
      case 'horizontal':
        return '/logos/ekko-logo-horizontal.svg';
      case 'vertical':
        return '/logos/ekko-logo-vertical.svg';
      case 'icon':
      default:
        return '/logos/ekko-icon.svg';
    }
  };

  // Default alt text based on interactivity
  const defaultAlt = interactive
    ? 'Ekko - Go to dashboard'
    : 'Ekko logo';

  const altText = alt || defaultAlt;

  // Base styles
  const baseStyles: React.CSSProperties = {
    width: variant === 'horizontal' ? numericSize * 2 : numericSize,
    height: variant === 'vertical' ? numericSize * 1.2 : numericSize,
    display: 'inline-block',
    transition: 'opacity 0.2s ease',
    cursor: interactive ? 'pointer' : 'default',
  };

  // Wrapper classes
  const wrapperClasses = [
    'ekko-logo',
    `ekko-logo--${variant}`,
    interactive && 'ekko-logo--interactive',
    className,
  ].filter(Boolean).join(' ');

  const handleClick = () => {
    if (interactive && onClick) {
      onClick();
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (interactive && onClick && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      onClick();
    }
  };

  return (
    <div
      className={wrapperClasses}
      style={baseStyles}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role={interactive ? 'button' : 'img'}
      aria-label={interactive ? altText : undefined}
      tabIndex={interactive ? 0 : undefined}
    >
      <img
        src={getLogoSrc()}
        alt={interactive ? '' : altText}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
        }}
        draggable="false"
      />
    </div>
  );
};

export default EkkoLogo;
