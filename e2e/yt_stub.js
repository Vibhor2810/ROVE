// Stand-in for the official YouTube IFrame API, for local tests only.
(() => {
  const S = { UNSTARTED: -1, ENDED: 0, PLAYING: 1, PAUSED: 2, BUFFERING: 3, CUED: 5 };
  window.__yt = { loads: [], players: 0 };
  window.YT = { Player: class {
    constructor(el, opts) {
      window.__yt.players++;
      this.opts = opts; this.state = S.UNSTARTED; this.base = 0; this.t0 = 0; this.vid = null; this.len = 210;
      const box = document.createElement('iframe'); box.setAttribute('data-stub', 'yt'); box.style.cssText = 'width:100%;height:100%;border:0;background:#111';
      el.replaceWith(box); this.box = box;
      setTimeout(() => opts.events.onReady(), 30);
    }
    _set(s) { this.state = s; this.opts.events.onStateChange({ data: s }); }
    now() { return this.state === S.PLAYING ? this.base + (performance.now() - this.t0) / 1000 : this.base; }
    loadVideoById({ videoId, startSeconds = 0 }) {
      window.__yt.loads.push({ videoId, startSeconds }); this.vid = videoId; this.base = startSeconds;
      this._set(S.BUFFERING);
      setTimeout(() => {
        if (videoId.startsWith('blocked')) return this.opts.events.onError({ data: 150 });
        this.t0 = performance.now(); this._set(S.PLAYING);
        if (videoId.startsWith('dies')) setTimeout(() => { this.state = S.PAUSED; this.opts.events.onError({ data: 100 }); }, 2000);
      }, 120);
    }
    playVideo() { if (this.state !== S.PLAYING) { this.t0 = performance.now(); this._set(S.PLAYING); } }
    pauseVideo() { if (this.state === S.PLAYING) { this.base = this.now(); this._set(S.PAUSED); } }
    stopVideo() { this.base = 0; this.state = S.UNSTARTED; }
    seekTo(s) { this.base = s; this.t0 = performance.now(); window.__yt.lastSeek = s; }
    getCurrentTime() { return this.now(); } getDuration() { return this.len; } getPlayerState() { return this.state; }
    destroy() {}
  } };
})();
