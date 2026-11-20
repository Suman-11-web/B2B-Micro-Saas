import * as React from 'react';
import { cn } from '@/lib/utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'outline' | 'secondary' | 'ghost' | 'destructive';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    const variants: Record<NonNullable<ButtonProps['variant']>, string> = {
      default:
        'bg-gradient-to-r from-violet-600 via-indigo-600 to-violet-600 text-white shadow-lg shadow-violet-600/25 hover:brightness-110 border border-violet-400/20',
      outline:
        'border border-white/15 bg-white/[0.03] hover:bg-white/[0.08] text-foreground backdrop-blur-sm',
      secondary:
        'bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-white/10',
      ghost: 'hover:bg-white/[0.06] text-foreground',
      destructive:
        'bg-red-600/90 text-white hover:bg-red-600 border border-red-400/20 shadow-sm shadow-red-900/30',
    };

    const sizes: Record<NonNullable<ButtonProps['size']>, string> = {
      default: 'h-10 px-4 py-2 text-sm',
      sm: 'h-8.5 px-3 py-1.5 text-xs',
      lg: 'h-12 px-7 text-sm font-semibold',
      icon: 'h-9 w-9',
    };

    return (
      <button
        ref={ref}
        className={cn(
          'inline-flex items-center justify-center rounded-lg font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/70 disabled:pointer-events-none disabled:opacity-45 active:scale-[0.99]',
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';
