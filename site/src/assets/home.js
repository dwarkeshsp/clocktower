(function () {
  const { $, config: C } = CT;
  // The video essay: embedded once its YouTube id is set; the video card then becomes the player.
  if (C.youtubeVideoId) {
    $('#essay').innerHTML = `<iframe src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(C.youtubeVideoId)}" title="Clocktower Bench: the video essay" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen loading="lazy"></iframe>`;
    $('#essay').hidden = false;
  }
})();
