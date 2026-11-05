// Apply the genre and availability filters as soon as they change.
const form = document.getElementById("filter-form");
if (form) {
  form.querySelectorAll("select, input[type=checkbox]").forEach((el) =>
    el.addEventListener("change", () => form.submit())
  );
}

// Show the default cover when a cover image is missing or fails to load.
// (Done here, not in an inline onerror attribute, so a strict Content-Security-Policy can be used.)
function useFallback(img) {
  if (img.dataset.fallback && !img.dataset.fallbackUsed) {
    img.dataset.fallbackUsed = "1";
    img.src = img.dataset.fallback;
  }
}
document.addEventListener("error", (e) => {           // 'error' does not bubble, so listen while capturing
  if (e.target.tagName === "IMG") useFallback(e.target);
}, true);
document.querySelectorAll("img.cover").forEach((img) => {   // images that failed before this script ran
  if (img.complete && img.naturalWidth === 0) useFallback(img);
});
