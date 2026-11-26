import { Component, HostListener, computed, inject, signal } from '@angular/core';
import { IconComponent } from './icon';
import { Store } from './store';

@Component({
  selector: 'app-flashcards',
  imports: [IconComponent],
  template: `
    <div class="page">
      <header>
        <h2>Flashcards</h2>
        <p>Pick a topic, flip the cards and sort them into “got it” and “again”.</p>
      </header>

      <form class="bar" (submit)="$event.preventDefault(); store.makeCards()">
        <input
          class="input"
          type="text"
          maxlength="300"
          placeholder="e.g. RAG pipeline"
          [value]="store.cardsTopic()"
          [disabled]="!store.hasNotes()"
          (input)="store.cardsTopic.set($any($event.target).value)"
        />
        <div class="seg" role="group" aria-label="Number of cards">
          @for (n of counts; track n) {
            <button type="button" [class.on]="store.cardCount() === n" (click)="store.cardCount.set(n)">{{ n }}</button>
          }
        </div>
        <button
          class="btn btn-primary"
          type="submit"
          [disabled]="!store.cardsTopic().trim() || store.generating() || !store.hasNotes()"
        >
          @if (store.generating()) {
            <span class="spinner"></span> Creating…
          } @else {
            <app-icon name="cards" [size]="17" /> Generate
          }
        </button>
      </form>

      @if (!store.hasNotes()) {
        <div class="hint card">Add some notes in the left panel first.</div>
      } @else if (store.generating()) {
        <div class="scene"><div class="skeleton card-skel"></div></div>
      } @else if (store.deck().length > 0) {
        <div class="progress" role="progressbar" [attr.aria-valuenow]="store.progress()" aria-valuemin="0" aria-valuemax="100">
          <div class="bar-track"><div class="bar-fill" [style.width.%]="store.progress()"></div></div>
          <span>{{ store.known() }} / {{ store.deck().length }} learned</span>
        </div>

        @if (current(); as card) {
          <div class="scene">
            <div
              class="flip"
              [class.flipped]="flipped()"
              tabindex="0"
              role="button"
              [attr.aria-label]="flipped() ? 'Show question' : 'Show answer'"
              (click)="flip()"
              (keydown.enter)="flip()"
            >
              <div class="face front">
                <span class="tag">Question</span>
                <p>{{ card.question }}</p>
                <span class="tap"><app-icon name="rotate" [size]="14" /> Click or press Space to flip</span>
              </div>
              <div class="face back">
                <span class="tag">Answer</span>
                <p>{{ card.answer }}</p>
              </div>
            </div>
          </div>

          <div class="actions">
            <button class="btn again" (click)="rate(false)" [disabled]="busy()">
              <app-icon name="refresh" [size]="16" /> Again <kbd>1</kbd>
            </button>
            <button class="btn good" (click)="rate(true)" [disabled]="busy()">
              <app-icon name="check" [size]="16" /> Got it <kbd>2</kbd>
            </button>
          </div>
          <div class="sub">
            <span>{{ store.queue().length }} left in this round</span>
            <button class="btn btn-ghost btn-sm" (click)="store.shuffle()">
              <app-icon name="shuffle" [size]="14" /> Shuffle
            </button>
          </div>
        } @else {
          <div class="card done">
            <div class="trophy"><app-icon name="check" [size]="30" /></div>
            <h3>All {{ store.deck().length }} cards learned</h3>
            <p>Nice work. Go again to lock it in, or try a new topic.</p>
            <div class="done-actions">
              <button class="btn btn-primary" (click)="store.restartDeck()">
                <app-icon name="refresh" [size]="16" /> Study again
              </button>
              <button class="btn" (click)="store.resetDeck()">New topic</button>
            </div>
          </div>
        }
      } @else if (store.cardsRequested()) {
        <div class="hint card">No cards for that topic. Try a topic that appears in your notes.</div>
      } @else {
        <div class="empty">
          <div class="orb"><app-icon name="cards" [size]="26" /></div>
          <p>Your flashcards will appear here.</p>
        </div>
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
        max-width: 720px;
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
        flex-wrap: wrap;
      }
      .bar .input {
        flex: 1 1 220px;
      }
      .bar .btn {
        height: 44px;
        flex: none;
      }
      .seg {
        display: inline-flex;
        padding: 4px;
        gap: 2px;
        height: 44px;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--surface);
      }
      .seg button {
        min-width: 38px;
        border: 0;
        border-radius: 8px;
        background: transparent;
        color: var(--muted);
        font-weight: 700;
        cursor: pointer;
      }
      .seg button.on {
        background: var(--accent-soft);
        color: var(--accent);
      }
      .hint {
        padding: 16px 18px;
        color: var(--muted);
      }

      .progress {
        display: flex;
        align-items: center;
        gap: 12px;
        color: var(--muted);
        font-size: 0.85rem;
      }
      .bar-track {
        flex: 1;
        height: 8px;
        border-radius: 99px;
        background: var(--surface-2);
        overflow: hidden;
      }
      .bar-fill {
        height: 100%;
        border-radius: 99px;
        background: linear-gradient(90deg, var(--accent), var(--accent-2));
        transition: width 0.4s ease;
      }

      .scene {
        perspective: 1400px;
      }
      .card-skel {
        height: 280px;
        border-radius: 22px;
      }
      .flip {
        position: relative;
        height: 280px;
        cursor: pointer;
        transform-style: preserve-3d;
        transition: transform 0.55s cubic-bezier(0.2, 0.8, 0.2, 1);
      }
      .flip.flipped {
        transform: rotateY(180deg);
      }
      .face {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 14px;
        padding: 28px 32px;
        border: 1px solid var(--line);
        border-radius: 22px;
        box-shadow: var(--shadow);
        text-align: center;
        overflow-y: auto;
        -webkit-backface-visibility: hidden;
        backface-visibility: hidden;
      }
      .face p {
        font-size: 1.2rem;
        line-height: 1.5;
        font-weight: 600;
        overflow-wrap: anywhere;
      }
      .front {
        background: var(--surface);
      }
      .back {
        color: #fff;
        background: linear-gradient(135deg, var(--accent), var(--accent-2));
        border-color: transparent;
        transform: rotateY(180deg);
      }
      .back p {
        font-weight: 500;
      }
      .tag {
        padding: 3px 12px;
        border-radius: 99px;
        background: var(--accent-soft);
        color: var(--accent);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      .back .tag {
        background: rgba(255, 255, 255, 0.2);
        color: #fff;
      }
      .tap {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: var(--muted);
        font-size: 0.78rem;
      }

      .actions {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      }
      .actions .btn {
        height: 50px;
      }
      .again:hover:not(:disabled) {
        border-color: var(--err);
        color: var(--err);
      }
      .good {
        background: var(--ok-soft);
        border-color: transparent;
        color: var(--ok);
      }
      .good:hover:not(:disabled) {
        border-color: var(--ok);
      }
      kbd {
        padding: 1px 7px;
        border-radius: 6px;
        background: var(--surface-2);
        color: var(--muted);
        font: 0.72rem ui-monospace, Menlo, monospace;
      }
      .sub {
        display: flex;
        align-items: center;
        justify-content: space-between;
        color: var(--muted);
        font-size: 0.82rem;
      }

      .done {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
        padding: 40px 24px;
        text-align: center;
        animation: pop 0.35s ease both;
      }
      .done p {
        color: var(--muted);
      }
      @keyframes pop {
        from {
          opacity: 0;
          transform: scale(0.96);
        }
      }
      .trophy,
      .orb {
        display: grid;
        place-items: center;
        width: 62px;
        height: 62px;
        border-radius: 20px;
        color: #fff;
        background: linear-gradient(135deg, var(--accent), var(--accent-2));
        box-shadow: 0 12px 28px rgba(91, 75, 225, 0.35);
      }
      .done-actions {
        display: flex;
        gap: 10px;
        margin-top: 8px;
      }
      .empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 14px;
        padding: 48px 0;
        color: var(--muted);
      }

      @media (max-width: 700px) {
        .page {
          padding: 18px 14px 32px;
        }
        .face {
          padding: 22px 20px;
        }
        .face p {
          font-size: 1.05rem;
        }
      }
    `,
  ],
})
export class FlashcardsPanel {
  protected readonly store = inject(Store);
  protected readonly counts = [3, 5, 8, 10];
  protected readonly flipped = signal(false);
  protected readonly busy = signal(false);
  protected readonly current = computed(() => this.store.queue()[0] ?? null);

  protected flip(): void {
    if (!this.busy()) this.flipped.update((f) => !f);
  }

  /** Flip back first so the next question is never visible through the old answer. */
  protected rate(knewIt: boolean): void {
    if (this.busy() || !this.current()) return;
    this.busy.set(true);
    const wasFlipped = this.flipped();
    this.flipped.set(false);
    setTimeout(
      () => {
        if (knewIt) this.store.gotIt();
        else this.store.again();
        this.busy.set(false);
      },
      wasFlipped ? 320 : 0,
    );
  }

  @HostListener('window:keydown', ['$event'])
  protected onKey(event: KeyboardEvent): void {
    const target = event.target as HTMLElement | null;
    if (target && ['INPUT', 'TEXTAREA'].includes(target.tagName)) return;
    if (!this.current()) return;
    if (event.key === ' ') {
      if (target?.tagName === 'BUTTON') return; // let a focused button handle its own Space
      event.preventDefault();
      this.flip();
    } else if (event.key === '1') {
      this.rate(false);
    } else if (event.key === '2') {
      this.rate(true);
    }
  }
}
