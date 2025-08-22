document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".inc").forEach(btn =>
    btn.addEventListener("click", () => update(btn, "increment"))
  );
  document.querySelectorAll(".dec").forEach(btn =>
    btn.addEventListener("click", () => update(btn, "decrement"))
  );
  document.querySelectorAll(".del").forEach(btn =>
    btn.addEventListener("click", () => update(btn, "delete"))
  );
});

function update(button, action) {
  const row = button.closest("tr");
  const productId = row.getAttribute("data-id");

  axios.post("/api/update_product", {
    product_id: productId,
    action: action
  }).then(() => {
    location.reload(); // simple reload after update
  }).catch(console.error);
}

