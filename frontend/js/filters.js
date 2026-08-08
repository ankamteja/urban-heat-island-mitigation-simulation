function setupFilters(originalGeojson, onFilterChange) {
  const buttons = document.querySelectorAll('.filter-btn');

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const priority = btn.dataset.priority;
      const filtered = priority === 'All'
        ? originalGeojson
        : {
            ...originalGeojson,
            features: originalGeojson.features.filter(f => f.properties.priority === priority)
          };

      onFilterChange(filtered);
    });
  });
}