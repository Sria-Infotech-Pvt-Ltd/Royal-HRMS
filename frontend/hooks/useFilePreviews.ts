"use client";

import { useEffect, useState } from "react";

/** Temporary browser addresses for picked image files, so thumbnails show before upload. They are released when the files change or
    the component goes away. Empty until the browser has made them (and on the server). */
export function useFilePreviews(files: File[]): string[] {
  const [urls, setUrls] = useState<string[]>([]);

  useEffect(() => {
    const made = files.map(file => URL.createObjectURL(file));
    setUrls(made);
    return () => made.forEach(url => URL.revokeObjectURL(url));
  }, [files]);

  return urls;
}
