import { useEditor, EditorContent, type Editor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Link from '@tiptap/extension-link'
import { Markdown } from 'tiptap-markdown'
import { useEffect, type CSSProperties } from 'react'

const getMarkdown = (editor: Editor): string => (editor.storage as unknown as { markdown: { getMarkdown(): string } }).markdown.getMarkdown()

interface RichTextEditorProps {
  value: string
  onChange: (markdown: string) => void
  placeholder?: string
  disabled?: boolean
  style?: CSSProperties
}

const TOOLBAR_BTN: CSSProperties = {
  border: 0, background: 'transparent', cursor: 'pointer',
  padding: '3px 7px', borderRadius: 4, fontSize: 12, color: 'var(--fg-2)', lineHeight: 1.4,
}

/** Minimal WYSIWYG editor; stores/reads Markdown so it stays compatible with the portal's marked+DOMPurify renderer. */
export function RichTextEditor({ value, onChange, placeholder, disabled, style }: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Link.configure({ openOnClick: false, autolink: true }),
      Markdown.configure({ html: false }),
    ],
    content: value,
    editable: !disabled,
    onUpdate: ({ editor }) => onChange(getMarkdown(editor)),
    editorProps: {
      attributes: { class: 'fld richtext-editor', style: 'min-height: 76px; padding: 8px 10px;' },
    },
  })

  useEffect(() => {
    if (editor && value !== getMarkdown(editor)) {
      editor.commands.setContent(value, { emitUpdate: false })
    }
  }, [value])

  useEffect(() => {
    editor?.setEditable(!disabled)
  }, [editor, disabled])

  if (!editor) return null

  const btn = (active: boolean, onClick: () => void, label: string, title: string) => (
    <button type="button" style={{ ...TOOLBAR_BTN, background: active ? 'var(--accent-50)' : undefined, color: active ? 'var(--accent-ink)' : TOOLBAR_BTN.color, fontWeight: active ? 700 : 400 }} onClick={onClick} title={title} disabled={disabled}>
      {label}
    </button>
  )

  return (
    <div style={style}>
      <div style={{ display: 'flex', gap: 2, marginBottom: 4, flexWrap: 'wrap' }}>
        {btn(editor.isActive('bold'), () => editor.chain().focus().toggleBold().run(), 'B', 'Fett')}
        {btn(editor.isActive('italic'), () => editor.chain().focus().toggleItalic().run(), 'I', 'Kursiv')}
        {btn(editor.isActive('heading', { level: 2 }), () => editor.chain().focus().toggleHeading({ level: 2 }).run(), 'H2', 'Überschrift')}
        {btn(editor.isActive('heading', { level: 3 }), () => editor.chain().focus().toggleHeading({ level: 3 }).run(), 'H3', 'Unterüberschrift')}
        {btn(editor.isActive('bulletList'), () => editor.chain().focus().toggleBulletList().run(), '•', 'Liste')}
        {btn(editor.isActive('orderedList'), () => editor.chain().focus().toggleOrderedList().run(), '1.', 'Nummerierte Liste')}
        {btn(editor.isActive('link'), () => {
          if (editor.isActive('link')) { editor.chain().focus().unsetLink().run(); return }
          const url = window.prompt('URL:')
          if (url) editor.chain().focus().setLink({ href: url }).run()
        }, 'Link', 'Link')}
      </div>
      <EditorContent editor={editor} placeholder={placeholder} />
    </div>
  )
}
