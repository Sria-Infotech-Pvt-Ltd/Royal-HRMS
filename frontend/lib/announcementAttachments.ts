/** Images, PDFs and links on an announcement: the limits, the checks done before upload, the editable draft, and the request body.
    The server checks everything again (type, real file content, size, counts, links); these checks only give instant feedback. */
import { API_BASE } from "@/lib/config";

export const MAX_IMAGES = 5;
export const MAX_DOCUMENTS = 5;
export const MAX_LINKS = 5;
export const MAX_FILE_BYTES = 5 * 1024 * 1024;
export const LINK_TITLE_MAX = 100;
export const LINK_URL_MAX = 500;

export type AttachmentKind = "image" | "document";

export interface AnnouncementAttachment {
  id:                string;
  attachment_type:   AttachmentKind;
  original_filename: string;
  file_size:         number;
  content_type:      string;
  /** Images only: a short-lived signed address to show the picture. Empty for documents. */
  url:               string;
  /** Authorised download endpoint, relative to the API root. */
  download_path:     string;
}

export interface AnnouncementLink {
  title: string;
  url:   string;
}

/** What the person is editing. `existing` are already saved; `removedIds` are the ones they asked to remove. */
export interface LinkDraft extends AnnouncementLink {
  key: string;
}

export interface AttachmentDraft {
  existing:     AnnouncementAttachment[];
  removedIds:   string[];
  newImages:    File[];
  newDocuments: File[];
  links:        LinkDraft[];
}

interface UploadLike {
  name: string;
  size: number;
  type: string;
}

const ACCEPTED: Record<AttachmentKind, Record<string, string[]>> = {
  image:    { "image/jpeg": [".jpg", ".jpeg"], "image/png": [".png"], "image/webp": [".webp"] },
  document: { "application/pdf": [".pdf"] },
};

export const IMAGE_ACCEPT = "image/jpeg,image/png,image/webp";
export const DOCUMENT_ACCEPT = "application/pdf";

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Why this file cannot be attached, or null when it can. */
export function checkFile(file: UploadLike, kind: AttachmentKind): string | null {
  const rules = ACCEPTED[kind];
  const extension = file.name.includes(".") ? `.${file.name.split(".").pop()?.toLowerCase() ?? ""}` : "";
  if (file.size === 0) return `"${file.name}" is empty.`;
  if (file.size > MAX_FILE_BYTES) return `"${file.name}" is larger than ${MAX_FILE_BYTES / (1024 * 1024)} MB.`;
  if (!(file.type in rules) || !rules[file.type].includes(extension)) {
    return `"${file.name}" is not accepted. Only ${kind === "image" ? "JPG, PNG or WebP images" : "PDF files"} can be added here.`;
  }
  return null;
}

export function emptyDraft(): AttachmentDraft {
  return { existing: [], removedIds: [], newImages: [], newDocuments: [], links: [] };
}

let linkCounter = 0;
function nextLinkKey(): string {
  linkCounter += 1;
  return `link-${linkCounter}`;
}

export function draftFromAnnouncement(
  announcement: { attachments?: AnnouncementAttachment[]; links?: AnnouncementLink[] },
): AttachmentDraft {
  return {
    existing:     announcement.attachments ?? [],
    removedIds:   [],
    newImages:    [],
    newDocuments: [],
    links:        (announcement.links ?? []).map(link => ({ ...link, key: nextLinkKey() })),
  };
}

function keptCount(draft: AttachmentDraft, kind: AttachmentKind): number {
  return draft.existing.filter(item => item.attachment_type === kind && !draft.removedIds.includes(item.id)).length;
}

export function imageCount(draft: AttachmentDraft): number {
  return keptCount(draft, "image") + draft.newImages.length;
}

export function documentCount(draft: AttachmentDraft): number {
  return keptCount(draft, "document") + draft.newDocuments.length;
}

/** Add files of one kind, keeping the first ones when the limit is reached. Returns the new draft and a message per refused file. */
export function addFiles(draft: AttachmentDraft, kind: AttachmentKind, files: File[]): { draft: AttachmentDraft; errors: string[] } {
  const limit = kind === "image" ? MAX_IMAGES : MAX_DOCUMENTS;
  const label = kind === "image" ? "images" : "PDF attachments";
  const errors: string[] = [];
  const accepted: File[] = [];
  let count = kind === "image" ? imageCount(draft) : documentCount(draft);
  for (const file of files) {
    const problem = checkFile(file, kind);
    if (problem) {
      errors.push(problem);
    } else if (count >= limit) {
      errors.push(`An announcement can have at most ${limit} ${label}; "${file.name}" was not added.`);
    } else {
      accepted.push(file);
      count += 1;
    }
  }
  const next = kind === "image"
    ? { ...draft, newImages: [...draft.newImages, ...accepted] }
    : { ...draft, newDocuments: [...draft.newDocuments, ...accepted] };
  return { draft: next, errors };
}

export function removeExisting(draft: AttachmentDraft, id: string): AttachmentDraft {
  return draft.removedIds.includes(id) ? draft : { ...draft, removedIds: [...draft.removedIds, id] };
}

export function removeNew(draft: AttachmentDraft, kind: AttachmentKind, index: number): AttachmentDraft {
  return kind === "image"
    ? { ...draft, newImages: draft.newImages.filter((_, position) => position !== index) }
    : { ...draft, newDocuments: draft.newDocuments.filter((_, position) => position !== index) };
}

export function addLink(draft: AttachmentDraft): AttachmentDraft {
  return draft.links.length >= MAX_LINKS ? draft : { ...draft, links: [...draft.links, { key: nextLinkKey(), title: "", url: "" }] };
}

export function updateLink(draft: AttachmentDraft, key: string, change: Partial<AnnouncementLink>): AttachmentDraft {
  return { ...draft, links: draft.links.map(link => (link.key === key ? { ...link, ...change } : link)) };
}

export function removeLink(draft: AttachmentDraft, key: string): AttachmentDraft {
  return { ...draft, links: draft.links.filter(link => link.key !== key) };
}

/** True for a plain web address: http or https, a host, no spaces, no embedded credentials. */
export function isSafeHttpUrl(value: string): boolean {
  const text = value.trim();
  if (!text || text.length > LINK_URL_MAX || /\s/.test(text)) return false;
  try {
    const parsed = new URL(text);
    return (parsed.protocol === "http:" || parsed.protocol === "https:") && !!parsed.hostname && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

export interface LinkProblems {
  title?: string;
  url?:   string;
}

/** What is wrong with one link row. `strict` also asks for rows that are still empty (used when saving). */
export function linkProblems(link: AnnouncementLink, strict: boolean): LinkProblems {
  const problems: LinkProblems = {};
  const title = link.title.trim();
  const url = link.url.trim();
  if (!title && (strict || url)) problems.title = "Enter a title for the link.";
  else if (title.length > LINK_TITLE_MAX) problems.title = `At most ${LINK_TITLE_MAX} characters.`;
  if (!url && (strict || title)) problems.url = "Enter the web address.";
  else if (url && !isSafeHttpUrl(url)) problems.url = "Enter a valid address starting with http:// or https://.";
  return problems;
}

/** Everything that stops this draft from being saved, one message per problem (empty when it can be saved). */
export function draftErrors(draft: AttachmentDraft): string[] {
  const errors: string[] = [];
  draft.links.forEach((link, index) => {
    const problems = linkProblems(link, true);
    if (problems.title || problems.url) errors.push(`Link ${index + 1}: ${problems.title ?? problems.url}`);
  });
  if (imageCount(draft) > MAX_IMAGES) errors.push(`At most ${MAX_IMAGES} images.`);
  if (documentCount(draft) > MAX_DOCUMENTS) errors.push(`At most ${MAX_DOCUMENTS} PDF attachments.`);
  return errors;
}

/** The multipart body the announcement endpoints expect: the text fields, new files, ids to remove, and all the links. */
export function buildAnnouncementFormData(fields: Record<string, string | boolean | number | null>, draft: AttachmentDraft): FormData {
  const body = new FormData();
  for (const [name, value] of Object.entries(fields)) {
    if (value !== null && value !== "") body.append(name, String(value));
  }
  draft.newImages.forEach(file => body.append("images", file, file.name));
  draft.newDocuments.forEach(file => body.append("documents", file, file.name));
  draft.removedIds.forEach(id => body.append("remove_attachment_ids", id));
  body.append("links", JSON.stringify(draft.links.map(({ title, url }) => ({ title: title.trim(), url: url.trim() }))));
  return body;
}

/** The address a person's browser opens to download an attachment (checked by the server for access). */
export function announcementDownloadHref(downloadPath: string): string {
  return `${API_BASE}${downloadPath}`;
}
