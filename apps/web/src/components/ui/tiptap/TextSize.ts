import { Mark, mergeAttributes } from '@tiptap/core'

export type TextSizeValue = 'sm' | 'lg'

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    textSize: {
      setTextSize: (size: TextSizeValue) => ReturnType
      unsetTextSize: () => ReturnType
      toggleTextSize: (size: TextSizeValue) => ReturnType
    }
  }
}

// Inline text sizing for emphasis. We use classes (not style="...") because
// backend HTML sanitization strips inline styles.
export const TextSize = Mark.create({
  name: 'textSize',

  addAttributes() {
    return {
      size: {
        default: null,
        rendered: false,
      },
    }
  },

  parseHTML() {
    return [
      {
        tag: 'span.rpt-text--sm',
        getAttrs: () => ({ size: 'sm' }),
      },
      {
        tag: 'span.rpt-text--lg',
        getAttrs: () => ({ size: 'lg' }),
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    const size = HTMLAttributes.size as TextSizeValue | null | undefined
    const attrs = { ...HTMLAttributes }
    delete (attrs as Record<string, unknown>).size

    const sizeClass =
      size === 'sm' ? 'rpt-text--sm' : size === 'lg' ? 'rpt-text--lg' : null

    const mergedClass = [attrs.class, sizeClass].filter(Boolean).join(' ')

    return [
      'span',
      mergeAttributes(attrs, mergedClass ? { class: mergedClass } : {}),
      0,
    ]
  },

  addCommands() {
    return {
      setTextSize:
        (size) =>
        ({ commands }) =>
          commands.setMark(this.name, { size }),
      unsetTextSize:
        () =>
        ({ commands }) =>
          commands.unsetMark(this.name),
      toggleTextSize:
        (size) =>
        ({ editor, commands }) => {
          if (editor.isActive(this.name, { size })) {
            return commands.unsetMark(this.name)
          }
          return commands.setMark(this.name, { size })
        },
    }
  },
})
