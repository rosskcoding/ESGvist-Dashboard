import { useEditor, EditorContent, Editor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import { useEffect, useCallback } from 'react'
import styles from './RichTextEditor.module.css'
import { IconLink, IconQuote, IconX } from './Icons'
import { TextSize } from './tiptap/TextSize'

interface RichTextEditorProps {
  value: string
  onChange: (html: string) => void
  placeholder?: string
  minHeight?: number
}

export function RichTextEditor({
  value,
  onChange,
  placeholder = 'Enter text...',
  minHeight = 200,
}: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3, 4],
        },
      }),
      TextSize,
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          rel: 'noopener noreferrer',
        },
      }),
      Placeholder.configure({
        placeholder,
      }),
    ],
    content: value,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML())
    },
  })

  // Sync external value changes
  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      editor.commands.setContent(value, false)
    }
  }, [value, editor])

  if (!editor) {
    return null
  }

  return (
    <div className={styles.editor}>
      <Toolbar editor={editor} />
      <EditorContent
        editor={editor}
        className={styles.content}
        style={{ minHeight }}
      />
    </div>
  )
}

function Toolbar({ editor }: { editor: Editor }) {
  const setLink = useCallback(() => {
    const previousUrl = editor.getAttributes('link').href
    const url = window.prompt('Link URL:', previousUrl)

    if (url === null) return

    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run()
      return
    }

    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
  }, [editor])

  return (
    <div className={styles.toolbar}>
      <div className={styles.toolbarGroup}>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          className={`${styles.toolbarBtn} ${editor.isActive('heading', { level: 2 }) ? styles.active : ''}`}
          title="Heading H2 (applies to the whole paragraph)"
        >
          H2
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
          className={`${styles.toolbarBtn} ${editor.isActive('heading', { level: 3 }) ? styles.active : ''}`}
          title="Heading H3 (applies to the whole paragraph)"
        >
          H3
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleHeading({ level: 4 }).run()}
          className={`${styles.toolbarBtn} ${editor.isActive('heading', { level: 4 }) ? styles.active : ''}`}
          title="Heading H4 (applies to the whole paragraph)"
        >
          H4
        </button>
      </div>

      <div className={styles.divider} />

      <div className={styles.toolbarGroup}>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleTextSize('sm').run()}
          className={`${styles.toolbarBtn} ${styles.toolbarBtnWide} ${editor.isActive('textSize', { size: 'sm' }) ? styles.active : ''}`}
          title="Smaller text"
        >
          A-
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleTextSize('lg').run()}
          className={`${styles.toolbarBtn} ${styles.toolbarBtnWide} ${editor.isActive('textSize', { size: 'lg' }) ? styles.active : ''}`}
          title="Larger text"
        >
          A+
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBold().run()}
          className={`${styles.toolbarBtn} ${editor.isActive('bold') ? styles.active : ''}`}
          title="Bold (Ctrl+B)"
        >
          <strong>B</strong>
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleItalic().run()}
          className={`${styles.toolbarBtn} ${editor.isActive('italic') ? styles.active : ''}`}
          title="Italic (Ctrl+I)"
        >
          <em>I</em>
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleStrike().run()}
          className={`${styles.toolbarBtn} ${editor.isActive('strike') ? styles.active : ''}`}
          title="Strikethrough"
        >
          <s>S</s>
        </button>
      </div>

      <div className={styles.divider} />

      <div className={styles.toolbarGroup}>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          className={`${styles.toolbarBtn} ${editor.isActive('bulletList') ? styles.active : ''}`}
          title="Bulleted list"
        >
          •
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          className={`${styles.toolbarBtn} ${editor.isActive('orderedList') ? styles.active : ''}`}
          title="Numbered list"
        >
          1.
        </button>
      </div>

      <div className={styles.divider} />

      <div className={styles.toolbarGroup}>
        <button
          type="button"
          onClick={setLink}
          className={`${styles.toolbarBtn} ${editor.isActive('link') ? styles.active : ''}`}
          title="Insert link"
        >
          <IconLink size={16} />
        </button>
        {editor.isActive('link') && (
          <button
            type="button"
            onClick={() => editor.chain().focus().unsetLink().run()}
            className={styles.toolbarBtn}
            title="Remove link"
          >
            <IconX size={16} />
          </button>
        )}
      </div>

      <div className={styles.divider} />

      <div className={styles.toolbarGroup}>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          className={`${styles.toolbarBtn} ${editor.isActive('blockquote') ? styles.active : ''}`}
          title="Quote"
        >
          <IconQuote size={16} />
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().setHorizontalRule().run()}
          className={styles.toolbarBtn}
          title="Horizontal line"
        >
          —
        </button>
      </div>

      <div className={styles.spacer} />

      <div className={styles.toolbarGroup}>
        <button
          type="button"
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          className={styles.toolbarBtn}
          title="Undo (Ctrl+Z)"
        >
          ↶
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          className={styles.toolbarBtn}
          title="Redo (Ctrl+Y)"
        >
          ↷
        </button>
      </div>
    </div>
  )
}
