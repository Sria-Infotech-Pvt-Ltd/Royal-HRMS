// Shape check for a face descriptor (the 128-float embedding) before it is
// trusted or sent anywhere. Pure, no DOM / face-api.js dependency - testable
// in plain Node. Never logs or returns the values themselves.

/** Length of face-api.js's faceRecognitionNet descriptor - the vector space the
 *  backend's FACE_RECOGNITION_MODEL_VERSION ('face-api.js-faceRecognitionNet-v1')
 *  pins stored registrations to. */
export const DESCRIPTOR_LENGTH = 128;

/** True only for exactly DESCRIPTOR_LENGTH values that are all finite numbers
 *  (no NaN, no +/-Infinity, no non-numbers). */
export function isValidDescriptor(descriptor: ArrayLike<number> | null | undefined): boolean {
  if (!descriptor || descriptor.length !== DESCRIPTOR_LENGTH) return false;
  for (let i = 0; i < descriptor.length; i++) {
    const value = descriptor[i];
    if (typeof value !== "number" || !Number.isFinite(value)) return false;
  }
  return true;
}
