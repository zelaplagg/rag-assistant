import { Component, inject, signal } from '@angular/core';
import { IconComponent } from './icon';
import { Store } from './store';

@Component({
  selector: 'app-library',
  imports: [IconComponent],
  template: `
    <div class="head">
      <h2>Your notes</h2>
      <div class="stats">
        <div>
          <b>{{ store.notes().length }}</b
          ><span>notes</span>
        </div>
        <div>
          <b>{{ store.chunkTotal() }}</b
          ><span>chunks</span>
        </div>
      </div>
    </div>

    <label
      class="drop"
      [class.over]="over()"
      [class.busy]="store.uploading()"
      (dragover)="onOver($event)"
      (dragleave)="over.set(false)"
      (drop)="onDrop($event)"
    >
      <input
        type="file"
        multiple
        accept=".md,.txt,.pdf,.docx"
        [disabled]="store.uploading()"
        (change)="onPick($event)"
      />
      @if (store.uploading()) {
        <span class="spinner"></span>
        <strong>Reading and indexing…</strong>
      } @else {
        <span class="drop-icon"><app-icon name="upload" [size]="22" /></span>
        <strong>Drop files here</strong>
        <small>or click to browse · .md .txt .pdf .docx</small>
      }
    </label>

    <button class="btn btn-sm sample" (click)="store.loadSample()" [disabled]="store.uploading()">
      <app-icon name="sparkles" [size]="15" /> Load sample notes
    </button>

    <ul class="list">
      @for (note of store.notes(); track note.name) {
        <li>
          <span class="file"><app-icon name="file" [size]="16" /></span>
          <div class="meta">
            <span class="name" [title]="note.name">{{ note.name }}</span>
            <small>{{ note.chunks }} chunks</small>
          </div>
          <button class="del" (click)="store.removeNote(note.name)" [attr.aria-label]="'Remove ' + note.name">
            <app-icon name="trash" [size]="15" />
          </button>
        </li>
      } @empty {
        <li class="none">Nothing here yet.</li>
      }
    </ul>

    @if (store.hasNotes()) {
      @if (confirming()) {
        <div class="confirm">
          <span>Delete all notes?</span>
          <button class="btn btn-sm" (click)="confirming.set(false)">Cancel</button>
          <button class="btn btn-sm danger" (click)="clearAll()">Delete</button>
        </div>
      } @else {
        <button class="btn btn-ghost btn-sm clear" (click)="confirming.set(true)">
          <app-icon name="trash" [size]="15" /> Clear all notes
        </button>
      }
    }

    <p class="model">
      <app-icon name="sparkles" [size]="14" />
      Model: <b>{{ store.model() || '…' }}</b>
    </p>
  `,
  styles: [
    `
      :host {
        display: flex;
        flex-direction: column;
        gap: 14px;
        padding: 20px 18px;
        height: 100%;
        overflow-y: auto;
      }
      h2 {
        font-size: 1.05rem;
        margin-bottom: 12px;
      }
      .stats {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
      }
      .stats div {
        padding: 10px 12px;
        border-radius: 12px;
        background: var(--surface-2);
        display: flex;
        flex-direction: column;
      }
      .stats b {
        font-size: 1.35rem;
        color: var(--accent);
        line-height: 1.1;
      }
      .stats span {
        font-size: 0.78rem;
        color: var(--muted);
      }

      .drop {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        padding: 22px 14px;
        border: 2px dashed var(--line);
        border-radius: 14px;
        text-align: center;
        cursor: pointer;
        transition: border-color 0.15s, background 0.15s;
      }
      .drop:hover,
      .drop.over {
        border-color: var(--accent);
        background: var(--accent-soft);
      }
      .drop.busy {
        cursor: progress;
        color: var(--accent);
      }
      .drop input {
        position: absolute;
        inset: 0;
        opacity: 0;
        cursor: inherit;
      }
      .drop-icon {
        display: grid;
        place-items: center;
        width: 42px;
        height: 42px;
        margin-bottom: 4px;
        border-radius: 12px;
        background: var(--accent-soft);
        color: var(--accent);
      }
      .drop small {
        color: var(--muted);
        font-size: 0.78rem;
      }
      .sample {
        align-self: stretch;
      }

      .list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .list li {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 10px;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--surface);
      }
      .list li.none {
        justify-content: center;
        border-style: dashed;
        color: var(--muted);
        font-size: 0.85rem;
      }
      .file {
        display: grid;
        place-items: center;
        width: 30px;
        height: 30px;
        border-radius: 9px;
        background: var(--accent-soft);
        color: var(--accent);
        flex: none;
      }
      .meta {
        min-width: 0;
        flex: 1;
        display: flex;
        flex-direction: column;
      }
      .name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-weight: 600;
        font-size: 0.9rem;
      }
      .meta small {
        color: var(--muted);
        font-size: 0.75rem;
      }
      .del {
        display: grid;
        place-items: center;
        width: 30px;
        height: 30px;
        border: 0;
        border-radius: 8px;
        background: transparent;
        color: var(--muted);
        cursor: pointer;
        opacity: 0.6;
      }
      .list li:hover .del,
      .del:focus-visible {
        opacity: 1;
      }
      .del:hover {
        background: var(--err-soft);
        color: var(--err);
      }

      .clear {
        align-self: flex-start;
      }
      .confirm {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.85rem;
      }
      .confirm span {
        flex: 1;
        color: var(--muted);
      }
      .danger {
        background: var(--err);
        border-color: var(--err);
        color: #fff;
      }
      .model {
        margin-top: auto;
        display: flex;
        align-items: center;
        gap: 6px;
        padding-top: 8px;
        color: var(--muted);
        font-size: 0.8rem;
      }
      .model b {
        color: var(--ink);
      }
    `,
  ],
})
export class LibraryPanel {
  protected readonly store = inject(Store);
  protected readonly over = signal(false);
  protected readonly confirming = signal(false);

  protected onOver(event: DragEvent): void {
    event.preventDefault();
    this.over.set(true);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.over.set(false);
    const files = Array.from(event.dataTransfer?.files ?? []);
    if (files.length) void this.store.upload(files);
  }

  protected onPick(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = '';
    if (files.length) void this.store.upload(files);
  }

  protected clearAll(): void {
    this.confirming.set(false);
    void this.store.clearAll();
  }
}
