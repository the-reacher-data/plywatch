<span class="spark" aria-label="running" role="img">
  <span>!</span><span>/</span><span>·</span>
</span>

<style>
  .spark {
    display: inline-flex;
    gap: 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    color: #1e4f85;
    letter-spacing: -0.02em;
  }

  .spark span {
    animation: spark-pulse 0.9s ease-in-out infinite;
  }

  .spark span:nth-child(1) { animation-delay: 0s; }
  .spark span:nth-child(2) { animation-delay: 0.3s; }
  .spark span:nth-child(3) { animation-delay: 0.6s; }

  @keyframes spark-pulse {
    0%, 100% { opacity: 0.15; }
    50%       { opacity: 1; }
  }
</style>
