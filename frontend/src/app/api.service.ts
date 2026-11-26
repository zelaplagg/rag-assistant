import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  AskResponse,
  FlashcardsResponse,
  Health,
  Note,
  SummaryResponse,
  UploadResult,
} from './models';

const API_URL = '/api';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  health(): Observable<Health> {
    return this.http.get<Health>(`${API_URL}/health`);
  }

  notes(): Observable<Note[]> {
    return this.http.get<Note[]>(`${API_URL}/notes`);
  }

  upload(files: File[]): Observable<UploadResult[]> {
    const body = new FormData();
    for (const file of files) body.append('files', file, file.name);
    return this.http.post<UploadResult[]>(`${API_URL}/upload`, body);
  }

  loadSample(): Observable<{ chunks: number }> {
    return this.http.post<{ chunks: number }>(`${API_URL}/sample`, {});
  }

  deleteNote(name: string): Observable<void> {
    return this.http.delete<void>(`${API_URL}/notes/${encodeURIComponent(name)}`);
  }

  clearNotes(): Observable<void> {
    return this.http.delete<void>(`${API_URL}/notes`);
  }

  ask(question: string): Observable<AskResponse> {
    return this.http.post<AskResponse>(`${API_URL}/ask`, { question });
  }

  summary(topic: string): Observable<SummaryResponse> {
    return this.http.post<SummaryResponse>(`${API_URL}/summary`, { topic });
  }

  flashcards(topic: string, count: number): Observable<FlashcardsResponse> {
    return this.http.post<FlashcardsResponse>(`${API_URL}/flashcards`, { topic, count });
  }
}
