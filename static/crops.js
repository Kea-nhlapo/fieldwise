'use strict';
// Crop thumbnails: public-domain / CC0 photos, with a flat leaf drawing for unknown crops.
// Decorative: callers always show the crop name as text next to the icon.
window.cropIcon = (() => {
  const wrap = body => `<svg class="crop-icon" viewBox="0 0 40 40" aria-hidden="true" focusable="false">${body}</svg>`;
  const ICONS = {
    other: wrap('<rect width="40" height="40" rx="10" fill="#e3edd6"/><path d="M20 34V16" stroke="#4f7a32" stroke-width="2.2" stroke-linecap="round"/><path d="M20 22c-7 0-10-5-10-11 7 0 10 5 10 11zM20 20c6 0 9-4 9-9-6 0-9 4-9 9z" fill="#7da544"/>'),
  };
  const PHOTOS = {maize: 'maize', groundnuts: 'groundnuts', tobacco: 'tobacco', vegetables: 'vegetables'};
  // Public-domain / CC0 photos; credits in static/photos/CREDITS.md.
  return crop => {
    const key = String(crop || '').toLowerCase();
    return PHOTOS[key] ? `<img class="crop-icon crop-photo" src="/static/photos/crop-${PHOTOS[key]}.jpg" alt="" width="40" height="40" decoding="async">` : ICONS.other;
  };
})();
