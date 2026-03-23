<script lang="ts">
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { Activity, ListTodo, Server, Layers, Zap, Github, Mail } from 'lucide-svelte';
  import '../app.css';

  // In Svelte 5 runes mode, layout children are rendered via the snippet API.
  const { children } = $props();

  const links = [
    { href: '/', label: 'Overview', icon: Activity },
    { href: '/tasks', label: 'Tasks', icon: ListTodo },
    { href: '/workers', label: 'Workers', icon: Server },
    { href: '/queues', label: 'Queues', icon: Layers },
    { href: '/events', label: 'Celery Events', icon: Zap }
  ];

</script>

<svelte:head>
  <title>Plywatch</title>
</svelte:head>

<div class="shell">
  <aside>
    <div class="brand-copy">
      <div class="brand-title" aria-label="plywatch">
        <span class="brand-title-ply">ply</span><span class="brand-title-watch">watch</span>
      </div>
      <div class="brand-subtitle">by MassiveDataScope</div>
    </div>
    <nav aria-label="Primary">
      {#each links as link (link.href)}
        {@const href = resolve(link.href)}
        {@const Icon = link.icon}
        <a class:active={page.url.pathname === href} href={href}>
          <Icon size={15} strokeWidth={2} class="nav-icon" />
          <span class="nav-label">{link.label}</span>
        </a>
      {/each}
    </nav>

    <footer class="sidebar-footer">
      <div class="footer-brand">MassiveDataScope</div>
      <div class="footer-links">
        <a
          class="footer-link"
          href="https://github.com/the-reacher-data"
          target="_blank"
          rel="noopener noreferrer"
          title="GitHub"
        >
          <Github size={13} strokeWidth={2} />
          <span>GitHub</span>
        </a>
        <a
          class="footer-link"
          href="mailto:massivedatascope@gmail.com"
          title="Contact us"
        >
          <Mail size={13} strokeWidth={2} />
          <span>Contact</span>
        </a>
      </div>
    </footer>
  </aside>

  <main>
    <div class="main-shell">
      <div class="main-content">
        {@render children()}
      </div>
    </div>
  </main>
</div>

<style>
  :global(body) {
    margin: 0;
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    background: #f6f7f9;
    color: #111827;
  }

  .shell {
    min-height: 100vh;
    display: grid;
    grid-template-columns: 224px minmax(0, 1fr);
    align-items: start;
  }

  aside {
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
    padding: 1.75rem 1.25rem;
    border-right: 1px solid #e2e6eb;
    background: #ffffff;
    display: flex;
    flex-direction: column;
  }

  .brand-copy {
    margin-bottom: 1.5rem;
    display: grid;
    gap: 0.28rem;
    text-align: left;
    padding: 0.15rem 0.35rem 1rem;
    border-bottom: 1px solid #edf1f5;
  }

  .brand-title {
    font-family: "Space Grotesk", "IBM Plex Sans", "Segoe UI", sans-serif;
    font-size: 1.42rem;
    font-weight: 700;
    letter-spacing: -0.055em;
    line-height: 1;
    text-transform: lowercase;
    display: inline-flex;
    align-items: baseline;
    gap: 0.04rem;
  }

  .brand-title-ply {
    color: #111827;
    font-weight: 700;
  }

  .brand-title-watch {
    color: #36576f;
    font-weight: 600;
  }

  .brand-subtitle {
    color: #8b9aab;
    font-size: 0.61rem;
    font-weight: 600;
    letter-spacing: 0.16em;
    line-height: 1.2;
    text-transform: uppercase;
    padding-left: 0.08rem;
  }

  nav {
    display: grid;
    gap: 0.2rem;
    flex: 1;
  }

  a {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.6rem 0.75rem;
    border-left: 2px solid transparent;
    border-radius: 0 6px 6px 0;
    background: transparent;
    color: #6b7280;
    text-decoration: none;
    font-size: 0.875rem;
    font-weight: 500;
    transition:
      background 120ms ease,
      color 120ms ease,
      border-color 120ms ease;
  }

  a:hover {
    background: #f6f7f9;
    color: #111827;
  }

  a.active {
    background: #eff6ff;
    color: #1d4ed8;
    border-left-color: #2563eb;
    font-weight: 600;
  }

  :global(.nav-icon) {
    flex-shrink: 0;
    color: #9ca3af;
    transition: color 120ms ease;
  }

  a:hover :global(.nav-icon) {
    color: #6b7280;
  }

  a.active :global(.nav-icon) {
    color: #2563eb;
  }

  .nav-label {
    min-width: 0;
    flex: 1;
  }

  main {
    min-width: 0;
    padding: 1.25rem;
    align-self: start;
  }

  .main-shell {
    display: block;
  }

  .main-content {
    display: grid;
    gap: 1rem;
  }

  .sidebar-footer {
    margin-top: 1.5rem;
    padding-top: 1rem;
    border-top: 1px solid #f3f4f6;
    display: grid;
    gap: 0.55rem;
  }

  .footer-brand {
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #d1d5db;
    padding: 0 0.25rem;
  }

  .footer-links {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }

  .footer-link {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.38rem 0.5rem;
    border-radius: 5px;
    border-left: none;
    color: #9ca3af;
    font-size: 0.78rem;
    font-weight: 500;
    text-decoration: none;
    transition: background 120ms ease, color 120ms ease;
  }

  .footer-link:hover {
    background: #f6f7f9;
    color: #374151;
    border-left-color: transparent;
  }

  .footer-link :global(svg) {
    flex-shrink: 0;
    color: #d1d5db;
    transition: color 120ms ease;
  }

  .footer-link:hover :global(svg) {
    color: #6b7280;
  }

  @media (max-width: 900px) {
    .shell {
      grid-template-columns: 1fr;
    }

    aside {
      position: static;
      height: auto;
      overflow-y: visible;
      border-right: none;
      border-bottom: 1px solid #e2e6eb;
    }

    main {
      padding: 1.25rem;
    }

  }
</style>
