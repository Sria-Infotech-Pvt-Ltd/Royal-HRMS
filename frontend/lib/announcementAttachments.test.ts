import { describe, expect, it } from "vitest"
import {
  MAX_DOCUMENTS, MAX_FILE_BYTES, MAX_IMAGES, MAX_LINKS,
  addFiles, addLink, announcementDownloadHref, buildAnnouncementFormData, checkFile, documentCount, draftErrors,
  draftFromAnnouncement, emptyDraft, formatFileSize, imageCount, isSafeHttpUrl, linkProblems, removeExisting, removeLink,
  removeNew, updateLink, type AnnouncementAttachment,
} from "./announcementAttachments"

const png = (name = "a.png", size = 1000) => new File([new Uint8Array(size)], name, { type: "image/png" })
const pdf = (name = "a.pdf", size = 1000) => new File([new Uint8Array(size)], name, { type: "application/pdf" })

const saved = (id: string, kind: "image" | "document", name: string): AnnouncementAttachment => ({
  id, attachment_type: kind, original_filename: name, file_size: 2048, content_type: kind === "image" ? "image/png" : "application/pdf",
  url: kind === "image" ? `https://signed.example/${id}` : "", download_path: `/announcements/1/attachments/${id}/download/`,
})

describe("formatFileSize", () => {
  it("shows bytes, kilobytes and megabytes", () => {
    expect(formatFileSize(500)).toBe("500 B")
    expect(formatFileSize(2048)).toBe("2 KB")
    expect(formatFileSize(5 * 1024 * 1024)).toBe("5.0 MB")
  })
})

describe("checkFile", () => {
  it("accepts JPG, PNG and WebP images and PDFs", () => {
    expect(checkFile({ name: "a.JPG", size: 10, type: "image/jpeg" }, "image")).toBeNull()
    expect(checkFile({ name: "a.jpeg", size: 10, type: "image/jpeg" }, "image")).toBeNull()
    expect(checkFile({ name: "a.png", size: 10, type: "image/png" }, "image")).toBeNull()
    expect(checkFile({ name: "a.webp", size: 10, type: "image/webp" }, "image")).toBeNull()
    expect(checkFile({ name: "a.pdf", size: 10, type: "application/pdf" }, "document")).toBeNull()
  })
  it("refuses other types, a wrong extension, empty and oversized files", () => {
    expect(checkFile({ name: "a.gif", size: 10, type: "image/gif" }, "image")).toContain("not accepted")
    expect(checkFile({ name: "a.png", size: 10, type: "image/jpeg" }, "image")).toContain("not accepted")
    expect(checkFile({ name: "a.exe", size: 10, type: "application/pdf" }, "document")).toContain("not accepted")
    expect(checkFile({ name: "a.pdf", size: 10, type: "image/png" }, "image")).toContain("not accepted")
    expect(checkFile({ name: "noextension", size: 10, type: "image/png" }, "image")).toContain("not accepted")
    expect(checkFile({ name: "a.png", size: 0, type: "image/png" }, "image")).toContain("empty")
    expect(checkFile({ name: "big.pdf", size: MAX_FILE_BYTES + 1, type: "application/pdf" }, "document")).toContain("5 MB")
  })
})

describe("adding and removing files", () => {
  it("adds valid files and reports each refused one", () => {
    const result = addFiles(emptyDraft(), "image", [png("ok.png"), new File(["x"], "bad.gif", { type: "image/gif" })])
    expect(result.draft.newImages.map(file => file.name)).toEqual(["ok.png"])
    expect(result.errors).toHaveLength(1)
    expect(result.errors[0]).toContain("bad.gif")
  })
  it("stops at five images and five PDFs, counting what is already saved", () => {
    const six = Array.from({ length: 6 }, (_, index) => png(`${index}.png`))
    const images = addFiles(emptyDraft(), "image", six)
    expect(images.draft.newImages).toHaveLength(MAX_IMAGES)
    expect(images.errors[0]).toContain("at most 5 images")

    const withSaved = { ...emptyDraft(), existing: [saved("1", "document", "x.pdf"), saved("2", "document", "y.pdf"), saved("3", "document", "z.pdf"), saved("4", "document", "w.pdf")] }
    const documents = addFiles(withSaved, "document", [pdf("a.pdf"), pdf("b.pdf")])
    expect(documents.draft.newDocuments).toHaveLength(MAX_DOCUMENTS - 4)
    expect(documentCount(documents.draft)).toBe(MAX_DOCUMENTS)
    expect(documents.errors[0]).toContain("b.pdf")
  })
  it("removing a saved attachment makes room and is remembered by id", () => {
    let draft = { ...emptyDraft(), existing: [saved("1", "image", "a.png"), saved("2", "image", "b.png")] }
    expect(imageCount(draft)).toBe(2)
    draft = removeExisting(removeExisting(draft, "1"), "1")
    expect(draft.removedIds).toEqual(["1"])
    expect(imageCount(draft)).toBe(1)
  })
  it("removes a newly picked file by position", () => {
    const draft = addFiles(emptyDraft(), "document", [pdf("a.pdf"), pdf("b.pdf")]).draft
    expect(removeNew(draft, "document", 0).newDocuments.map(file => file.name)).toEqual(["b.pdf"])
  })
})

describe("links", () => {
  it("accepts only plain http(s) addresses", () => {
    for (const ok of ["https://example.com", "http://intranet.local/form?id=1#top", " https://example.com/a "]) expect(isSafeHttpUrl(ok)).toBe(true)
    for (const bad of ["", "example.com", "javascript:alert(1)", "data:text/html,x", "ftp://example.com", "https://", "https://user:pw@example.com", "https://exa mple.com", `https://example.com/${"a".repeat(500)}`]) {
      expect(isSafeHttpUrl(bad)).toBe(false)
    }
  })
  it("asks for a title and an address, but only nags about empty rows when saving", () => {
    expect(linkProblems({ title: "", url: "" }, false)).toEqual({})
    expect(linkProblems({ title: "", url: "" }, true)).toEqual({ title: "Enter a title for the link.", url: "Enter the web address." })
    expect(linkProblems({ title: "Map", url: "" }, false).url).toBe("Enter the web address.")
    expect(linkProblems({ title: "", url: "https://example.com" }, false).title).toBe("Enter a title for the link.")
    expect(linkProblems({ title: "Map", url: "nope" }, false).url).toContain("http://")
    expect(linkProblems({ title: "x".repeat(101), url: "https://example.com" }, false).title).toContain("100")
    expect(linkProblems({ title: "Map", url: "https://example.com" }, true)).toEqual({})
  })
  it("adds, edits and removes link rows, up to five", () => {
    let draft = emptyDraft()
    for (let count = 0; count < MAX_LINKS + 2; count += 1) draft = addLink(draft)
    expect(draft.links).toHaveLength(MAX_LINKS)
    const key = draft.links[0].key
    draft = updateLink(draft, key, { title: "Handbook", url: "https://example.com" })
    expect(draft.links[0]).toMatchObject({ title: "Handbook", url: "https://example.com" })
    expect(removeLink(draft, key).links).toHaveLength(MAX_LINKS - 1)
  })
  it("blocks saving while any link is invalid and says which one", () => {
    let draft = addLink(addLink(emptyDraft()))
    draft = updateLink(draft, draft.links[0].key, { title: "Good", url: "https://example.com" })
    expect(draftErrors(draft)).toEqual(["Link 2: Enter a title for the link."])
    draft = updateLink(draft, draft.links[1].key, { title: "Bad", url: "javascript:alert(1)" })
    expect(draftErrors(draft)[0]).toContain("Link 2")
    expect(draftErrors(updateLink(draft, draft.links[1].key, { url: "https://ok.example.com" }))).toEqual([])
  })
})

describe("editing an announcement", () => {
  const announcement = {
    attachments: [saved("img-1", "image", "a.png"), saved("img-2", "image", "b.png"), saved("doc-1", "document", "policy.pdf")],
    links: [{ title: "Handbook", url: "https://example.com/handbook" }],
  }

  it("starts from what is saved: attachments kept, links editable", () => {
    const draft = draftFromAnnouncement(announcement)
    expect(draft.existing).toHaveLength(3)
    expect(draft.removedIds).toEqual([])
    expect(draft.links).toMatchObject([{ title: "Handbook", url: "https://example.com/handbook" }])
    expect(draftFromAnnouncement({}).existing).toEqual([])
  })

  it("sends only the changes: new files, the ids removed, and all links", () => {
    let draft = draftFromAnnouncement(announcement)
    draft = removeExisting(draft, "img-2")
    draft = addFiles(draft, "image", [png("new.png")]).draft
    draft = addFiles(draft, "document", [pdf("extra.pdf")]).draft
    draft = updateLink(draft, draft.links[0].key, { title: "  Handbook v2 " })
    const body = buildAnnouncementFormData({ title: "Office move", is_pinned: false, send_email: true, target_org_unit: null, target_branch: "", category: "general" }, draft)

    expect(body.get("title")).toBe("Office move")
    expect(body.get("is_pinned")).toBe("false")
    expect(body.get("send_email")).toBe("true")
    expect(body.has("target_org_unit")).toBe(false)
    expect(body.has("target_branch")).toBe(false)
    expect(body.getAll("images").map(file => (file as File).name)).toEqual(["new.png"])
    expect(body.getAll("documents").map(file => (file as File).name)).toEqual(["extra.pdf"])
    expect(body.getAll("remove_attachment_ids")).toEqual(["img-2"])
    expect(JSON.parse(String(body.get("links")))).toEqual([{ title: "Handbook v2", url: "https://example.com/handbook" }])
  })

  it("always sends the links, so removing the last one clears it", () => {
    const draft = draftFromAnnouncement(announcement)
    const cleared = removeLink(draft, draft.links[0].key)
    expect(JSON.parse(String(buildAnnouncementFormData({ title: "x" }, cleared).get("links")))).toEqual([])
  })
})

describe("announcementDownloadHref", () => {
  it("goes through the API root so the server can check access", () => {
    expect(announcementDownloadHref("/announcements/1/attachments/abc/download/")).toBe("/api/announcements/1/attachments/abc/download/")
  })
})
