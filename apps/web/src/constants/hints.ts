/**
 * UI tooltips used across the application.
 * Centralized to keep wording consistent.
 */

export const HINTS = {
  // === Header / Navigation ===
  header: {
    backToReports: 'Back to the full report list',
    reportYear: 'Reporting period year',
    reportTitle: 'Report title',
    localeSwitch: 'Switch content editing locale',
    sourceLocale: 'Source locale (green dot)',
    structureBtn: 'Manage report table of contents structure',
    releasesBtn: 'Create and download builds (ZIP)',
    translationBtn: 'Auto-translate content to other locales',
    previewBtn: 'Preview current section (ESC to close)',
    logoutBtn: 'Sign out',
  },

  // === Sidebar / Sections ===
  sections: {
    title: 'Report sections list. Sections are report chapters',
    addSection: 'Create a new section',
    sectionItem: 'Click to open block editor',
    sectionFolder: 'Section with nested subsections',
    sectionFile: 'Section without nested subsections',
    sectionCount: 'Number of content blocks in section',
    editSection: 'Edit section title and settings',
    deleteSection: 'Delete section and all nested blocks',
    labelPrefix: 'TOC number/prefix (e.g. "1.", "09")',
  },

  // === Blocks ===
  blocks: {
    title: 'Content blocks of the selected section',
    addBlock: 'Add a new content block',
    blockType: 'Block type defines structure and rendering',
    blockVariant: 'Display variant: compact, accent, etc.',
    editBlock: 'Edit block content',
    deleteBlock: 'Delete block',
    moveUp: 'Move block up',
    moveDown: 'Move block down',
    status: 'Content readiness status (draft/ready/approved)',
  },

  // === Block Types ===
  blockTypes: {
    text: 'Text block with formatting (headings, lists, links)',
    kpi_cards: 'Key KPI metric cards',
    table: 'Data table',
    chart: 'Chart or graph',
    image: 'Image with caption',
    video: 'Video content',
    quote: 'Quote with author attribution',
    downloads: 'List of downloadable files',
    accordion: 'Expandable list (FAQ)',
    timeline: 'Event timeline',
    custom: 'Custom HTML content',
  },

  // === Properties Panel ===
  properties: {
    title: 'Properties of the selected item',
    theme: 'Theme used for report export',
    sectionTitle: 'Section title in current locale',
    sectionSlug: 'Section URL identifier (for navigation)',
    blocksCount: 'Total block count in section',
  },

  // === Releases ===
  releases: {
    title: 'Builds are downloadable report versions (ESC to close)',
    newRelease: 'Create a new build (draft or release)',
    buildType: 'Draft for QA, Release for final output',
    buildStatus: 'Build status: queued/running/ready/failed',
    download: 'Download ZIP archive with static website',
    locales: 'Locales included in this build',
  },

  // === Translation ===
  translation: {
    title: 'Automatic content translation (ESC to close)',
    sourceLocale: 'Source locale for translation',
    targetLocales: 'Target locales',
    startTranslation: 'Start auto-translation for selected content',
    progress: 'Translation progress by locale',
  },

  // === Structure Page ===
  structure: {
    title: 'Manage report table of contents structure',
    tocPreview: 'TOC preview. Click to open in editor',
    sectionTree: 'Flat section list. Drag to reorder',
    addRootSection: 'Add top-level section',
    addChildSection: 'Add subsection (max 4 levels)',
    dragHandle: 'Drag to reorder sections',
    depth: 'Nesting level (1-4)',
    labelPrefix: 'TOC prefix: "1.", "09", "A."',
    labelSuffix: 'TOC suffix: "(p. 5)"',
  },

  // === Forms ===
  forms: {
    required: 'Required field',
    optional: 'Optional field',
    save: 'Save changes',
    cancel: 'Cancel and close',
    create: 'Create new item',
  },

  // === Dashboard ===
  dashboard: {
    title: 'List of all reports in the system',
    createReport: 'Create a new report',
    reportCard: 'Report card. Click to open editor',
    reportYear: 'Reporting period year',
    reportSections: 'Number of report sections',
    reportBlocks: 'Total number of content blocks',
    deleteReport: 'Delete report (irreversible)',
  },

  // === Rich Text Editor ===
  editor: {
    bold: 'Bold text (Ctrl+B)',
    italic: 'Italic text (Ctrl+I)',
    underline: 'Underline (Ctrl+U)',
    strike: 'Strikethrough',
    heading1: 'Heading H1',
    heading2: 'Heading H2',
    heading3: 'Heading H3',
    bulletList: 'Bulleted list',
    orderedList: 'Numbered list',
    link: 'Insert link',
    code: 'Code (monospace font)',
    blockquote: 'Quote block',
    horizontalRule: 'Horizontal line',
    undo: 'Undo (Ctrl+Z)',
    redo: 'Redo (Ctrl+Shift+Z)',
  },
} as const

export type HintKey = keyof typeof HINTS
