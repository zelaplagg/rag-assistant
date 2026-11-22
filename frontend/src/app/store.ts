import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';
import { ChatMessage, Flashcard, Note, Tab, Toast } from './models';

const ALLOWED = ['.md', '.txt', '.pdf', '.docx'];
const MAX_MB = 10;

type Theme = 'light' | 'dark';

/** Single source of truth for the UI. Components only read signals and call methods. */
@Injectable({ providedIn: 'root' })
export class Store {
  private readonly api = inject(ApiService);
  private seq = 0;

  // ---- app
  readonly tab = signal<Tab>('ask');
  readonly theme = signal<Theme>('light');
  readonly online = signal<boolean | null>(null);
  readonly model = signal('');
  readonly toasts = signal<Toast[]>([]);

  // ---- library
  readonly notes = signal<Note[]>([]);
  readonly uploading = signal(false);
  readonly hasNotes = computed(() => this.notes().length > 0);
  readonly chunkTotal = computed(() => this.notes().reduce((sum, n) => sum + n.chunks, 0));

  // ---- ask
  readonly messages = signal<ChatMessage[]>([]);
  readonly asking = signal(false);

  // ---- summary
  readonly summaryTopic = signal('');
  readonly summaryText = signal('');
  readonly summaryFor = signal('');
  readonly summarySources = signal<string[]>([]);
  readonly summarizing = signal(false);

  // ---- flashcards
  readonly cardsTopic = signal('');
  readonly cardCount = signal(5);
  readonly generating = signal(false);
  readonly cardsRequested = signal(false);
  readonly deck = signal<Flashcard[]>([]);
  readonly queue = signal<Flashcard[]>([]);
  readonly known = signal(0);
  readonly progress = computed(() => {
    const total = this.deck().length;
    return total === 0 ? 0 : Math.round((this.known() / total) * 100);
  });

  // ------------------------------------------------------------------ lifecycle
  async init(): Promise<void> {
    this.theme.set(this.initialTheme());
    this.applyTheme();
    await this.refresh();
  }

  async refresh(): Promise<void> {
    try {
      const health = await firstValueFrom(this.api.health());
      this.model.set(health.model);
      this.notes.set(await firstValueFrom(this.api.notes()));
      this.online.set(true);
    } catch {
      this.online.set(false);
    }
  }

  toggleTheme(): void {
    this.theme.update((t) => (t === 'dark' ? 'light' : 'dark'));
    this.applyTheme();
    try {
      localStorage.setItem('studymate-theme', this.theme());
    } catch {
      /* storage can be unavailable (private mode) — the theme just won't persist */
    }
  }

  // ------------------------------------------------------------------ library
  async upload(files: File[]): Promise<void> {
    const valid: File[] = [];
    for (const file of files) {
      const lower = file.name.toLowerCase();
      if (!ALLOWED.some((ext) => lower.endsWith(ext))) {
        this.toast('error', `${file.name}: unsupported type. Use ${ALLOWED.join(', ')}.`);
      } else if (file.size > MAX_MB * 1024 * 1024) {
        this.toast('error', `${file.name}: larger than ${MAX_MB} MB.`);
      } else {
        valid.push(file);
      }
    }
    if (valid.length === 0) return;

    this.uploading.set(true);
    try {
      const results = await firstValueFrom(this.api.upload(valid));
      const ok = results.filter((r) => !r.error);
      for (const r of results.filter((x) => x.error)) this.toast('error', `${r.name}: ${r.error}`);
      if (ok.length) {
        const chunks = ok.reduce((sum, r) => sum + r.chunks, 0);
        this.toast('success', `Indexed ${ok.length} file${ok.length > 1 ? 's' : ''} (${chunks} chunks).`);
      }
      await this.refresh();
    } catch (err) {
      this.toast('error', this.errorText(err));
    } finally {
      this.uploading.set(false);
    }
  }

  async loadSample(): Promise<void> {
    this.uploading.set(true);
    try {
      const { chunks } = await firstValueFrom(this.api.loadSample());
      this.toast('success', `Loaded the sample notes (${chunks} chunks).`);
      await this.refresh();
    } catch (err) {
      this.toast('error', this.errorText(err));
    } finally {
      this.uploading.set(false);
    }
  }

  async removeNote(name: string): Promise<void> {
    try {
      await firstValueFrom(this.api.deleteNote(name));
      await this.refresh();
    } catch (err) {
      this.toast('error', this.errorText(err));
    }
  }

  async clearAll(): Promise<void> {
    try {
      await firstValueFrom(this.api.clearNotes());
      this.messages.set([]);
      this.summaryText.set('');
      this.resetDeck();
      await this.refresh();
    } catch (err) {
      this.toast('error', this.errorText(err));
    }
  }

  // ------------------------------------------------------------------ ask
  async ask(question: string): Promise<void> {
    const text = question.trim();
    if (!text || this.asking()) return;
    this.messages.update((m) => [...m, this.message('user', text)]);
    this.asking.set(true);
    try {
      const res = await firstValueFrom(this.api.ask(text));
      this.messages.update((m) => [...m, this.message('assistant', res.answer, res.sources)]);
    } catch (err) {
      this.messages.update((m) => [...m, this.message('assistant', this.errorText(err), [], true)]);
    } finally {
      this.asking.set(false);
    }
  }

  clearChat(): void {
    this.messages.set([]);
  }

  // ------------------------------------------------------------------ summary
  async summarize(): Promise<void> {
    const topic = this.summaryTopic().trim();
    if (!topic || this.summarizing()) return;
    this.summarizing.set(true);
    try {
      const res = await firstValueFrom(this.api.summary(topic));
      this.summaryText.set(res.summary);
      this.summarySources.set(res.sources);
      this.summaryFor.set(topic);
    } catch (err) {
      this.toast('error', this.errorText(err));
    } finally {
      this.summarizing.set(false);
    }
  }

  // ------------------------------------------------------------------ flashcards
  async makeCards(): Promise<void> {
    const topic = this.cardsTopic().trim();
    if (!topic || this.generating()) return;
    this.generating.set(true);
    this.cardsRequested.set(true);
    this.resetDeck(true);
    try {
      const res = await firstValueFrom(this.api.flashcards(topic, this.cardCount()));
      this.deck.set(res.cards);
      this.queue.set(res.cards);
      this.known.set(0);
      if (res.cards.length === 0) {
        this.toast('info', 'No flashcards for that topic. Try a topic closer to your notes.');
      }
    } catch (err) {
      this.toast('error', this.errorText(err));
    } finally {
      this.generating.set(false);
    }
  }

  /** "Got it": the card leaves the queue. */
  gotIt(): void {
    this.queue.update((q) => q.slice(1));
    this.known.update((k) => k + 1);
  }

  /** "Again": the card goes to the back of the queue. */
  again(): void {
    this.queue.update((q) => (q.length > 1 ? [...q.slice(1), q[0]] : q));
  }

  shuffle(): void {
    this.queue.update((q) => {
      const copy = [...q];
      for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
      }
      return copy;
    });
  }

  restartDeck(): void {
    this.queue.set(this.deck());
    this.known.set(0);
  }

  resetDeck(keepRequested = false): void {
    this.deck.set([]);
    this.queue.set([]);
    this.known.set(0);
    if (!keepRequested) this.cardsRequested.set(false);
  }

  // ------------------------------------------------------------------ toasts
  toast(kind: Toast['kind'], text: string): void {
    const id = ++this.seq;
    this.toasts.update((t) => [...t, { id, kind, text }]);
    setTimeout(() => this.dismiss(id), kind === 'error' ? 7000 : 4000);
  }

  dismiss(id: number): void {
    this.toasts.update((t) => t.filter((x) => x.id !== id));
  }

  // ------------------------------------------------------------------ helpers
  private message(
    role: ChatMessage['role'],
    text: string,
    sources: ChatMessage['sources'] = [],
    error = false,
  ): ChatMessage {
    return { id: ++this.seq, role, text, sources, error };
  }

  private errorText(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      if (err.status === 0) {
        return 'Cannot reach the StudyMate API on http://localhost:8000. Start it with: uvicorn api:app --reload --port 8000';
      }
      const detail: unknown = err.error?.detail;
      if (typeof detail === 'string') return detail;
      if (err.status === 422) return 'The request was not valid. Please check your input.';
    }
    return 'Something went wrong. Please try again.';
  }

  private initialTheme(): Theme {
    try {
      const saved = localStorage.getItem('studymate-theme');
      if (saved === 'dark' || saved === 'light') return saved;
    } catch {
      /* ignore */
    }
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  private applyTheme(): void {
    document.documentElement.dataset['theme'] = this.theme();
  }
}
