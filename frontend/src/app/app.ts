import { Component, inject, signal } from '@angular/core';
import { AskPanel } from './ask';
import { FlashcardsPanel } from './flashcards';
import { IconComponent } from './icon';
import { LibraryPanel } from './library';
import { Tab } from './models';
import { Store } from './store';
import { SummaryPanel } from './summary';

@Component({
  selector: 'app-root',
  imports: [IconComponent, LibraryPanel, AskPanel, SummaryPanel, FlashcardsPanel],
  template: `
    <div class="shell">
      <header class="top">
        <div class="brand">
          <span class="logo"><app-icon name="book" [size]="22" /></span>
          <div>
            <h1>StudyMate</h1>
            <p>Turn your lecture notes into an interactive tutor</p>
          </div>
        </div>

        <span class="spacer"></span>

        <span class="status" [class.on]="store.online() === true" [class.off]="store.online() === false">
          <i></i>{{ status() }}
        </span>
        <button class="icon-btn only-small" (click)="toggleLib()" aria-label="Show or hide your notes">
          <app-icon name="folder" />
        </button>
        <button
          class="icon-btn"
          (click)="store.toggleTheme()"
          [attr.aria-label]="store.theme() === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
        >
          <app-icon [name]="store.theme() === 'dark' ? 'sun' : 'moon'" />
        </button>
      </header>

      @if (store.online() === false) {
        <div class="banner" role="alert">
          <app-icon name="alert" [size]="18" />
          <span>
            The StudyMate API is not running. In the project folder run
            <code>uvicorn api:app --reload --port 8000</code>
          </span>
          <button class="btn btn-sm" (click)="store.refresh()"><app-icon name="refresh" [size]="14" /> Retry</button>
        </div>
      }

      <div class="body">
        <aside class="sidebar" [class.open]="libOpen()">
          <app-library />
        </aside>

        <main class="main">
          <nav class="tabs" role="tablist" aria-label="Study modes">
            @for (t of tabs; track t.id) {
              <button
                role="tab"
                [attr.aria-selected]="store.tab() === t.id"
                [class.active]="store.tab() === t.id"
                (click)="store.tab.set(t.id)"
              >
                <app-icon [name]="t.icon" [size]="17" /> {{ t.label }}
              </button>
            }
          </nav>

          <section class="panel" role="tabpanel">
            @switch (store.tab()) {
              @case ('ask') {
                <app-ask />
              }
              @case ('summary') {
                <app-summary />
              }
              @case ('cards') {
                <app-flashcards />
              }
            }
          </section>
        </main>
      </div>

      <div class="toasts" aria-live="polite">
        @for (t of store.toasts(); track t.id) {
          <div class="toast" [class]="t.kind" role="status">
            <app-icon [name]="t.kind === 'success' ? 'check' : t.kind === 'error' ? 'alert' : 'sparkles'" [size]="17" />
            <span>{{ t.text }}</span>
            <button (click)="store.dismiss(t.id)" aria-label="Dismiss"><app-icon name="x" [size]="15" /></button>
          </div>
        }
      </div>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        height: 100dvh;
      }
      .shell {
        display: flex;
        flex-direction: column;
        height: 100%;
      }

      .top {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 22px;
        border-bottom: 1px solid var(--line);
        background: var(--surface);
      }
      .brand {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .logo {
        display: grid;
        place-items: center;
        width: 42px;
        height: 42px;
        border-radius: 13px;
        color: #fff;
        background: linear-gradient(135deg, var(--accent), var(--accent-2));
        box-shadow: 0 8px 18px rgba(91, 75, 225, 0.32);
      }
      h1 {
        font-size: 1.25rem;
        letter-spacing: -0.02em;
        line-height: 1.1;
      }
      .brand p {
        margin-top: 2px;
        color: var(--muted);
        font-size: 0.8rem;
      }
      .spacer {
        flex: 1;
      }

      .status {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 12px;
        border-radius: 99px;
        background: var(--surface-2);
        color: var(--muted);
        font-size: 0.8rem;
        font-weight: 600;
      }
      .status i {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--muted);
      }
      .status.on i {
        background: var(--ok);
        box-shadow: 0 0 0 3px var(--ok-soft);
      }
      .status.off i {
        background: var(--err);
        box-shadow: 0 0 0 3px var(--err-soft);
      }
      .only-small {
        display: none;
      }

      .banner {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 22px;
        background: var(--err-soft);
        color: var(--err);
        font-size: 0.88rem;
      }
      .banner span {
        flex: 1;
      }
      .banner code {
        padding: 2px 8px;
        border-radius: 6px;
        background: rgba(0, 0, 0, 0.08);
        font-family: ui-monospace, Menlo, monospace;
      }

      .body {
        flex: 1;
        min-height: 0;
        display: grid;
        grid-template-columns: 310px 1fr;
      }
      .sidebar {
        min-height: 0;
        border-right: 1px solid var(--line);
        background: var(--surface);
      }
      .main {
        min-width: 0;
        min-height: 0;
        display: flex;
        flex-direction: column;
      }

      .tabs {
        display: flex;
        gap: 6px;
        padding: 12px 24px 0;
        border-bottom: 1px solid var(--line);
        background: var(--surface);
      }
      .tabs button {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 10px 16px;
        margin-bottom: -1px;
        border: 0;
        border-bottom: 2px solid transparent;
        border-radius: 10px 10px 0 0;
        background: transparent;
        color: var(--muted);
        font-weight: 600;
        cursor: pointer;
        transition: color 0.15s, background 0.15s, border-color 0.15s;
      }
      .tabs button:hover {
        color: var(--ink);
        background: var(--surface-2);
      }
      .tabs button.active {
        color: var(--accent);
        border-bottom-color: var(--accent);
      }
      .panel {
        flex: 1;
        min-height: 0;
      }

      .toasts {
        position: fixed;
        right: 20px;
        bottom: 20px;
        z-index: 50;
        display: flex;
        flex-direction: column;
        gap: 10px;
        width: min(380px, calc(100vw - 40px));
      }
      .toast {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 12px 14px;
        border: 1px solid var(--line);
        border-radius: 14px;
        background: var(--surface);
        box-shadow: var(--shadow);
        font-size: 0.88rem;
        line-height: 1.45;
        animation: slide 0.25s ease both;
      }
      .toast span {
        flex: 1;
        overflow-wrap: anywhere;
      }
      .toast.success {
        border-color: var(--ok);
        color: var(--ok);
      }
      .toast.error {
        border-color: var(--err);
        color: var(--err);
      }
      .toast button {
        border: 0;
        background: transparent;
        color: var(--muted);
        cursor: pointer;
        padding: 0;
      }
      @keyframes slide {
        from {
          opacity: 0;
          transform: translateX(16px);
        }
      }

      @media (max-width: 900px) {
        .body {
          grid-template-columns: 1fr;
        }
        .sidebar {
          display: none;
          max-height: 46dvh;
          border-right: 0;
          border-bottom: 1px solid var(--line);
        }
        .sidebar.open {
          display: block;
        }
        .only-small {
          display: inline-grid;
        }
        .brand p {
          display: none;
        }
        .tabs {
          padding: 8px 12px 0;
          overflow-x: auto;
        }
        .top {
          padding: 10px 14px;
        }
      }
    `,
  ],
})
export class App {
  protected readonly store = inject(Store);
  protected readonly libOpen = signal(false);

  protected readonly tabs: { id: Tab; label: string; icon: string }[] = [
    { id: 'ask', label: 'Ask', icon: 'message' },
    { id: 'summary', label: 'Summary', icon: 'list' },
    { id: 'cards', label: 'Flashcards', icon: 'cards' },
  ];

  constructor() {
    void this.store.init();
  }

  protected toggleLib(): void {
    this.libOpen.update((open) => !open);
  }

  protected status(): string {
    switch (this.store.online()) {
      case true:
        return 'Connected';
      case false:
        return 'Offline';
      default:
        return 'Connecting…';
    }
  }
}
