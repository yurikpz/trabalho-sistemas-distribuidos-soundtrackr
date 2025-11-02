(function(){
  function playPreviewDirect(url, title, artist){
    const audioEl = new Audio(url);
    audioEl.play().catch(()=>{});
    alert('Tocando preview de: '+title+' — '+artist);
  }

  document.querySelectorAll('.play-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      playPreviewDirect(
        btn.getAttribute('data-preview'),
        btn.getAttribute('data-title'),
        btn.getAttribute('data-artist')
      );
    });
  });
})();
