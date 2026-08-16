const venueInputs = document.querySelectorAll('input[name="is_home"]');
const locationInput = document.querySelector("#id_location");
const locationField = locationInput?.closest("p");

function updateLocationField() {
  const homeInput = document.querySelector('input[name="is_home"]:checked');
  const isHome = homeInput?.value === "True";

  if (!locationInput || !locationField) {
    return;
  }

  locationField.hidden = isHome;
  locationInput.disabled = isHome;
  if (isHome) {
    locationInput.value = "";
  }
}

for (const venueInput of venueInputs) {
  venueInput.addEventListener("change", updateLocationField);
}

updateLocationField();
