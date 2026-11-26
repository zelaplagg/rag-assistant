import { Component, ElementRef, effect, inject, signal, viewChild } from '@angular/core';
import { IconComponent } from './icon';
import { MarkdownComponent } from './markdown';
import { ChatMessage, Passage } from './models';
import { Store } from './store';

@Component({
  selector: 'app-ask',
  imports: [IconComponent, MarkdownComponent],
  template: `
    <div class="thread" #thread aria-live="polite">
      @if (store.messages().length === 0) {
        <div class="welcome">
          <div class="orb"><app-icon name="sparkles" [size]="26" /></div>
          @if (store.hasNotes()) {
            <h2>What would you like to know?</h2>
            @if (store.extractive()) {
              <p>The demo quotes matching passages and shows their sources.</p>
            } @else {
              <p>Answers use passages retrieved from your notes. Open the sources to inspect them.</p>
            }
            <div class="suggest">
              @for (s of (store.notes().some(sampleNote) ? sampleQuestions : suggestions); track s) {
                <button class="chip-btn" (click)="store.ask(s)">{{ s }}</button>
              }
            </div>
          } @else {
            <h2>Add your notes to get started</h2>
            <p>Upload .md, .txt, .pdf or .docx files on the left, or try the bundled sample notes.</p>
            <button class="btn btn-primary" (click)="store.loadSample()" [disabled]="store.uploading()">
              <app-icon name="sparkles" [size]="16" /> Load sample notes
            </button>
          }
        </div>
      }

      @for (m of store.messages(); track m.id) {
        @if (m.role === 'user') {
          <div class="row user"><div class="bubble">{{ m.text }}</div></div>
        } @else {
          <div class="row bot">
            <div class="avatar"><app-icon name="sparkles" [size]="16" /></div>
            <div class="reply" [class.error]="m.error">
              @if (m.error) {
                <p class="err-text"><app-icon name="alert" [size]="16" /> {{ m.text }}</p>
              } @else {
                <app-md [text]="m.text" />
              }
              @if (!m.error) {
                <div class="foot">
                  @if (m.sources.length) {
                    <button class="link" (click)="toggle(m.id)" [attr.aria-expanded]="isOpen(m.id)">
                      <app-icon name="paperclip" [size]="14" />
                      {{ m.sources.length }} source{{ m.sources.length > 1 ? 's' : '' }}
                      <app-icon name="chevron" [size]="14" [class.rot]="isOpen(m.id)" />
                    </button>
                  }
                  <button class="link" (click)="copy(m)">
                    <app-icon [name]="copiedId() === m.id ? 'check' : 'copy'" [size]="14" />
                    {{ copiedId() === m.id ? 'Copied' : 'Copy' }}
                  </button>
                </div>
                @if (isOpen(m.id)) {
                  <ul class="sources">
                    @for (s of m.sources; track $index) {
                      <li>
                        <div class="src-head">
                          <span class="pill">{{ s.source }}</span>
                          <span class="score">{{ match(s) }}</span>
                        </div>
                        <p>{{ preview(s.text) }}</p>
                      </li>
                    }
                  </ul>
                }
              }
            </div>
          </div>
        }
      }

      @if (store.asking()) {
        <div class="row bot">
          <div class="avatar"><app-icon name="sparkles" [size]="16" /></div>
          <div class="reply typing" aria-label="Thinking"><i></i><i></i><i></i></div>
        </div>
      }
    </div>

    <form class="composer" (submit)="$event.preventDefault(); send()">
      @if (store.messages().length > 0) {
        <button type="button" class="btn btn-ghost btn-sm new" (click)="store.clearChat()">
          <app-icon name="refresh" [size]="14" /> New chat
        </button>
      }
      <div class="box">
        <textarea
          #field
          rows="1"
          maxlength="2000"
          [value]="draft()"
          [disabled]="!store.hasNotes()"
          [placeholder]="store.hasNotes() ? 'Ask anything about your notes…' : 'Add notes first'"
          (input)="grow($event)"
          (keydown)="onKey($event)"
        ></textarea>
        <button
          type="submit"
          class="send"
          [disabled]="!draft().trim() || store.asking() || !store.hasNotes()"
          aria-label="Send"
        >
          <app-icon name="send" [size]="18" />
        </button>
      </div>
      <small>Enter to send · Shift+Enter for a new line</small>
    </form>
  `,
  styles: [
    `
      :host {
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
      }
      .thread {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        padding: 24px 24px 8px;
        display: flex;
        flex-direction: column;
        gap: 18px;
      }

      .welcome {
        margin: auto;
        max-width: 520px;
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
        padding: 24px 0;
      }
      .welcome p {
        color: var(--muted);
        line-height: 1.5;
      }
      .welcome h2 {
        font-size: 1.5rem;
        letter-spacing: -0.02em;
      }
      .orb {
        display: grid;
        place-items: center;
        width: 62px;
        height: 62px;
        margin-bottom: 6px;
        border-radius: 20px;
        color: #fff;
        background: linear-gradient(135deg, var(--accent), var(--accent-2));
        box-shadow: 0 12px 28px rgba(91, 75, 225, 0.35);
      }
      .suggest {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 8px;
        margin-top: 10px;
      }

      .row {
        display: flex;
        gap: 12px;
        max-width: 780px;
        width: 100%;
        margin: 0 auto;
        animation: pop 0.25s ease both;
      }
      @keyframes pop {
        from {
          opacity: 0;
          transform: translateY(6px);
        }
      }
      .row.user {
        justify-content: flex-end;
      }
      .bubble {
        max-width: 85%;
        padding: 10px 16px;
        border-radius: 18px 18px 6px 18px;
        color: #fff;
        background: linear-gradient(135deg, var(--accent), var(--accent-2));
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        line-height: 1.5;
      }
      .avatar {
        display: grid;
        place-items: center;
        flex: none;
        width: 32px;
        height: 32px;
        margin-top: 2px;
        border-radius: 10px;
        color: var(--accent);
        background: var(--accent-soft);
      }
      .reply {
        flex: 1;
        min-width: 0;
        padding: 14px 18px;
        border: 1px solid var(--line);
        border-radius: 6px 18px 18px 18px;
        background: var(--surface);
        box-shadow: var(--shadow);
      }
      .reply.error {
        border-color: var(--err);
        background: var(--err-soft);
      }
      .err-text {
        display: flex;
        gap: 8px;
        color: var(--err);
        line-height: 1.5;
      }
      .typing {
        display: flex;
        gap: 5px;
        align-items: center;
        flex: none;
        padding: 16px 18px;
      }
      .typing i {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--accent);
        animation: bounce 1s infinite ease-in-out;
      }
      .typing i:nth-child(2) {
        animation-delay: 0.15s;
      }
      .typing i:nth-child(3) {
        animation-delay: 0.3s;
      }
      @keyframes bounce {
        0%,
        80%,
        100% {
          opacity: 0.3;
          transform: translateY(0);
        }
        40% {
          opacity: 1;
          transform: translateY(-4px);
        }
      }

      .foot {
        display: flex;
        gap: 6px;
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid var(--line);
      }
      .link {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border: 0;
        border-radius: 8px;
        background: transparent;
        color: var(--muted);
        font-size: 0.82rem;
        font-weight: 600;
        cursor: pointer;
      }
      .link:hover {
        background: var(--surface-2);
        color: var(--accent);
      }
      .rot {
        transform: rotate(180deg);
      }
      .sources {
        list-style: none;
        margin: 8px 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .sources li {
        padding: 10px 12px;
        border-radius: 12px;
        background: var(--surface-2);
      }
      .src-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 6px;
      }
      .score {
        flex: none;
        color: var(--muted);
        font-size: 0.75rem;
      }
      .sources p {
        color: var(--muted);
        font-size: 0.85rem;
        line-height: 1.55;
      }

      .composer {
        position: relative;
        padding: 8px 24px 16px;
        max-width: 828px;
        width: 100%;
        margin: 0 auto;
      }
      .new {
        position: absolute;
        right: 24px;
        top: -30px;
      }
      .box {
        display: flex;
        align-items: flex-end;
        gap: 10px;
        padding: 8px 8px 8px 16px;
        border: 1px solid var(--line);
        border-radius: 18px;
        background: var(--surface);
        box-shadow: var(--shadow);
        transition: border-color 0.15s, box-shadow 0.15s;
      }
      .box:focus-within {
        border-color: var(--accent);
        box-shadow: 0 0 0 4px var(--accent-soft);
      }
      textarea {
        flex: 1;
        min-height: 28px;
        max-height: 150px;
        padding: 6px 0;
        border: 0;
        outline: none;
        resize: none;
        background: transparent;
        line-height: 1.5;
      }
      textarea::placeholder {
        color: var(--muted);
      }
      .send {
        display: grid;
        place-items: center;
        flex: none;
        width: 40px;
        height: 40px;
        border: 0;
        border-radius: 12px;
        color: #fff;
        background: linear-gradient(135deg, var(--accent), var(--accent-2));
        cursor: pointer;
        transition: transform 0.12s, opacity 0.15s;
      }
      .send:hover:not(:disabled) {
        transform: translateY(-1px);
      }
      .send:disabled {
        opacity: 0.35;
        cursor: not-allowed;
      }
      small {
        display: block;
        margin-top: 6px;
        text-align: center;
        color: var(--muted);
        font-size: 0.75rem;
      }

      @media (max-width: 700px) {
        .thread {
          padding: 16px 12px 8px;
        }
        .composer {
          padding: 8px 12px 12px;
        }
        .new {
          right: 12px;
        }
        small {
          display: none;
        }
      }
    `,
  ],
})
export class AskPanel {
  protected readonly store = inject(Store);
  protected readonly draft = signal('');
  protected readonly copiedId = signal<number | null>(null);
  private readonly open = signal<ReadonlySet<number>>(new Set());

  private readonly thread = viewChild<ElementRef<HTMLElement>>('thread');
  private readonly field = viewChild<ElementRef<HTMLTextAreaElement>>('field');

  protected readonly suggestions = [
    'What are the key ideas in my notes?',
    'Explain the most important concept simply',
    'What should I remember for an exam?',
  ];
  protected readonly sampleNote = (note: { name: string }): boolean => note.name === 'rag_basics.md';
  protected readonly sampleQuestions = [
    'How does a RAG pipeline work?',
    'What is overfitting?',
    'What is predictive maintenance?',
  ];

  constructor() {
    // keep the newest message in view
    effect(() => {
      this.store.messages();
      this.store.asking();
      const el = this.thread()?.nativeElement;
      if (el) setTimeout(() => el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' }), 30);
    });
  }

  protected grow(event: Event): void {
    const el = event.target as HTMLTextAreaElement;
    this.draft.set(el.value);
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 150)}px`;
  }

  protected onKey(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      this.send();
    }
  }

  protected send(): void {
    const question = this.draft().trim();
    if (!question || this.store.asking() || !this.store.hasNotes()) return;
    this.draft.set('');
    const el = this.field()?.nativeElement;
    if (el) el.style.height = 'auto';
    void this.store.ask(question);
  }

  protected isOpen(id: number): boolean {
    return this.open().has(id);
  }

  protected toggle(id: number): void {
    this.open.update((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  protected match(passage: Passage): string {
    return passage.score > 0 ? `${Math.round(passage.score * 100)}% match` : 'keyword match';
  }

  protected preview(text: string): string {
    const flat = text.replace(/\s+/g, ' ').trim();
    return flat.length > 320 ? `${flat.slice(0, 319).trimEnd()}…` : flat;
  }

  protected async copy(message: ChatMessage): Promise<void> {
    try {
      await navigator.clipboard.writeText(message.text);
      this.copiedId.set(message.id);
      setTimeout(() => this.copiedId.set(null), 1600);
    } catch {
      this.store.toast('error', 'Could not copy to the clipboard.');
    }
  }
}
