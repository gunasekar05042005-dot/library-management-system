// Apply the genre and availability filters as soon as they change.
const form = document.getElementById("filter-form");
if (form) {
  form.querySelectorAll("select, input[type=checkbox]").forEach((el) =>
    el.addEventListener("change", () => form.submit())
  );
}
