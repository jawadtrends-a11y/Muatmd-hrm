/**
 * أيقونات النظام — SVG مضمّنة بلا مكتبة خارجية.
 * currentColor فترث لون النص، وstroke-width موحّد.
 */
type P = { size?: number; className?: string };

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export const IcHome = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />
  </svg>
);

export const IcUsers = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
);

export const IcPayroll = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <rect x="2" y="5" width="20" height="14" rx="2" />
    <circle cx="12" cy="12" r="3" />
    <path d="M6 12h.01M18 12h.01" />
  </svg>
);

export const IcClock = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);

export const IcLeave = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M16 3v4M8 3v4M3 11h18M9 15l2 2 4-4" />
  </svg>
);

export const IcChart = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M3 3v18h18" />
    <path d="M7 15l4-5 3 3 5-7" />
  </svg>
);

export const IcSettings = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 9 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 9a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z" />
  </svg>
);

export const IcOrg = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <rect x="9" y="3" width="6" height="5" rx="1" />
    <rect x="2" y="16" width="6" height="5" rx="1" />
    <rect x="16" y="16" width="6" height="5" rx="1" />
    <path d="M12 8v4M5 16v-2h14v2" />
  </svg>
);

export const IcWallet = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M3 7a2 2 0 0 1 2-2h13v4" />
    <rect x="3" y="7" width="18" height="13" rx="2" />
    <path d="M16 13h3" />
  </svg>
);

export const IcDoc = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5M9 13h6M9 17h4" />
  </svg>
);

export const IcMenu = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M3 6h18M3 12h18M3 18h18" />
  </svg>
);

export const IcSun = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);

export const IcMoon = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
);

export const IcGlobe = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18z" />
  </svg>
);

export const IcSearch = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

export const IcPlus = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const IcDownload = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M12 3v12M7 11l5 5 5-5M4 20h16" />
  </svg>
);

export const IcAlert = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <path d="M12 9v4M12 17h.01" />
  </svg>
);

export const IcCheck = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="m4 12 5 5L20 6" />
  </svg>
);

export const IcX = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);

export const IcChevron = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="m9 6 6 6-6 6" />
  </svg>
);

export const IcLogout = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
  </svg>
);

export const IcUser = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21a8 8 0 0 1 16 0" />
  </svg>
);

export const IcShield = ({ size = 20, className }: P) => (
  <svg {...base(size)} className={className}>
    <path d="M12 3l8 3v6c0 4.4-3.2 7.9-8 9-4.8-1.1-8-4.6-8-9V6z" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);
