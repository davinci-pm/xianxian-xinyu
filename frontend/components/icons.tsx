import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function IconBase({ size = 20, children, ...props }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
      {...props}
    >
      {children}
    </svg>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return <IconBase {...props}><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" /></IconBase>;
}

export function SearchIcon(props: IconProps) {
  return <IconBase {...props}><circle cx="10.8" cy="10.8" r="6.3" stroke="currentColor" strokeWidth="1.6" /><path d="m15.5 15.5 4 4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" /></IconBase>;
}

export function SparkIcon(props: IconProps) {
  return <IconBase {...props}><path d="M12 2.8c.8 4.4 2.9 6.5 7.2 7.2-4.3.8-6.4 2.9-7.2 7.2-.8-4.3-2.9-6.4-7.2-7.2C9.1 9.3 11.2 7.2 12 2.8Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.5" /><path d="M18.4 15.3c.3 1.8 1.2 2.7 3 3-1.8.3-2.7 1.2-3 3-.3-1.8-1.2-2.7-3-3 1.8-.3 2.7-1.2 3-3Z" fill="currentColor" /></IconBase>;
}

export function BookIcon(props: IconProps) {
  return <IconBase {...props}><path d="M4.5 4.5h8A2.5 2.5 0 0 1 15 7v13H7a2.5 2.5 0 0 1-2.5-2.5v-13Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.5" /><path d="M15 7a2.5 2.5 0 0 1 2.5-2.5h2V17h-2A2.5 2.5 0 0 0 15 19.5" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.5" /></IconBase>;
}

export function MemoryIcon(props: IconProps) {
  return <IconBase {...props}><path d="M8.2 5.2A3.3 3.3 0 0 1 14 3.6a3.3 3.3 0 0 1 3.2 4.1 3.2 3.2 0 0 1 .7 5.9 3.3 3.3 0 0 1-4.1 5.1 3.3 3.3 0 0 1-5.6-.5 3.2 3.2 0 0 1-2.1-5.8 3.2 3.2 0 0 1 2.1-7.2Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.5" /><path d="M12 5.5V19M8.5 9.2c1.8 0 3.5 1.4 3.5 3.2m3.5-2.8c-1.8 0-3.5 1.4-3.5 3.2" stroke="currentColor" strokeLinecap="round" strokeWidth="1.3" /></IconBase>;
}

export function MenuIcon(props: IconProps) {
  return <IconBase {...props}><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" /></IconBase>;
}

export function CloseIcon(props: IconProps) {
  return <IconBase {...props}><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" /></IconBase>;
}

export function ChevronDownIcon(props: IconProps) {
  return <IconBase {...props}><path d="m6 9 6 6 6-6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" /></IconBase>;
}

export function QuoteIcon(props: IconProps) {
  return <IconBase {...props}><path d="M5 7h6v6H7c0 2 1 3.4 3 4l-1 2c-3.7-1.2-5-3.6-4-7V7Zm9 0h6v6h-4c0 2 1 3.4 3 4l-1 2c-3.7-1.2-5-3.6-4-7V7Z" fill="currentColor" /></IconBase>;
}

export function SendIcon(props: IconProps) {
  return <IconBase {...props}><path d="m3 11 17-7-7 17-2.2-7.8L3 11Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.6" /><path d="m11 13 4-4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" /></IconBase>;
}

export function StopIcon(props: IconProps) {
  return <IconBase {...props}><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" /></IconBase>;
}

export function MoreIcon(props: IconProps) {
  return <IconBase {...props}><circle cx="5" cy="12" r="1.5" fill="currentColor" /><circle cx="12" cy="12" r="1.5" fill="currentColor" /><circle cx="19" cy="12" r="1.5" fill="currentColor" /></IconBase>;
}

export function ExternalIcon(props: IconProps) {
  return <IconBase {...props}><path d="M14 5h5v5M19 5l-8 8" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" /><path d="M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" /></IconBase>;
}

