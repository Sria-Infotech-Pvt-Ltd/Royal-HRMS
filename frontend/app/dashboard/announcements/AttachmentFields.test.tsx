import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { addLink, emptyDraft, removeExisting, updateLink, type AnnouncementAttachment, type AttachmentDraft } from "@/lib/announcementAttachments"
import AttachmentFields, { ImageTile } from "./AttachmentFields"

const saved = (id: string, kind: "image" | "document", name: string, size = 3 * 1024): AnnouncementAttachment => ({
  id, attachment_type: kind, original_filename: name, file_size: size, content_type: kind === "image" ? "image/png" : "application/pdf",
  url: kind === "image" ? `https://signed.example/${id}.png` : "", download_path: `/announcements/7/attachments/${id}/download/`,
})

const render = (draft: AttachmentDraft, props: { showLinkErrors?: boolean; uploadProgress?: number | null } = {}) =>
  renderToStaticMarkup(<AttachmentFields draft={draft} onChange={() => {}} {...props} />)

describe("AttachmentFields", () => {
  it("starts as three small icon buttons with their limits, and nothing else", () => {
    const html = render(emptyDraft())
    expect(html).toContain('aria-label="Add images"')
    expect(html).toContain('aria-label="Add PDF"')
    expect(html).toContain('aria-label="Add link"')
    expect(html).toContain("JPG, PNG or WebP, up to 5 MB each, 0/5")
    expect(html).toContain("PDF, up to 5 MB each, 0/5")
    expect(html).toContain('accept="image/jpeg,image/png,image/webp"')
    expect(html).toContain('accept="application/pdf"')
    // no big empty boxes: nothing is shown until something is added
    expect(html).not.toContain("Drag images here")
    expect(html).not.toContain("Link title")
    expect(html).not.toContain("<img")
  })

  it("shows how many are attached and stops offering more at the limit", () => {
    const five = Array.from({ length: 5 }, (_, index) => saved(`i${index}`, "image", `${index}.png`))
    const html = render({ ...emptyDraft(), existing: five })
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*aria-label="Add images"/)
    expect(html).toContain("5/5")
    expect(render(emptyDraft())).not.toMatch(/<button[^>]*disabled=""[^>]*aria-label="Add images"/)
  })

  it("shows saved pictures as thumbnails with a remove button", () => {
    const html = render({ ...emptyDraft(), existing: [saved("a", "image", "front.png"), saved("b", "image", "back.png")] })
    expect(html).toContain('src="https://signed.example/a.png"')
    expect(html).toContain('alt="front.png"')
    expect(html).toContain('aria-label="Remove image back.png"')
    expect(html).toContain("2/5")
  })

  it("shows saved PDFs with name, size, a download link and a remove button", () => {
    const html = render({ ...emptyDraft(), existing: [saved("p", "document", "Leave policy.pdf", 3 * 1024)] })
    expect(html).toContain("Leave policy.pdf")
    expect(html).toContain("3 KB")
    expect(html).toContain('href="/api/announcements/7/attachments/p/download/"')
    expect(html).toContain('aria-label="Remove Leave policy.pdf"')
  })

  it("hides an attachment that was marked for removal and frees its place", () => {
    const draft = removeExisting({ ...emptyDraft(), existing: [saved("a", "image", "front.png"), saved("p", "document", "x.pdf")] }, "a")
    const html = render(draft)
    expect(html).not.toContain("front.png")
    expect(html).toContain("0/5")
    expect(html).toContain("x.pdf")
  })

  it("shows newly picked PDFs with their size and that they upload on publish", () => {
    const html = render({ ...emptyDraft(), newDocuments: [new File([new Uint8Array(2048)], "agenda.pdf", { type: "application/pdf" })] })
    expect(html).toContain("agenda.pdf")
    expect(html).toContain("2 KB")
    expect(html).toContain("will be uploaded when you publish")
  })

  it("shows link rows with their values and a remove button", () => {
    const draft = (() => {
      const withRow = addLink(emptyDraft())
      return updateLink(withRow, withRow.links[0].key, { title: "Handbook", url: "https://example.com/handbook" })
    })()
    const html = render(draft)
    expect(html).toContain('value="Handbook"')
    expect(html).toContain('value="https://example.com/handbook"')
    expect(html).toContain('aria-label="Remove link 1"')
    expect(html).not.toContain("field-error-msg")
  })

  it("explains an invalid link straight away, and empty rows only after a save attempt", () => {
    const row = (title: string, url: string) => {
      const withRow = addLink(emptyDraft())
      return updateLink(withRow, withRow.links[0].key, { title, url })
    }
    expect(render(row("Map", "javascript:alert(1)"))).toContain("Enter a valid address starting with http:// or https://.")
    expect(render(addLink(emptyDraft()))).not.toContain("Enter a title")
    const afterSave = render(addLink(emptyDraft()), { showLinkErrors: true })
    expect(afterSave).toContain("Enter a title for the link.")
    expect(afterSave).toContain("Enter the web address.")
  })

  it("shows upload progress only while uploading", () => {
    expect(render(emptyDraft())).not.toContain("Uploading")
    const html = render(emptyDraft(), { uploadProgress: 42 })
    expect(html).toContain("Uploading… 42%")
    expect(html).toContain("width:42%")
  })
})

describe("ImageTile", () => {
  it("shows the preview picture with a remove button", () => {
    const html = renderToStaticMarkup(<ImageTile src="blob:preview-1" name="new.png" onRemove={() => {}} />)
    expect(html).toContain('src="blob:preview-1"')
    expect(html).toContain('alt="new.png"')
    expect(html).toContain('aria-label="Remove image new.png"')
  })
  it("shows a placeholder until the browser has made the preview", () => {
    const html = renderToStaticMarkup(<ImageTile src={null} name="new.png" onRemove={() => {}} />)
    expect(html).not.toContain("<img")
    expect(html).toContain("ti-photo")
  })
})
