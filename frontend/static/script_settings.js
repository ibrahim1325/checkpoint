const avatarInput = document.getElementById('avatar');

if (avatarInput) {
  avatarInput.addEventListener('change', function () {
    const file = this.files[0];
    const previewImg = document.querySelector('.profile img');
    const MAX_SIZE_MB = 2;

    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert("The selected file is not an image");
      this.value = ""; // Reset input
      return;
    }

  
    // Display preview
    const reader = new FileReader();
    reader.onload = function (e) {
      if (previewImg) {
        previewImg.src = e.target.result;
      } else {
        console.warn("No <img> element found inside .profile for preview.");
      }
    };
    reader.readAsDataURL(file);
  });
}
