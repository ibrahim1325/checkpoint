document.addEventListener('DOMContentLoaded', function() {
    console.log('Reset password page loaded');
    
    const form = document.querySelector('form');
    const passwordInput = document.querySelector('[name="password"]');
    const confirmInput = document.querySelector('[name="confirm_password"]');
    
    console.log('Form:', form);
    console.log('Password input:', passwordInput);
    console.log('Confirm input:', confirmInput);
    console.log('Confirm input value:', confirmInput?.value);
    
    // Debug: log quand on tape dans le champ confirm
    if (confirmInput) {
        confirmInput.addEventListener('input', function() {
            console.log('Confirm input changed:', this.value);
        });
    }
    
    // Debug: avant soumission
    form.addEventListener('submit', function(e) {
        console.log('=== FORM SUBMIT DEBUG ===');
        console.log('Password value:', passwordInput?.value);
        console.log('Confirm value:', confirmInput?.value);
        console.log('All form data:');
        Array.from(form.elements).forEach(el => {
            if (el.name) console.log(`${el.name}: ${el.value}`);
        });
        console.log('=== END DEBUG ===');
    });
});