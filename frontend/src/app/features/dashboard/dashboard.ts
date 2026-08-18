import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { AuthService } from '../../core/services/auth';
import { DocumentResponse, DocumentService } from '../../core/services/document';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [DatePipe, FormsModule, MatIconModule, RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class DashboardComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly documentService = inject(DocumentService);

  readonly user = this.authService.currentUser;
  readonly documents = signal<DocumentResponse[]>([]);
  readonly loading = signal(true);
  readonly errorMessage = signal('');
  readonly documentFilter = signal<'all' | 'archived' | 'processing' | 'errors'>('all');

  ngOnInit(): void {
    if (!this.user()) this.authService.getCurrentUser().subscribe();
    this.loadDocuments();
  }

  private loadDocuments(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.documentService.getDocuments().subscribe({
      next: documents => { this.documents.set(documents); this.loading.set(false); },
      error: () => { this.loading.set(false); this.errorMessage.set('Impossible de charger l’activité des documents.'); },
    });
  }

  get archivedCount(): number { return this.documents().filter(document => document.status === 'ARCHIVED').length; }
  get processingCount(): number { return this.documents().filter(document => !['ARCHIVED', 'OCR_ERROR', 'AI_ERROR', 'PROCESSING_ERROR', 'ARCHIVE_ERROR'].includes(document.status)).length; }
  readonly filteredRecentDocuments = computed(() => {
    const filter = this.documentFilter();
    const filtered = this.documents().filter((document) => {
      if (filter === 'archived') return document.status === 'ARCHIVED';
      if (filter === 'errors') return ['OCR_ERROR', 'AI_ERROR', 'PROCESSING_ERROR', 'ARCHIVE_ERROR'].includes(document.status);
      if (filter === 'processing') return !['ARCHIVED', 'OCR_ERROR', 'AI_ERROR', 'PROCESSING_ERROR', 'ARCHIVE_ERROR'].includes(document.status);
      return true;
    });
    return filtered.slice(0, 5);
  });
  get recentDocuments(): DocumentResponse[] { return this.filteredRecentDocuments(); }
}
