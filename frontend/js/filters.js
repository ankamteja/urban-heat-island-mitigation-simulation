function setupFilters(allCells, onChange) {
  const buttons = document.querySelectorAll('.filter-btn');
  const count = document.getElementById('filter-count');

  function announce(cells, priority) {
    count.textContent = priority === 'All'
      ? `${cells.length.toLocaleString()} cells in the study area`
      : `${cells.length.toLocaleString()} ${priority.toLowerCase()}-priority cells`;
  }

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');

      const priority = btn.dataset.priority;
      const cells = priority === 'All'
        ? allCells
        : allCells.filter(c => c.priority === priority);

      announce(cells, priority);
      onChange(cells);
    });
  });

  announce(allCells, 'All');
}
