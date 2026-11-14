# Spotlight and last-recorded clips

Spotlight is a separate sidebar view. Its round preview cards show cow number, herd, the latest demo assessment, open-finding count, and recording availability. Favorites can be selected through the searchable picker, removed from a card, or toggled in the existing cow-detail drawer. The browser's existing versioned workspace preferences store favorite IDs. Existing workspaces migrate to three example favorites without losing reviews, added cattle or flight plans; an intentionally empty favorite list stays empty.

## Media behavior

`GET /api/cattle/:id/recording` follows the route → service → repository boundary. The demo adapter returns unavailable/null media for a known cow and 404 for unknown/non-cow IDs. No footage or signed URL is invented. The typed `LatestRecording` response leaves a port for backend-authorized, short-lived playback/thumbnail URLs later.

Users can attach an actual recorded clip to a cow in the viewer. MP4, WebM and MOV inputs are limited to 100 MB and must decode as a finite video. The browser extracts a JPEG frame, stores the recording and poster in IndexedDB, and creates short-lived object URLs for display. Native video controls provide play/pause, seek, volume and fullscreen. Object URLs are revoked when no longer needed; they are not durable media identifiers.

This feature does **not upload files**. Favorites and clips are local to the browser and origin; the local preview and hosted preview therefore have separate saved lists/media. Quota and codec errors are surfaced. Failed replacement does not overwrite the current clip. Removing an attached copy deletes only the IndexedDB copy, not the user's original file. Unfavoriting retains the attached recording for later reuse. Profile reset restores demo preferences/favorites; attached media is managed explicitly from its recording viewer.

Capture time is optional and remains unknown when omitted. If both an existing recording and its replacement have known capture times, an older replacement is rejected. Unknown time is never inferred from filesystem modification/upload time. A manually attached clip is not an automatically verified RFID association.

Illustrative cow photographs are distinctly labeled and are replaced by a real extracted frame only after attachment. No generic image is presented as the actual cow's source evidence.

## Live integration later

The private application backend must authenticate the caller, authorize the cow's tenant and evidence access, select the latest **capture/event time** with a deterministic tie-breaker, and return a fresh playback capability. Preserve the backend-only database/Storage boundary. For the existing 30 fps image-sequence pipeline, the backend can produce a playable 10–15 second clip or add a versioned frame-sequence response; do not expose private object keys as permanent public URLs. No live Supabase policy/schema was changed for this UI feature.

## Non-cow map observations

Non-cow detections use their own DTO/collection, purple diamond markers, a toggleable legend filter and a detail dialog. The demo includes two unidentified non-cow objects. They have pasture-area/time provenance but no permanent cow identity, herd membership, health assessment or diagnosed species. Cow roster/observation totals remain 90/82; map counts explicitly distinguish cow observations from non-cow objects. Area filtering is a display grouping, not evidence of animal herd membership.
