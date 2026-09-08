/**
 * What counts as a file worth sending, on either side.
 *
 * A school claim and a visa case differ in what a document means. They do not differ in
 * what a file is, so this lives in one place rather than twice — the server checks the
 * same three things, and HCS-11 checks them again after that.
 */

export const ALLOWED_TYPES = ["application/pdf", "image/png", "image/jpeg"];
export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

/** The browser's own accept list, matching ALLOWED_TYPES. */
export const ACCEPTED_FILE_INPUT =
  ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";

/** What is wrong with this file, or null if nothing is. */
export function validateFile(file: File): string | null {
  if (!ALLOWED_TYPES.includes(file.type)) {
    return `"${file.name}" is not a supported format. Please use PDF, PNG, or JPEG.`;
  }
  if (file.size > MAX_FILE_SIZE) {
    const sizeMB = (file.size / 1024 / 1024).toFixed(1);
    return `"${file.name}" is too large (${sizeMB}MB). Maximum size is 10MB.`;
  }
  return null;
}
