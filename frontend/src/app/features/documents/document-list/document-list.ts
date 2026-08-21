import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth';
import { DocumentResponse, DocumentService } from '../../../core/services/document';

type StatusFilter = 'all' | 'imported' | 'processing' | 'review' | 'archived' | 'errors';

@Component({
  selector: 'app-document-list',
  standalone: true,
  imports: [DatePipe, FormsModule, MatIconModule, RouterLink],
  templateUrl: './document-list.html',
  styleUrl: './document-list.css',
})
export class DocumentListComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly documentService = inject(DocumentService);
  private readonly router = inject(Router);

  readonly user = this.authService.currentUser;
  readonly documents = signal<DocumentResponse[]>([]);
  readonly query = signal('');
  readonly statusFilter = signal<StatusFilter>('all');
  readonly loading = signal(true);
  readonly errorMessage = signal('');
  readonly resumingDocumentId = signal<string | null>(null);

  readonly filteredDocuments = computed(() => {
    const query = this.query().trim().toLocaleLowerCase('fr');
    const statuses = this.statusesFor(this.statusFilter());
    return this.documents().filter(document => {
      const matchesQuery = !query
        || document.original_filename.toLocaleLowerCase('fr').includes(query)
        || this.statusLabel(document.status).toLocaleLowerCase('fr').includes(query);
      return matchesQuery && (!statuses || statuses.includes(document.status));
    });
  });

  ngOnInit(): void {
    if (!this.user()) this.authService.getCurrentUser().subscribe();
    this.documentService.getDocuments().subscribe({
      next: documents => {
        this.documents.set(documents);
        this.loading.set(false);
      },
      error: error => {
        this.loading.set(false);
        this.errorMessage.set(error.error?.detail ?? 'Impossible de charger les documents.');
      },
    });
  }

  canResume(status: string): boolean {
    return ['IMPORTED', 'OCR_ERROR', 'AI_ERROR', 'PROCESSING_ERROR', 'ARCHIVE_ERROR'].includes(status);
  }

  continueReview(document: DocumentResponse): void {
    void this.router.navigate(['/documents/import'], { state: { documentId: document.id } });
  }

  resumeProcessing(document: DocumentResponse): void {
    if (this.user()?.role !== 'ADMIN' || !this.canResume(document.status) || this.resumingDocumentId()) return;
    this.resumingDocumentId.set(document.id);
    this.errorMessage.set('');
    this.documentService.resumeProcessing(document.id).subscribe({
      next: () => {
        this.resumingDocumentId.set(null);
        void this.router.navigate(['/documents/import'], {
          state: { documentId: document.id, resumed: true },
        });
      },
      error: error => {
        this.resumingDocumentId.set(null);
        this.errorMessage.set(error.error?.detail ?? 'Impossible de relancer le traitement du document.');
      },
    });
  }

  statusLabel(status: string): string {
    return ({
      IMPORTED: 'Importé',
      OCR_PROCESSING: 'Analyse en cours',
      AI_PROCESSING: 'Extraction en cours',
      READY_FOR_REVIEW: 'À vérifier',
      ARCHIVED: 'Archivé',
      OCR_ERROR: 'Erreur OCR',
      AI_ERROR: 'Erreur d’extraction',
      PROCESSING_ERROR: 'Erreur de traitement',
      ARCHIVE_ERROR: 'Erreur d’archivage',
    } as Record<string, string>)[status] ?? status.replaceAll('_', ' ');
  }

  statusBadgeClass(status: string): string {
    if (status === 'ARCHIVED') return 'app-badge app-badge-success';
    if (status === 'READY_FOR_REVIEW') return 'app-badge app-badge-review';
    if (status === 'OCR_PROCESSING' || status === 'AI_PROCESSING') return 'app-badge app-badge-processing';
    if (status.endsWith('_ERROR')) return 'app-badge app-badge-error';
    return 'app-badge app-badge-info';
  }

  private statusesFor(filter: StatusFilter): string[] | null {
    return ({
      all: null,
      imported: ['IMPORTED'],
      processing: ['OCR_PROCESSING', 'AI_PROCESSING'],
      review: ['READY_FOR_REVIEW'],
      archived: ['ARCHIVED'],
      errors: ['OCR_ERROR', 'AI_ERROR', 'PROCESSING_ERROR', 'ARCHIVE_ERROR'],
    } as Record<StatusFilter, string[] | null>)[filter];
  }
}
