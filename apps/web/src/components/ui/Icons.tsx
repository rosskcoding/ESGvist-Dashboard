import type { CSSProperties, ReactNode } from 'react'

type IconProps = {
  size?: number
  className?: string
  style?: CSSProperties
  title?: string
}

function SvgIcon({
  size = 18,
  className,
  style,
  title,
  children,
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
    >
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  )
}

export function IconChartBar(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M4 20V10" />
      <path d="M9 20V4" />
      <path d="M14 20v-8" />
      <path d="M19 20v-13" />
    </SvgIcon>
  )
}

export function IconBuilding(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M4 20V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v14" />
      <path d="M8 8h4" />
      <path d="M8 12h4" />
      <path d="M8 16h4" />
      <path d="M18 20V10h2a0 0 0 0 1 0 0v10" />
    </SvgIcon>
  )
}

export function IconSettings(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z" />
      <path d="M19.4 15a1.8 1.8 0 0 0 .36 1.98l.03.03a2.2 2.2 0 0 1-1.56 3.74h-.05a1.8 1.8 0 0 0-1.67 1.2 1.8 1.8 0 0 0-.42.76v.05a2.2 2.2 0 0 1-4.2 0v-.05a1.8 1.8 0 0 0-.42-.76A1.8 1.8 0 0 0 9.78 20.8h-.05A2.2 2.2 0 0 1 8.17 17l.03-.03A1.8 1.8 0 0 0 8.56 15a1.8 1.8 0 0 0-.36-1.98l-.03-.03A2.2 2.2 0 0 1 9.73 9.25h.05A1.8 1.8 0 0 0 11.45 8a1.8 1.8 0 0 0 .42-.76v-.05a2.2 2.2 0 0 1 4.2 0v.05a1.8 1.8 0 0 0 .42.76 1.8 1.8 0 0 0 1.67 1.2h.05a2.2 2.2 0 0 1 1.56 3.74l-.03.03A1.8 1.8 0 0 0 19.4 15z" />
    </SvgIcon>
  )
}

export function IconMenu(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </SvgIcon>
  )
}

export function IconMoreHorizontal(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="5" cy="12" r="1" />
      <circle cx="12" cy="12" r="1" />
      <circle cx="19" cy="12" r="1" />
    </SvgIcon>
  )
}

export function IconUser(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M20 21a8 8 0 0 0-16 0" />
      <circle cx="12" cy="7" r="4" />
    </SvgIcon>
  )
}

export function IconLogOut(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </SvgIcon>
  )
}

export function IconArrowLeft(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M19 12H5" />
      <path d="M12 19l-7-7 7-7" />
    </SvgIcon>
  )
}

export function IconArrowRight(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M5 12h14" />
      <path d="M12 5l7 7-7 7" />
    </SvgIcon>
  )
}

export function IconPackage(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M16.5 9.4L7.6 4.3" />
      <path d="M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.7z" />
      <path d="M3.3 7.9L12 13l8.7-5.1" />
      <path d="M12 22V13" />
    </SvgIcon>
  )
}

export function IconClock(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </SvgIcon>
  )
}

export function IconMessageCircle(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H7l-4 2 1.2-3.6A8.5 8.5 0 1 1 21 11.5z" />
    </SvgIcon>
  )
}

export function IconGlobe(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a14 14 0 0 1 0 18" />
      <path d="M12 3a14 14 0 0 0 0 18" />
    </SvgIcon>
  )
}

export function IconX(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M18 6L6 18" />
      <path d="M6 6l12 12" />
    </SvgIcon>
  )
}

export function IconCheck(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M20 6L9 17l-5-5" />
    </SvgIcon>
  )
}

export function IconAlertTriangle(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M10.3 4.2L2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </SvgIcon>
  )
}

export function IconSearch(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.2-3.2" />
    </SvgIcon>
  )
}

export function IconTrash(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M3 6h18" />
      <path d="M8 6V4h8v2" />
      <path d="M6 6l1 16h10l1-16" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
    </SvgIcon>
  )
}

export function IconPencil(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4 11.5-11.5z" />
    </SvgIcon>
  )
}

export function IconUsers(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M17 21a5 5 0 0 0-10 0" />
      <circle cx="12" cy="8" r="3.5" />
      <path d="M22 21a4.5 4.5 0 0 0-7-3.8" />
      <path d="M9 17.2A4.5 4.5 0 0 0 2 21" />
    </SvgIcon>
  )
}

export function IconFileText(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h8" />
      <path d="M8 17h8" />
      <path d="M8 9h2" />
    </SvgIcon>
  )
}

export function IconTable(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M3 6h18" />
      <path d="M3 10h18" />
      <path d="M3 14h18" />
      <path d="M3 18h18" />
      <path d="M8 6v12" />
      <path d="M16 6v12" />
      <rect x="3" y="6" width="18" height="12" rx="2" />
    </SvgIcon>
  )
}

export function IconImage(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M8 13l2.5-3 3 4 2-2.5L21 19" />
      <circle cx="9" cy="9" r="1.3" />
    </SvgIcon>
  )
}

export function IconQuote(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M7 17h4V7H6v6h1a2 2 0 0 1 2 2v2z" />
      <path d="M17 17h4V7h-5v6h1a2 2 0 0 1 2 2v2z" />
    </SvgIcon>
  )
}

export function IconDownload(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M12 3v10" />
      <path d="M8 11l4 4 4-4" />
      <path d="M4 21h16" />
    </SvgIcon>
  )
}

export function IconList(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M8 6h13" />
      <path d="M8 12h13" />
      <path d="M8 18h13" />
      <path d="M3 6h.01" />
      <path d="M3 12h.01" />
      <path d="M3 18h.01" />
    </SvgIcon>
  )
}

export function IconVideo(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <rect x="3" y="7" width="15" height="10" rx="2" />
      <path d="M18 10l3-2v8l-3-2z" />
    </SvgIcon>
  )
}

export function IconMegaphone(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M3 11v2a2 2 0 0 0 2 2h2l5 4V5L7 9H5a2 2 0 0 0-2 2z" />
      <path d="M16 9a4 4 0 0 1 0 6" />
      <path d="M18.5 7.5a7 7 0 0 1 0 9" />
    </SvgIcon>
  )
}

export function IconRefresh(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M21 12a9 9 0 0 1-15.4 6.4" />
      <path d="M3 12a9 9 0 0 1 15.4-6.4" />
      <path d="M21 3v6h-6" />
      <path d="M3 21v-6h6" />
    </SvgIcon>
  )
}

export function IconPlus(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </SvgIcon>
  )
}

export function IconSun(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="M4.9 4.9l1.4 1.4" />
      <path d="M17.7 17.7l1.4 1.4" />
      <path d="M19.1 4.9l-1.4 1.4" />
      <path d="M6.3 17.7l-1.4 1.4" />
    </SvgIcon>
  )
}

export function IconMoon(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M21 12.8A8.5 8.5 0 0 1 11.2 3a6.8 6.8 0 1 0 9.8 9.8z" />
    </SvgIcon>
  )
}

export function IconBookOpen(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M2 4.5A2.5 2.5 0 0 1 4.5 2H11v18H4.5A2.5 2.5 0 0 0 2 22V4.5z" />
      <path d="M22 4.5A2.5 2.5 0 0 0 19.5 2H13v18h6.5A2.5 2.5 0 0 1 22 22V4.5z" />
      <path d="M11 6h2" />
    </SvgIcon>
  )
}

export function IconLock(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </SvgIcon>
  )
}

export function IconMapPin(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M12 21s7-4.5 7-11a7 7 0 1 0-14 0c0 6.5 7 11 7 11z" />
      <circle cx="12" cy="10" r="2.5" />
    </SvgIcon>
  )
}

export function IconLightbulb(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M9 18h6" />
      <path d="M10 22h4" />
      <path d="M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 3H9c0-1 0-2-1-3z" />
    </SvgIcon>
  )
}

export function IconZap(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" />
    </SvgIcon>
  )
}

export function IconFolder(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M3 7a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
    </SvgIcon>
  )
}

export function IconEye(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </SvgIcon>
  )
}

export function IconUnlock(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 7.5-2" />
    </SvgIcon>
  )
}

export function IconLink(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M10 13a5 5 0 0 1 0-7l1.5-1.5a5 5 0 0 1 7 7L17 13" />
      <path d="M14 11a5 5 0 0 1 0 7L12.5 19.5a5 5 0 0 1-7-7L7 11" />
    </SvgIcon>
  )
}

export function IconPaperclip(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <path d="M21.44 11.05l-8.49 8.49a5 5 0 0 1-7.07-7.07l9.19-9.19a3.5 3.5 0 0 1 4.95 4.95l-9.19 9.19a2 2 0 1 1-2.83-2.83l8.49-8.49" />
    </SvgIcon>
  )
}

export function IconInfo(props: IconProps) {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 10v6" />
      <path d="M12 7h.01" />
    </SvgIcon>
  )
}
