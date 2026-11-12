import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import type { AnnouncementAttachment } from "@/lib/announcementAttachments"
import AnnouncementMedia, { AnnouncementMediaPreview } from "./AnnouncementMedia"

const image = (id: string, name: string): AnnouncementAttachment => ({
  id, attachment_type: "image", original_filename: name, file_size: 1000, content_type: "image/png",
  url: `https://signed.example/${id}.png`, download_path: `/announcements/7/attachments/${id}/download/`,
})
const document = (id: string, name: string, size: number): AnnouncementAttachment => ({
  id, attachment_type: "document", original_filename: name, file_size: size, content_type: "application/pdf",
  url: "", download_path: `/announcements/7/attachments/${id}/download/`,
})

describe("AnnouncementMedia (the detail view)", () => {
  it("shows nothing when there is nothing attached", () => {
    expect(renderToStaticMarkup(<AnnouncementMedia />)).toBe("")
    expect(renderToStaticMarkup(<AnnouncementMedia attachments={[]} links={[]} />)).toBe("")
  })

  it("shows every picture with alt text, opening the full picture in a new tab", () => {
    const html = renderToStaticMarkup(<AnnouncementMedia attachments={[image("a", "front.png"), image("b", "back.png")]} />)
    expect(html).toContain('src="https://signed.example/a.png"')
    expect(html).toContain('alt="front.png"')
    expect(html).toContain('alt="back.png"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it("shows each PDF with its file name, its size and a download button to the authorised endpoint", () => {
    const html = renderToStaticMarkup(<AnnouncementMedia attachments={[document("p", "Leave policy.pdf", 2 * 1024 * 1024 + 300000)]} />)
    expect(html).toContain("Leave policy.pdf")
    expect(html).toContain("2.3 MB")
    expect(html).toContain('href="/api/announcements/7/attachments/p/download/"')
    expect(html).toContain('aria-label="Download Leave policy.pdf"')
  })

  it("shows links as buttons that open in a new tab", () => {
    const html = renderToStaticMarkup(<AnnouncementMedia links={[{ title: "Handbook", url: "https://example.com/handbook" }]} />)
    expect(html).toContain('href="https://example.com/handbook"')
    expect(html).toContain("Handbook")
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it("never makes a clickable link out of an unsafe address, and escapes titles", () => {
    const html = renderToStaticMarkup(<AnnouncementMedia links={[{ title: "Sneaky", url: "javascript:alert(1)" }, { title: "<b>Bold</b>", url: "https://ok.example.com" }]} />)
    expect(html).not.toContain("javascript:")
    expect(html).toContain("Sneaky")
    expect(html).toContain("&lt;b&gt;Bold&lt;/b&gt;")
    expect(html).not.toContain("<b>Bold</b>")
  })
})

describe("AnnouncementMediaPreview (the list card)", () => {
  it("shows the first picture and counts what else is attached", () => {
    const html = renderToStaticMarkup(
      <AnnouncementMediaPreview attachments={[image("a", "front.png"), image("b", "back.png"), document("p", "x.pdf", 10)]} links={[{ title: "A", url: "https://a.example.com" }]} />,
    )
    expect(html).toContain('src="https://signed.example/a.png"')
    expect(html).not.toContain("back.png")
    expect(html).toContain("2 images")
    expect(html).toContain("1 PDF")
    expect(html).toContain("1 link")
  })
  it("renders nothing for an announcement without attachments", () => {
    expect(renderToStaticMarkup(<AnnouncementMediaPreview />)).toBe("")
  })
})
