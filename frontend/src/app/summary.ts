import { Component, inject, signal } from '@angular/core';
import { IconComponent } from './icon';
import { MarkdownComponent } from './markdown';
import { Store } from './store';

@Component({
  selector: 'app-summary',
  imports: [IconComponent, MarkdownComponent],
  template: `
    <div class="page">
      <header>
        <h2>Summarize a topic</h2>
        <p>StudyMate reads the most relevant parts of your notes and writes short study notes.</p>
      </header>

      <form class="bar" (submit)="$event.preventDefault(); store.summarize()">
        <input
          class="input"
          type="text"
          maxlength="300"
          placeholder="e.g. predictive maintenance"
          [value]="store.summaryTopic()"
          [disabled]="!store.hasNotes()"
          (input)="store.summaryTopic.set($any($event.target).value)"
        />
        <button
          class="btn btn-primary"
          type="submit"
          [disabled]="!store.summaryTopic().trim() || store.summarizing() || !store.hasNotes()"
        >
          @if (store.summarizing()) {
            <span class="spinner"></span> Summarizing…
          } @else {
            <app-icon name="list" [size]="17" /> Generate summary
          }
        </button>
      </form>

      @if (!store.hasNotes()) {
        <div class="hint card">Add some notes in the left panel first.</div>
      }

      @if (store.summarizing()) {
        <div class="card result" aria-busy="true">
          <div class="skeleton" style="height: 18px; width: 38%"></div>
          <div class="skeleton" style="height: 12px; margin-top: 18px"></div>
          <div class="skeleton" style="height: 12px; margin-top: 10px; width: 92%"></div>
          <div class="skeleton" style="height: 12px; margin-top: 10px; width: 80%"></div>
          <div class="skeleton" style="height: 12px; margin-top: 10px; width: 86%"></div>
        </div>
      } @else if (store.summaryText()) {
        <article class="card result">
          <div class="result-head">
            <div>
              <small>Summary of</small>
              <h3>{{ store.summaryFor() }}</h3>
            </div>
            <button class="btn btn-sm" (click)="copy()">
              <app-icon [name]="copied() ? 'check' : 'copy'" [size]="15" /> {{ copied() ? 'Copied' : 'Copy' }}
            </button>
          </div>
          <app-md [text]="store.summaryText()" />
          @if (store.summarySources().length) {
            <div class="based">
              <span>Based on</span>
              @for (s of store.summarySources(); track s) {
                <span class="pill">{{ s }}</span>
              }
            </div>
          }
        </article>
      }
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        height: 100%;
        overflow-y: auto;
      }
      .page {
        max-width: 780px;
        margin: 0 auto;
        padding: 28px 24px 40px;
        display: flex;
        flex-direction: column;
        gap: 18px;
      }
      header h2 {
        font-size: 1.5rem;
        letter-spacing: -0.02em;
      }
      header p {
        margin-top: 4px;
        color: var(--muted);
      }
      .bar {
        display: flex;
        gap: 10px;
      }
      .bar .btn {
        flex: none;
        height: 44px;
      }
      .hint {
        padding: 16px 18px;
        color: var(--muted);
      }
      .result {
        padding: 22px 24px;
        animation: rise 0.3s ease both;
      }
      @keyframes rise {
        from {
          opacity: 0;
          transform: translateY(8px);
        }
      }
      .result-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 14px;
        padding-bottom: 14px;
        border-bottom: 1px solid var(--line);
      }
      .result-head small {
        color: var(--muted);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }
      .result-head h3 {
        font-size: 1.2rem;
        overflow-wrap: anywhere;
      }
      .based {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        margin-top: 18px;
        padding-top: 14px;
        border-top: 1px solid var(--line);
        color: var(--muted);
        font-size: 0.82rem;
      }
      @media (max-width: 700px) {
        .page {
          padding: 18px 14px 32px;
        }
        .bar {
          flex-direction: column;
        }
      }
    `,
  ],
})
export class SummaryPanel {
  protected readonly store = inject(Store);
  protected readonly copied = signal(false);

  protected async copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.store.summaryText());
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 1600);
    } catch {
      this.store.toast('error', 'Could not copy to the clipboard.');
    }
  }
}
