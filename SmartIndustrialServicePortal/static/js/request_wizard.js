document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('#request-form');
  if (!form) return;
  const steps = [...document.querySelectorAll('.request-step')]; let index = 0;
  const show = () => steps.forEach((step, i) => step.classList.toggle('active', i === index));
  document.querySelector('#next').onclick = () => { if ([...steps[index].querySelectorAll('[required]')].every(x => x.reportValidity())) { index++; show(); } };
  document.querySelector('#back').onclick = () => { index--; show(); };
  document.querySelector('#generate-draft').onclick = async () => {
    const response = await fetch('/api/description-draft', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrf_token]').value}, body:JSON.stringify({title:document.querySelector('#title').value, category:document.querySelector('#category').value})});
    const result = await response.json(); if (response.ok) document.querySelector('#description').value = result.description; else alert(result.error);
  };
  show();
});
