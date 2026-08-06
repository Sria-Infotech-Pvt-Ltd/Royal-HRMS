# Face-api.js model weights

Self-hosted (not loaded from a CDN) so the registration flow works offline in
dev and never depends on an external host at runtime.

Pulled from `justadudewhohacks/face-api.js` at commit
`a86f011d72124e5fb93e59d5c4ab98f699dd5c9c` (pinned, not `master`):

- `tiny_face_detector_model-*` — face detection for the live preview
- `face_landmark_68_model-*` — 68-point landmarks, used for the liveness check
- `face_recognition_model-*` — generates the 128-d descriptor stored as
  `face_embedding`. This is the exact model
  `FACE_RECOGNITION_MODEL_VERSION = 'face-api.js-faceRecognitionNet-v1'` on
  the backend refers to — do not swap it for a different weights version
  without also updating that backend constant, or previously-approved
  embeddings become incomparable with newly-enrolled ones.

To refresh: re-download the same seven files from
`https://raw.githubusercontent.com/justadudewhohacks/face-api.js/<commit>/weights/`
and update the commit hash above.
