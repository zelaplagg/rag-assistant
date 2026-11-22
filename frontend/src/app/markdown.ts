import { NgTemplateOutlet } from '@angular/common';
import { Component, computed, input } from '@angular/core';

/*
 * A tiny, dependency-free Markdown renderer for LLM answers.
 * It builds a structure and renders it with normal Angular bindings — never innerHTML —
 * so model output can not inject HTML or scripts.
 */

export interface Inline {
  t: 'text' | 'bold' | 'em' | 'code' | 'cite';
  v: string;
}

export interface Block {
  k: 'p' | 'ul' | 'ol' | 'h' | 'code';
  inl: Inline[];
  items: Inline[][];
  text: string;
}

const block = (k: Block['k'], part: Partial<Block> = {}): Block => ({ k, inl: [], items: [], text: '', ...part });

// **bold**, `code`, [file.md] citations, *emphasis*
const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\.(?:md|txt|pdf|docx)\]|\*[^*\n]+\*)/i;

export function parseInline(src: string): Inline[] {
  return src
    .split(INLINE)
    .filter((part) => part !== '')
    .map((part): Inline => {
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return { t: 'bold', v: part.slice(2, -2) };
      if (part.startsWith('`') && part.endsWith('`') && part.length > 2) return { t: 'code', v: part.slice(1, -1) };
      if (part.startsWith('[') && part.endsWith(']')) return { t: 'cite', v: part.slice(1, -1) };
      if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return { t: 'em', v: part.slice(1, -1) };
      return { t: 'text', v: part };
    });
}

export function parseMarkdown(src: string): Block[] {
  const blocks: Block[] = [];
  const lines = src.replace(/\r\n?/g, '\n').split('\n');
  const state: { para: string[]; list: { k: 'ul' | 'ol'; items: Inline[][] } | null } = { para: [], list: null };

  const flush = (): void => {
    if (state.para.length) blocks.push(block('p', { inl: parseInline(state.para.join(' ')) }));
    if (state.list) blocks.push(block(state.list.k, { items: state.list.items }));
    state.para = [];
    state.list = null;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (/^\s*```/.test(line)) {
      flush();
      const buf: string[] = [];
      i++;
      while (i < lines.length && !/^\s*```/.test(lines[i])) buf.push(lines[i++]);
      blocks.push(block('code', { text: buf.join('\n') }));
      continue;
    }
    if (!line.trim()) {
      flush();
      continue;
    }

    const heading = /^\s{0,3}#{1,6}\s+(.*)$/.exec(line);
    if (heading) {
      flush();
      blocks.push(block('h', { inl: parseInline(heading[1]) }));
      continue;
    }

    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const item = bullet ?? numbered;
    if (item) {
      const kind = bullet ? 'ul' : 'ol';
      if (state.para.length || (state.list && state.list.k !== kind)) flush();
      if (!state.list) state.list = { k: kind, items: [] };
      state.list.items.push(parseInline(item[1]));
      continue;
    }

    if (state.list && /^\s{2,}\S/.test(line)) {
      // wrapped continuation line of the previous list item
      state.list.items[state.list.items.length - 1].push(...parseInline(' ' + line.trim()));
      continue;
    }

    if (state.list) flush();
    state.para.push(line.trim());
  }
  flush();
  return blocks;
}

@Component({
  selector: 'app-md',
  imports: [NgTemplateOutlet],
  template: `
    <ng-template #inl let-parts>
      @for (p of parts; track $index) {
        @switch (p.t) {
          @case ('bold') {
            <strong>{{ p.v }}</strong>
          }
          @case ('em') {
            <em>{{ p.v }}</em>
          }
          @case ('code') {
            <code>{{ p.v }}</code>
          }
          @case ('cite') {
            <span class="cite">{{ p.v }}</span>
          }
          @default {
            {{ p.v }}
          }
        }
      }
    </ng-template>

    @for (b of blocks(); track $index) {
      @switch (b.k) {
        @case ('h') {
          <h4><ng-container [ngTemplateOutlet]="inl" [ngTemplateOutletContext]="{ $implicit: b.inl }" /></h4>
        }
        @case ('ul') {
          <ul>
            @for (it of b.items; track $index) {
              <li><ng-container [ngTemplateOutlet]="inl" [ngTemplateOutletContext]="{ $implicit: it }" /></li>
            }
          </ul>
        }
        @case ('ol') {
          <ol>
            @for (it of b.items; track $index) {
              <li><ng-container [ngTemplateOutlet]="inl" [ngTemplateOutletContext]="{ $implicit: it }" /></li>
            }
          </ol>
        }
        @case ('code') {
          <pre>{{ b.text }}</pre>
        }
        @default {
          <p><ng-container [ngTemplateOutlet]="inl" [ngTemplateOutletContext]="{ $implicit: b.inl }" /></p>
        }
      }
    }
  `,
  styles: [
    `
      :host {
        display: block;
        line-height: 1.65;
        overflow-wrap: anywhere;
      }
      p,
      ul,
      ol {
        margin: 0 0 0.75em;
      }
      :host > :last-child {
        margin-bottom: 0;
      }
      h4 {
        margin: 1em 0 0.4em;
        font-size: 1rem;
        font-weight: 700;
      }
      ul,
      ol {
        padding-left: 1.25em;
      }
      li {
        margin: 0.25em 0;
      }
      li::marker {
        color: var(--accent);
      }
      code {
        font-family: ui-monospace, 'SF Mono', Menlo, monospace;
        font-size: 0.88em;
        padding: 0.12em 0.4em;
        border-radius: 6px;
        background: var(--surface-2);
      }
      pre {
        margin: 0 0 0.75em;
        padding: 12px 14px;
        border-radius: 12px;
        background: var(--surface-2);
        overflow-x: auto;
        font: 0.85rem/1.5 ui-monospace, 'SF Mono', Menlo, monospace;
      }
      .cite {
        display: inline-block;
        padding: 0 7px;
        border-radius: 6px;
        background: var(--accent-soft);
        color: var(--accent);
        font-size: 0.78em;
        font-weight: 600;
        line-height: 1.6;
      }
    `,
  ],
})
export class MarkdownComponent {
  readonly text = input.required<string>();
  protected readonly blocks = computed(() => parseMarkdown(this.text()));
}
