const liItems = document.querySelectorAll('.menu ul li');

if (liItems.length > 0) {
  liItems.forEach((item) => {
    item.addEventListener('click', () => {
      
      liItems.forEach((v) => v.classList.remove('active'));
      
      item.classList.add('active');
    });
  });
}
