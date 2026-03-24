<script lang="ts">
  export let size: 'md' | 'lg' = 'md';
</script>

<svg
  class:large={size === 'lg'}
  class="brand-mark"
  viewBox="0 0 144 144"
  xmlns="http://www.w3.org/2000/svg"
  aria-hidden="true"
>
  <defs>
    <linearGradient id="plywatch-stroke" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f1720" />
      <stop offset="100%" stop-color="#2d4d68" />
    </linearGradient>
  </defs>

  <rect x="20" y="20" width="20" height="104" rx="10" fill="url(#plywatch-stroke)" />
  <ellipse
    cx="69"
    cy="54"
    rx="35"
    ry="30"
    fill="none"
    stroke="url(#plywatch-stroke)"
    stroke-width="12"
  />
  <circle cx="98" cy="88" r="8" fill="#20c997" />
</svg>

<style>
  .brand-mark {
    width: 3.75rem;
    height: 3.75rem;
    display: block;
  }

  .large {
    width: 4.6rem;
    height: 4.6rem;
  }
</style>
