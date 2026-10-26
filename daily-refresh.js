(()=>{
  'use strict';

  const tokyoDate=()=>{
    const parts=Object.fromEntries(
      new Intl.DateTimeFormat('en-CA',{
        timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'
      }).formatToParts(new Date())
        .filter(part=>part.type!=='literal')
        .map(part=>[part.type,part.value])
    );
    return `${parts.year}-${parts.month}-${parts.day}`;
  };

  let loadedDate=tokyoDate();

  const refreshIfDateChanged=()=>{
    const currentDate=tokyoDate();
    if(currentDate===loadedDate)return;
    loadedDate=currentDate;
    location.reload();
  };

  // Keep an already-open tab in sync when Japan's calendar date changes.
  setInterval(refreshIfDateChanged,60*1000);
  document.addEventListener('visibilitychange',()=>{
    if(!document.hidden)refreshIfDateChanged();
  });
  window.addEventListener('focus',refreshIfDateChanged);
  // Build marker: archive compatibility fix deployed 2026-10-27.
})();
