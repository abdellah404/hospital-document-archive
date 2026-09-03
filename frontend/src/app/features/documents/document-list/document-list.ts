import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth';
import {
  DeletedDocument,
  DocumentResponse,
  DocumentService,
} from '../../../core/services/document';

type StatusFilter = 'all' | 'imported' | 'processing' | 'review' | 'archived' | 'errors';

@Component({
  selector: 'app-document-list',
  standalone: true,
  imports: [DatePipe, FormsModule, MatIconModule, MatTooltipModule, RouterLink],
  templateUrl: './document-list.html',
  styleUrl: './document-list.css',
})
export class DocumentListComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly documentService = inject(DocumentService);
  private readonly router = inject(Router);

  readonly user = this.authService.currentUser;
  readonly documents = signal<DocumentResponse[]>([]);
  readonly deletedDocuments = signal<DeletedDocument[]>([]);
  readonly deletedDocumentCount = signal(0);
  readonly view = signal<'active' | 'deleted'>('active');
  readonly query = signal('');
  readonly statusFilter = signal<StatusFilter>('all');
  readonly loading = signal(true);
  readonly errorMessage = signal('');
  readonly successMessage = signal('');
  readonly resumingDocumentId = signal<string | null>(null);
  readonly downloadingDocumentId = signal<string | null>(null);
  readonly deletingDocumentId = signal<string | null>(null);
  readonly restoringDocumentId = signal<string | null>(null);

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

  readonly filteredDeletedDocuments = computed(() => {
    const query = this.query().trim().toLocaleLowerCase('fr');
    const statuses = this.statusesFor(this.statusFilter());
    return this.deletedDocuments().filter(document => {
      const matchesQuery = !query
        || document.original_filename.toLocaleLowerCase('fr').includes(query)
        || this.statusLabel(document.status).toLocaleLowerCase('fr').includes(query);
      return matchesQuery && (!statuses || statuses.includes(document.status));
    });
  });

  ngOnInit(): void {
    if (!this.user()) {
      this.authService.getCurrentUser().subscribe(user => {
        if (user.role === 'ADMIN') this.loadDeletedDocumentCount();
      });
    } else if (this.user()?.role === 'ADMIN') {
      this.loadDeletedDocumentCount();
    }
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

  downloadDocument(item: DocumentResponse): void {
    if (this.downloadingDocumentId()) return;

    this.downloadingDocumentId.set(item.id);
    this.errorMessage.set('');
    this.documentService.getFile(item.id).subscribe({
      next: file => {
        const url = URL.createObjectURL(file);
        const link = document.createElement('a');
        link.href = url;
        link.download = item.original_filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 0);
        this.downloadingDocumentId.set(null);
      },
      error: () => {
        this.downloadingDocumentId.set(null);
        this.errorMessage.set('Impossible de télécharger le document.');
      },
    });
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

  showActiveDocuments(): void {
    this.view.set('active');
    this.errorMessage.set('');
  }

  showDeletedDocuments(): void {
    if (this.user()?.role !== 'ADMIN') return;

    this.view.set('deleted');
    this.loading.set(true);
    this.errorMessage.set('');
    this.documentService.getDeletedDocuments().subscribe({
      next: documents => {
        this.deletedDocuments.set(documents);
        this.deletedDocumentCount.set(documents.length);
        this.loading.set(false);
      },
      error: error => {
        this.loading.set(false);
        this.errorMessage.set(
          error.error?.detail ?? 'Impossible de charger la corbeille.',
        );
      },
    });
  }

  deleteDocument(document: DocumentResponse): void {
    if (this.user()?.role !== 'ADMIN' || this.deletingDocumentId()) return;

    const confirmed = window.confirm(
      `Supprimer le document « ${document.original_filename} » ? Le PDF sera conservé et le document pourra être restauré depuis la corbeille.`,
    );
    if (!confirmed) return;

    this.deletingDocumentId.set(document.id);
    this.errorMessage.set('');
    this.successMessage.set('');
    this.documentService.deleteDocument(document.id).subscribe({
      next: () => {
        this.documents.update(documents => (
          documents.filter(item => item.id !== document.id)
        ));
        this.deletedDocumentCount.update(count => count + 1);
        this.deletingDocumentId.set(null);
        this.successMessage.set('Document déplacé dans la corbeille.');
      },
      error: error => {
        this.deletingDocumentId.set(null);
        this.errorMessage.set(
          error.error?.detail ?? 'Impossible de supprimer le document.',
        );
      },
    });
  }

  restoreDocument(document: DeletedDocument): void {
    if (this.user()?.role !== 'ADMIN' || this.restoringDocumentId()) return;

    const confirmed = window.confirm(
      `Restaurer le document « ${document.original_filename} » ?`,
    );
    if (!confirmed) return;

    this.restoringDocumentId.set(document.id);
    this.errorMessage.set('');
    this.successMessage.set('');
    this.documentService.restoreDocument(document.id).subscribe({
      next: () => {
        this.deletedDocuments.update(documents => (
          documents.filter(item => item.id !== document.id)
        ));
        this.deletedDocumentCount.update(count => Math.max(0, count - 1));
        this.restoringDocumentId.set(null);
        this.successMessage.set('Document restauré avec succès.');
      },
      error: error => {
        this.restoringDocumentId.set(null);
        this.errorMessage.set(
          error.error?.detail ?? 'Impossible de restaurer le document.',
        );
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

  private loadDeletedDocumentCount(): void {
    this.documentService.getDeletedDocuments().subscribe({
      next: documents => this.deletedDocumentCount.set(documents.length),
    });
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
