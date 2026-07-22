"use client";

import clientApi from "@/lib/clientApi";

export interface DownloadFileResult {
  success:  boolean;
  message?: string;
}

// Shared blob-download helper for authenticated file endpoints (sample
// import templates, exports, ...) — same clientApi.get(url, { responseType:
// "blob" }) pattern already used for attendance's "Export CSV", factored out
// now that three sample-download endpoints need the identical flow.
export async function downloadBlobFile(
  url:      string,
  params:   Record<string, string>,
  filename: string,
): Promise<DownloadFileResult> {
  try {
    const response = await clientApi.get(url, { params, responseType: "blob" });
    const blobUrl = URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(blobUrl);
    return { success: true };
  } catch (err: unknown) {
    const message = (err as { message?: string })?.message ?? "Failed to download file.";
    return { success: false, message };
  }
}
