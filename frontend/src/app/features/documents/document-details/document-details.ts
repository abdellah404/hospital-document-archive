import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, Router } from '@angular/router';
import { ArchivedDocument, DocumentService } from '../../../core/services/document';

@Component({
  selector: 'app-document-details',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './document-details.html',
  styleUrl: './document-details.css',
})
export class DocumentDetailsComponent implements OnDestroy, OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly documentService = inject(DocumentService);
  private readonly sanitizer = inject(DomSanitizer);
  private objectUrl: string | null = null;

  readonly document = signal<ArchivedDocument | null>(null);
  readonly previewUrl = signal<SafeResourceUrl | null>(null);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  ngOnInit(): void {
    const document = history.state?.document as ArchivedDocument | undefined;
    if (!document || document.id !== this.route.snapshot.paramMap.get('documentId')) {
      this.loading.set(false);
      this.errorMessage.set(
        'Les informations de ce document ne sont plus disponibles. Revenez à la recherche et sélectionnez le document à nouveau.',
      );
      return;
    }

    this.document.set(document);
    this.documentService.getFile(document.id).subscribe({
      next: (file) => {
        this.objectUrl = URL.createObjectURL(file);
        this.previewUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(this.objectUrl));
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('Impossible de charger le PDF.');
      },
    });
  }

  goBack(): void {
    this.router.navigate(['/documents/search']);
  }

  ngOnDestroy(): void {
    if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
  }
}
